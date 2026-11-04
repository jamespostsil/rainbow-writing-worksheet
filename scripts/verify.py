"""Check every letter's stroke paths against the real glyph.

Numbers, not eyeballing: for points along each path, walk out along the
path's normal to the ink edge on both sides. A centred path is equidistant;
report the worst lopsidedness, any point outside the ink, and any place the
path doubles back. Also writes overlay sheets for a visual pass.
"""

import math
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from letterform import Glyph, strokes_for, FONT_PATH


def to_px(g, kind, data, n=120):
    if kind == "line":
        a, b, c, d = data
        pts = [(a + (c - a) * i / n, b + (d - b) * i / n) for i in range(n + 1)]
    elif kind == "poly":
        pts = data
    elif kind == "dot":
        pts = [data]
    else:
        cx, cy, rx, ry, a0, a1 = data
        pts = [(cx + rx * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
                cy + ry * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]
    return [(g.l + x * g.w, g.b - y * g.h) for x, y in pts]


def resample(pts, step=4.0):
    out = [pts[0]]
    need = step
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        seg = math.hypot(x1 - x0, y1 - y0)
        pos = 0.0
        while seg - pos >= need:
            pos += need
            t = pos / seg
            out.append((x0 + (x1 - x0) * t, y0 + (y1 - y0) * t))
            need = step
        need -= seg - pos
    return out


def reach(g, x, y, dx, dy, cap):
    t = 0.0
    while t < cap and g.inside(x + dx * t, y + dy * t):
        t += 0.5
    return t


def check_stroke(g, pts, skip=0.10):
    """Returns (outside_count, worst_asym, worst_at, reversals)."""
    if len(pts) == 1:   # a dot: it only has to sit on its ink
        return (0 if g.inside(*pts[0]) else 1), 0.0, None, 0
    pts = resample(pts)
    n = len(pts)
    outside = sum(1 for x, y in pts if not g.inside(x, y))
    rev = 0
    for (a, b), (c, d), (e, f) in zip(pts, pts[1:], pts[2:]):
        if (c - a) * (e - c) + (d - b) * (f - d) < 0:
            rev += 1
    cap = 0.35 * g.cap_px   # not g.h: a mark (Ñ's tilde) makes g.h taller
    samples = []
    for i in range(2, n - 2):
        if i < n * skip or i > n * (1 - skip):
            continue  # terminals: the stroke is cut off here anyway
        (x0, y0), (x1, y1) = pts[i - 2], pts[i + 2]
        tx, ty = x1 - x0, y1 - y0
        m = math.hypot(tx, ty) or 1.0
        nx, ny = -ty / m, tx / m
        x, y = pts[i]
        d1, d2 = reach(g, x, y, nx, ny, cap), reach(g, x, y, -nx, -ny, cap)
        if d1 + d2 == 0 or d1 >= cap or d2 >= cap:
            continue
        samples.append((d1, d2, x, y))
    worst, at = 0.0, None
    if samples:
        widths = sorted(d1 + d2 for d1, d2, _, _ in samples)
        typical = widths[len(widths) // 2]
        for d1, d2, x, y in samples:
            if d1 + d2 > 1.35 * typical:
                continue  # crossing a junction: the other stroke widens it
            asym = abs(d1 - d2) / (d1 + d2)
            if asym > worst:
                worst, at = asym, (g.nx(x), g.ny(y))
    return outside, worst, at, rev


def contours(g):
    """The ink's outlines, kept on the glyph itself. (Not in a dict keyed
    by id(g): Python reuses ids once a glyph is freed, and later letters
    were measured against an earlier letter's outline.)"""
    import cv2
    if not hasattr(g, "_contours"):
        cs, _ = cv2.findContours(g.mask.astype(np.uint8), cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
        g._contours = [c[:, 0, :].astype(float) for c in cs if len(c) > 20]
    return g._contours


def end_check(g, pts, stroke_w, turn=30.0, win=6):
    """Is a stroke end on the middle of the cut it ends on?

    check_stroke skips the first and last 10% of every stroke, which is
    exactly where Ñ's tilde, Ž's caron and Ø's slash went wrong (each ended
    in a corner). So: from the end point, follow the ink's outline both ways
    until it turns more than `turn` degrees (a corner). That stretch is the
    cut. A centred end sits in its middle, and a real cut is at least about
    half a stroke wide; a corner gives a lopsided or very short stretch.
    Ends inside the ink (a junction, or E's bars that stop short of the
    tip) are skipped. Returns (lopsided, cut_len_px) or None."""
    x, y = pts
    dt = g.dist()
    xi, yi = int(round(x)), int(round(y))
    if g.inside(x, y) and dt[yi, xi] > 4:
        return None
    best = None
    for c in contours(g):
        d = np.hypot(c[:, 0] - x, c[:, 1] - y)
        k = int(np.argmin(d))
        if best is None or d[k] < best[0]:
            best = (d[k], c, k)
    _, c, k = best
    n = len(c)

    def direction(i):
        a, b = c[(i - win) % n], c[(i + win) % n]
        v = b - a
        return v / (np.hypot(*v) or 1.0)

    d0 = direction(k)
    lens = []
    for step in (1, -1):
        i, length = k, 0.0
        while length < 0.6 * g.cap_px:
            j = (i + step) % n
            if math.degrees(math.acos(max(-1.0, min(1.0, float(direction(j) @ d0))))) > turn:
                break
            length += float(np.hypot(*(c[j] - c[i])))
            i = j
        # A stroke can end on an edge that carries on along another stroke
        # (the top of E's stem runs on along its top arm), so only the first
        # 0.6 stroke widths each way count. A centred end still scores ~0%,
        # and a corner still scores ~100%.
        lens.append(min(length, 0.6 * stroke_w))
    total = lens[0] + lens[1]
    lop = abs(lens[0] - lens[1]) / total if total else 1.0
    if total < 0.5 * stroke_w:
        lop = 1.0                 # the "cut" is a corner, not a cut
    return lop, total


def stroke_width(g, pts):
    dt = g.dist()
    vals = [dt[int(round(y)), int(round(x))] for x, y in pts if g.inside(x, y)]
    return 2.0 * float(np.median(vals)) if vals else 0.0


def load_expected():
    """(letter, stroke, check) -> (limit, reason) from verify_expected.txt."""
    import os
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "verify_expected.txt")
    out = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            ch, n, check, limit, reason = line.split(None, 4)
            out[(ch, int(n), check)] = (int(limit), reason)
    return out


def v_over(expected, ch, n, check, value):
    """Is this flag NEW: not listed, or worse than its listed limit?"""
    e = expected.get((ch, n, check))
    return e is None or value > e[0]


def sheet(letters, path, cols=6, tile=300):
    rows = (len(letters) + cols - 1) // cols
    img = Image.new("RGB", (cols * tile, rows * tile), "white")
    d = ImageDraw.Draw(img)
    lab = ImageFont.truetype(FONT_PATH, 18)
    for k, ch in enumerate(letters):
        r, c = divmod(k, cols)
        ox, oy = c * tile, r * tile
        g = Glyph(ch)
        s = (tile * 0.86) / max(g.w, g.h)
        # glyph, scaled into the tile
        crop = g.mask[g.t:g.b + 1, g.l:g.r + 1]
        gi = Image.fromarray((crop * 255).astype(np.uint8)).resize(
            (int(g.w * s), int(g.h * s)))
        gx, gy = ox + (tile - gi.width) // 2, oy + (tile - gi.height) // 2
        grey = Image.new("RGB", gi.size, (205, 205, 212))
        img.paste(grey, (gx, gy), gi)
        for n, (kind, data) in enumerate(strokes_for(ch), 1):
            p = [(gx + (x - g.l) * s, gy + (y - g.t) * s) for x, y in to_px(g, kind, data)]
            if kind == "dot":
                bx, by = p[0]
                d.ellipse([bx - 11, by - 11, bx + 11, by + 11], fill=(20, 90, 200))
                d.text((bx, by), str(n), fill="white", font=lab, anchor="mm")
                continue
            d.line(p, fill=(200, 30, 30), width=3)
            (x1, y1) = p[-1]
            back, j = 0.0, len(p) - 1          # aim by length, not by count
            while j > 0 and back < 10:
                back += math.hypot(p[j][0] - p[j - 1][0], p[j][1] - p[j - 1][1])
                j -= 1
            (x0, y0) = p[j]
            a = math.atan2(y1 - y0, x1 - x0)
            d.polygon([(x1, y1), (x1 - 12 * math.cos(a - .5), y1 - 12 * math.sin(a - .5)),
                       (x1 - 12 * math.cos(a + .5), y1 - 12 * math.sin(a + .5))], fill=(200, 30, 30))
            bx, by = p[0]
            d.ellipse([bx - 11, by - 11, bx + 11, by + 11], fill=(20, 90, 200))
            d.text((bx, by), str(n), fill="white", font=lab, anchor="mm")
        d.text((ox + 8, oy + 6), ch, fill=(0, 0, 0), font=lab)
    img.save(path)


if __name__ == "__main__":
    letters = sys.argv[1] if len(sys.argv) > 1 else "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    expected = load_expected()
    new_count = 0
    print(f"{'':3}{'stroke':>7} {'outside':>8} {'lopsided':>9}  {'worst at (x,y)':<16} "
          f"{'doubles back':>12} {'start':>6} {'end':>6}")
    for ch in letters:
        g = Glyph(ch)
        for n, (kind, data) in enumerate(strokes_for(ch), 1):
            px = to_px(g, kind, data)
            out, worst, at, rev = check_stroke(g, px)
            ends = ["", ""]
            measured = {"outside": out, "lopsided": round(worst * 100), "doubles": rev}
            if kind != "dot":
                sw = stroke_width(g, resample(px))
                for k, (name, p) in enumerate((("start", px[0]), ("end", px[-1]))):
                    r = end_check(g, p, sw)
                    if r is None:
                        ends[k] = "-"        # ends inside the ink: not on a cut
                    else:
                        ends[k] = f"{r[0]:.0%}"
                        measured[name] = round(r[0] * 100)
            limits = {"outside": 0, "lopsided": 25, "doubles": 0, "start": 25, "end": 25}
            problems = [c for c, v in measured.items() if v > limits[c]]
            new = [c for c in problems if v_over(expected, ch, n, c, measured[c])]
            if new:
                new_count += 1
                flag = "  <-- NEW: " + ", ".join(new)
            elif problems:
                flag = "  (expected: " + expected[(ch, n, problems[0])][1] + ")"
            else:
                flag = ""
            at_s = f"({at[0]:.2f},{at[1]:.2f})" if at else "-"
            print(f"{ch:3}{n:>7} {out:>8} {worst:>8.0%}  {at_s:<16} {rev:>12} "
                  f"{ends[0]:>6} {ends[1]:>6}{flag}")
    sheet(letters[:13], "verify_sheet_1.png")
    if len(letters) > 13:
        sheet(letters[13:], "verify_sheet_2.png")
    print(f"\n{new_count} stroke{'s' if new_count != 1 else ''} with NEW problems"
          + ("" if new_count else " (all flags are listed in verify_expected.txt)"))
    sys.exit(1 if new_count else 0)
