"""Measure Poppins-Bold capitals and derive correct stroke-order paths.

Anchors come from the rendered glyph's ink mask, never from guesses. Results
are normalized: x as a fraction of the glyph's ink width, y as a fraction of
cap height above the baseline. x and y are scaled independently on the page,
so arcs carry separate rx/ry.

Stroke forms:
  ("line", (x0, y0, x1, y1))
  ("arc",  (cx, cy, rx, ry, start_deg, end_deg))
Angles are standard math convention; the sweep runs start -> end.
"""

import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

FONT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "assets", "fonts", "Poppins-Bold.ttf")
RENDER_PX = 900


def _runs(line):
    idx = np.nonzero(line)[0]
    if idx.size == 0:
        return []
    splits = np.nonzero(np.diff(idx) > 1)[0]
    return [(g[0], g[-1]) for g in np.split(idx, splits + 1)]


def even_curve(path, min_gap=5.0, step=3.0, window=7):
    """Turn a noisy traced path into one a dotted line can follow evenly.

    Tracing leaves pixel-scale back-and-forth jitter; a dash pattern laid
    over that bunches its dots wherever the path doubles back. Thinning to
    points at least `min_gap` px apart is coarser than the jitter, so it
    can't double back; then respace evenly by arc length and average."""
    kept = [path[0]]
    for p in path[1:]:
        if math.hypot(p[0] - kept[-1][0], p[1] - kept[-1][1]) >= min_gap:
            kept.append(p)
    if kept[-1] != path[-1]:
        kept.append(path[-1])

    even = [kept[0]]
    need = step
    for (x0, y0), (x1, y1) in zip(kept, kept[1:]):
        seg = math.hypot(x1 - x0, y1 - y0)
        pos = 0.0
        while seg - pos >= need:
            pos += need
            t = pos / seg
            even.append((x0 + (x1 - x0) * t, y0 + (y1 - y0) * t))
            need = step
        need -= seg - pos
    if even[-1] != kept[-1]:
        even.append(kept[-1])

    out = [even[0]]
    for i in range(1, len(even) - 1):
        seg = even[max(0, i - window):i + window + 1]
        out.append((sum(p[0] for p in seg) / len(seg), sum(p[1] for p in seg) / len(seg)))
    out.append(even[-1])
    return out


class Glyph:
    def __init__(self, ch):
        font = ImageFont.truetype(FONT_PATH, RENDER_PX)
        img = Image.new("L", (RENDER_PX * 2, RENDER_PX * 2), 0)
        ImageDraw.Draw(img).text((RENDER_PX // 2, RENDER_PX // 2), ch, font=font, fill=255)
        self.mask = np.array(img) > 128
        ys, xs = np.nonzero(self.mask)
        self.l, self.t, self.r, self.b = xs.min(), ys.min(), xs.max(), ys.max()
        self.w, self.h = self.r - self.l, self.b - self.t

    def nx(self, px):
        return float((px - self.l) / self.w)

    def ny(self, py):
        return float((self.b - py) / self.h)

    def row_runs(self, frac_from_top):
        y = int(round(self.t + frac_from_top * self.h))
        y = min(max(y, self.t), self.b)
        return _runs(self.mask[y])

    def col_runs(self, frac_from_left):
        x = int(round(self.l + frac_from_left * self.w))
        x = min(max(x, self.l), self.r)
        return _runs(self.mask[:, x])

    def stem_x(self, at=0.25):
        """Centre of the left vertical stem, sampled where it stands alone."""
        s, e = self.row_runs(at)[0]
        return self.nx((s + e) / 2)

    def ring_thickness_y(self, at_x=0.5):
        """Vertical thickness of a round stroke, sampled down a column."""
        s, e = self.col_runs(at_x)[0]
        return abs(self.ny(s) - self.ny(e))

    def has_ink(self, nx, ny):
        px = int(round(self.l + nx * self.w))
        py = int(round(self.b - ny * self.h))
        if not (0 <= py < self.mask.shape[0] and 0 <= px < self.mask.shape[1]):
            return False
        return bool(self.mask[py, px])

    def ink_arc_span(self, cx, cy, rx, ry, step=1.0):
        """Angular span of ink along an ellipse — finds where an open round
        letter's terminals actually are instead of assuming them."""
        angles = [a * step for a in range(int(360 / step))]
        inked = [self.has_ink(cx + rx * math.cos(math.radians(a)),
                              cy + ry * math.sin(math.radians(a))) for a in angles]
        if all(inked):
            return 0.0, 360.0
        gap_start = next(i for i, v in enumerate(inked) if not v)
        order = [(gap_start + k) % len(angles) for k in range(len(angles))]
        run, best = [], []
        for i in order:
            if inked[i]:
                run.append(i)
            else:
                if len(run) > len(best):
                    best = run
                run = []
        if len(run) > len(best):
            best = run
        return angles[best[0]], angles[best[0]] + len(best) * step

    def ray_mid(self, cx, cy, deg):
        """Cast a ray (pixel space) from inside a counter and return the
        midpoint of the first band of ink it crosses — a point on the
        stroke's true centreline, whatever shape the bowl is."""
        dx, dy = math.cos(math.radians(deg)), -math.sin(math.radians(deg))
        H, W = self.mask.shape
        t, entry = 0.0, None
        while True:
            x, y = int(round(cx + dx * t)), int(round(cy + dy * t))
            if not (0 <= x < W and 0 <= y < H):
                return None
            ink = self.mask[y, x]
            if entry is None and ink:
                entry = t
            elif entry is not None and not ink:
                m = (entry + t) / 2
                return (cx + dx * m, cy + dy * m), t - entry
            t += 0.5

    def bowl_centreline(self, counter_px, stem_x_px, step=2.0, lane=None):
        """Centreline of a bowl hung off the left stem: sweep rays from the
        counter's centre over the right-hand side (90 deg -> -90 deg), then
        join each end back to the stem along its bar.

        A ray is only trusted when the ink it crosses is about one stroke
        thick. Where two bowls merge (B's waist) a diagonal ray runs through
        the whole junction and its midpoint is meaningless, so those are
        dropped and the gap is bridged."""
        cx, cy = counter_px
        hits = []
        a = 90.0
        while a >= -90.0:
            hit = self.ray_mid(cx, cy, a)
            if hit:
                hits.append(hit)
            a -= step
        chords = sorted(c for _, c in hits)
        typical = chords[len(chords) // 2]
        pts = [p for p, c in hits if c <= typical * 1.3]

        # A bar travelled by two strokes (B's waist) gets split into lanes so
        # the two dotted paths run side by side instead of on top of each
        # other. lane = (band_centre_y_px, band_half_px, shift_px).
        if lane:
            band_y, band_half, shift = lane
            fade = 2.0 * band_half  # ease the shift in, so the lane has no step

            def weight(y):
                d = abs(y - band_y) - band_half
                return 1.0 if d <= 0 else max(0.0, 1.0 - d / fade)

            pts = [(x, y + shift * weight(y)) for x, y in pts]

        # smoothing so the dotted path reads as one clean curve
        k = 4
        smooth = [pts[0]]
        for i in range(1, len(pts) - 1):
            lo, hi = max(0, i - k), min(len(pts), i + k + 1)
            xs = [p[0] for p in pts[lo:hi]]
            ys = [p[1] for p in pts[lo:hi]]
            smooth.append((sum(xs) / len(xs), sum(ys) / len(ys)))
        smooth.append(pts[-1])

        path = [(stem_x_px, smooth[0][1])] + smooth + [(stem_x_px, smooth[-1][1])]
        return [(self.nx(x), self.ny(y)) for x, y in path]


    # --- generic toolkit (pixel space) used by F-Z ---------------------------
    def inside(self, x, y):
        xi, yi = int(round(x)), int(round(y))
        H, W = self.mask.shape
        return 0 <= xi < W and 0 <= yi < H and bool(self.mask[yi, xi])

    def run_mid(self, t, idx):
        """Centre of the idx-th ink run on the row t of the way down. Through
        a straight band, a horizontal cut's midpoint lies on its centreline."""
        y = int(round(self.t + t * self.h))
        s, e = _runs(self.mask[y])[idx]
        return ((s + e) / 2, float(y))

    def col_mid(self, xf, idx):
        x = int(round(self.l + xf * self.w))
        s, e = _runs(self.mask[:, x])[idx]
        return (float(x), (s + e) / 2)

    @staticmethod
    def line(p, q):
        dx, dy = q[0] - p[0], q[1] - p[1]
        m = math.hypot(dx, dy)
        return (p, (dx / m, dy / m))

    @staticmethod
    def meet(l1, l2):
        (x1, y1), (dx1, dy1) = l1
        (x2, y2), (dx2, dy2) = l2
        den = dx1 * dy2 - dy1 * dx2
        t = ((x2 - x1) * dy2 - (y2 - y1) * dx2) / den
        return (x1 + dx1 * t, y1 + dy1 * t)

    def to_edge(self, p, d, inset=1.0):
        """Walk from p along d to the edge of the ink."""
        x, y = p
        t = 0.0
        while self.inside(x + d[0] * (t + 0.5), y + d[1] * (t + 0.5)):
            t += 0.5
        t = max(0.0, t - inset)
        return (x + d[0] * t, y + d[1] * t)

    def pull_inside(self, p, d, margin):
        """A vertex where two centrelines cross can land just outside a
        pointed tip; step along d until it sits `margin` px inside."""
        x, y = p
        t = 0.0
        while not self.inside(x + d[0] * t, y + d[1] * t) and t < self.h:
            t += 0.5
        return (x + d[0] * (t + margin), y + d[1] * (t + margin))

    def dist(self):
        if not hasattr(self, "_dt"):
            import cv2
            self._dt = cv2.distanceTransform(self.mask.astype(np.uint8), cv2.DIST_L2, 5)
        return self._dt

    def ridge_snap(self, p, radius):
        """Nearest point of maximum thickness — the stroke's middle."""
        dt = self.dist()
        x, y = int(round(p[0])), int(round(p[1]))
        r = int(radius)
        win = dt[y - r:y + r + 1, x - r:x + r + 1]
        iy, ix = np.unravel_index(np.argmax(win), win.shape)
        return (float(x - r + ix), float(y - r + iy))

    def ridge_route(self, waypoints, head="edge", tail="edge"):
        """Curved stroke through normalized waypoints, riding the middle of
        the ink: a least-cost path where cost falls off steeply with
        distance from the edge, so it hugs the ridge.

        Each end is then finished one of three ways:
          "edge" - run straight out along the tangent to the ink's edge
          "face-down" / "face-up" - the stroke ends in a flat level cut
                   facing that way (S, G, J): curve in to the middle of the
                   cut, arriving square to it
          "none" - leave it; the caller finishes the stroke (G's corner)"""
        from skimage.graph import route_through_array
        dt = self.dist()
        pad = 4
        y0, y1 = self.t - pad, self.b + pad + 1
        x0, x1 = self.l - pad, self.r + pad + 1
        sub = dt[y0:y1, x0:x1]
        cost = np.where(sub > 0, 1.0 / (sub + 1.0) ** 2, 1e3)

        pts = [(self.l + nx * self.w, self.b - ny * self.h) for nx, ny in waypoints]
        pts = [self.ridge_snap(p, 0.05 * self.h) for p in pts]
        path = []
        for a, b in zip(pts, pts[1:]):
            seg, _ = route_through_array(
                cost, (int(a[1]) - y0, int(a[0]) - x0), (int(b[1]) - y0, int(b[0]) - x0),
                fully_connected=True, geometric=True)
            seg = [(c + x0, r + y0) for r, c in seg]
            path.extend(seg if not path else seg[1:])
        path = even_curve([(float(x), float(y)) for x, y in path],
                          min_gap=4.0, step=3.0, window=6)

        path = self._finish(path, tail)
        path = list(reversed(self._finish(list(reversed(path)), head)))
        return path

    def _finish(self, path, how):
        """Finish the END of `path` (reverse it to finish the start)."""
        if how == "none":
            return path
        k = min(8, len(path) - 1)
        if how == "edge":
            return path + [self.to_edge(path[-1], self._unit(path[-1 - k], path[-1]))]

        # "face-down" / "face-up": the stroke ends in a flat level cut facing
        # that way. Near a flat cut the ridge forks toward the cut's corners,
        # so the traced path drifts off-centre and meets the cut at a slant.
        # Instead, walk back from the cut row by row: the middle of the
        # stroke's ink on each row is a true centre point, so together they
        # follow the real curve right up to the middle of the cut.
        sgn = 1.0 if how == "face-down" else -1.0      # pixel y grows downward
        dt = self.dist()
        half = float(np.median([dt[int(round(y)), int(round(x))] for x, y in path]))
        cut_y, cs, ce = self.find_cut(path[-1], sgn, reach=3.0 * half)
        cut_w = ce - cs
        mids = [((cs + ce) / 2, cut_y - sgn * 1.0)]
        x = mids[0][0]
        travelled = 0.0
        y = cut_y
        while travelled < 3.0 * half:
            y -= int(sgn)
            runs = _runs(self.mask[int(y)])
            hit = [r for r in runs if r[0] <= x <= r[1]]
            if not hit:
                break
            a, b = hit[0]
            if b - a > 1.5 * cut_w:     # the stroke is turning level; rows stop
                break                   # cutting straight across it
            nx_ = (a + b) / 2
            travelled += math.hypot(nx_ - x, 1.0)
            x = nx_
            mids.append((x, float(y)))
        far = mids[-1]
        j = min(range(len(path)), key=lambda k: math.hypot(path[k][0] - far[0], path[k][1] - far[1]))
        joined = even_curve(path[:j] + list(reversed(mids)), min_gap=3.0, step=3.0, window=3)
        # the traced path and the row centres disagree slightly where they
        # meet; ease across that one join so it doesn't show as a step
        k = min(range(len(joined)), key=lambda i: math.hypot(joined[i][0] - far[0], joined[i][1] - far[1]))
        span, win = int(2.5 * half / 3.0), int(1.2 * half / 3.0)
        eased = list(joined)
        for i in range(max(1, k - span), min(len(joined) - 1, k + span)):
            seg = joined[max(0, i - win):i + win + 1]
            ax = sum(p[0] for p in seg) / len(seg)
            ay = sum(p[1] for p in seg) / len(seg)
            # feathered: full easing at the join, none at the edges of the
            # region, so the easing leaves no seam of its own
            f = 1.0 - abs(i - k) / span
            eased[i] = (joined[i][0] + (ax - joined[i][0]) * f,
                        joined[i][1] + (ay - joined[i][1]) * f)
        return eased

    def find_cut(self, near, sgn, reach):
        """The flat level cut that ends a stroke close to `near`.
        sgn=+1: the cut faces down (ink above, paper below); -1: faces up.
        Only looks a short way ahead of `near` in the direction the cut
        faces — G's bar, a longer level edge further off, must not win.
        Returns (row, first x, last x) of the longest level edge there."""
        H, W = self.mask.shape
        x0, x1 = int(round(near[0] - reach)), int(round(near[0] + reach))
        x0, x1 = max(0, x0), min(W, x1)
        ys = range(int(round(near[1])), int(round(near[1] + sgn * reach)), int(sgn))
        best = None
        for y in ys:
            if not (1 <= y < H - 1):
                continue
            edge = self.mask[y, x0:x1] & ~self.mask[y + int(sgn), x0:x1]
            for a, b in _runs(edge):
                if best is None or b - a > best[2] - best[1]:
                    best = (y, a + x0, b + x0)
        return best

    @staticmethod
    def _unit(frm, to):
        dx, dy = to[0] - frm[0], to[1] - frm[1]
        m = math.hypot(dx, dy) or 1.0
        return (dx / m, dy / m)

    def norm(self, pts):
        return [(self.nx(x), self.ny(y)) for x, y in pts]

    def seg(self, p, q):
        (a, b), (c, d) = self.norm([p, q])
        return ("line", (a, b, c, d))

    def stem(self, idx=0, t=(0.5, 0.8)):
        """A vertical stem: centred from two rows, run to top and bottom."""
        a, b = self.run_mid(t[0], idx), self.run_mid(t[1], idx)
        x = (a[0] + b[0]) / 2
        mid = (x, (a[1] + b[1]) / 2)
        return self.to_edge(mid, (0, -1)), self.to_edge(mid, (0, 1)), x

    def regions(self):
        """(outside, [counters sorted top to bottom]) as bool masks."""
        import cv2
        bg = (~self.mask).astype(np.uint8)
        n, labels = cv2.connectedComponents(bg)
        outside_label = labels[0, 0]
        outside = labels == outside_label
        counters = [labels == k for k in range(1, n) if k != outside_label]
        counters.sort(key=lambda m: np.nonzero(m)[0].mean())
        return outside, counters

    def medial_bowl(self, own, stem_x_px, lane_frac=0.30):
        """Centreline of the bowl around counter `own`, as the boundary of
        'closer to this counter than to anything else'.

        Against the outside edge that boundary is exactly mid-stroke. Against
        a neighbouring counter (B's waist) the distance is scaled so the
        boundary sits lane_frac of the way across the shared bar: each bowl
        gets its own lane there, with no seam where the lane begins."""
        import cv2

        def dist_to(region):
            src = np.where(region, 0, 255).astype(np.uint8)
            return cv2.distanceTransform(src, cv2.DIST_L2, 5)

        outside, counters = self.regions()
        d_own = dist_to(counters[own])
        others = [dist_to(outside)]
        scale = lane_frac / (1.0 - lane_frac)
        others += [dist_to(c) * scale for j, c in enumerate(counters) if j != own]
        nearer = (d_own < np.minimum.reduce(others)).astype(np.uint8) * 255

        contours, _ = cv2.findContours(nearer, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        loop = max(contours, key=cv2.contourArea)[:, 0, :].astype(float)

        # the loop also runs down the stem; keep only the part right of the
        # counter's left wall, which is the bowl stroke itself
        cut = np.nonzero(counters[own])[1].min() + 2
        right = loop[:, 0] > cut
        start = next(i for i in range(len(loop)) if right[i] and not right[i - 1])
        run = []
        i = start
        while right[i % len(loop)] and len(run) < len(loop):
            run.append(tuple(loop[i % len(loop)]))
            i += 1
        if run[0][1] > run[-1][1]:   # begin at the upper end, like the pen
            run.reverse()

        smooth = even_curve(run, min_gap=2.0, step=3.0, window=6)
        full = [(stem_x_px, smooth[0][1])] + smooth + [(stem_x_px, smooth[-1][1])]
        return [(self.nx(x), self.ny(y)) for x, y in full]


def strokes_for(ch):
    g = Glyph(ch)

    if ch == "A":
        apex = g.nx(sum(g.row_runs(0.02)[0]) / 2)
        base = g.row_runs(0.985)
        left_foot = g.nx(sum(base[0]) / 2)
        right_foot = g.nx(sum(base[-1]) / 2)
        # crossbar height: last ink run down the centre column
        bar_y = g.ny(sum(g.col_runs(0.5)[-1]) / 2)
        # the legs' centrelines at that height, by interpolation
        t = 1.0 - bar_y
        bar_l = apex + (left_foot - apex) * t
        bar_r = apex + (right_foot - apex) * t
        return [
            ("line", (apex, 1.0, left_foot, 0.0)),
            ("line", (apex, 1.0, right_foot, 0.0)),
            ("line", (bar_l, bar_y, bar_r, bar_y)),
        ]

    if ch == "E":
        sx = g.stem_x(0.25)
        arms = g.col_runs(0.85)  # a column crossing all three arms
        top_y = g.ny(sum(arms[0]) / 2)
        mid_y = g.ny(sum(arms[1]) / 2)
        bot_y = g.ny(sum(arms[2]) / 2)
        top_end = g.nx(g.row_runs(1 - top_y)[0][1]) - 0.04
        mid_end = g.nx(g.row_runs(1 - mid_y)[0][1]) - 0.04
        bot_end = g.nx(g.row_runs(1 - bot_y)[0][1]) - 0.04
        return [
            ("line", (sx, 1.0, sx, 0.0)),
            ("line", (sx, top_y, top_end, top_y)),
            ("line", (sx, mid_y, mid_end, mid_y)),
            ("line", (sx, bot_y, bot_end, bot_y)),
        ]

    if ch in ("B", "D"):
        sx = g.stem_x(0.25 if ch == "B" else 0.5)
        stem_px = g.l + sx * g.w
        # a column clear of the stem crosses each horizontal bar as its own
        # run; the white gaps between them are the counters
        col_x_frac = 0.45 if ch == "B" else 0.5
        col_px = g.l + col_x_frac * g.w
        bars = g.col_runs(col_x_frac)
        counters = []
        for upper, lower in zip(bars, bars[1:]):
            cy = (upper[1] + lower[0]) / 2
            row = _runs(g.mask[int(round(cy))])
            cx = (row[0][1] + row[1][0]) / 2 if len(row) >= 2 else col_px
            counters.append((cx, cy))
        strokes = [("line", (sx, 1.0, sx, 0.0))]
        # interior bars (B's waist) are shared by the bowl above and below
        shared = bars[1:-1]
        if not shared:
            for counter in counters:
                strokes.append(("poly", g.bowl_centreline(counter, stem_px)))
            return strokes

        for i in range(len(counters)):
            strokes.append(("poly", g.medial_bowl(i, stem_px)))
        return strokes

    if ch == "C":
        side = g.row_runs(0.5)[0]           # left wall of the ring
        tx = g.nx(side[1]) - g.nx(side[0])
        ty = g.ring_thickness_y(0.5)
        rx = 0.5 - tx / 2
        ry = 0.5 - ty / 2
        # measure where the ring is actually cut, then start at the upper
        # terminal and sweep counter-clockwise round to the lower one
        a0, a1 = g.ink_arc_span(0.5, 0.5, rx, ry)  # upper terminal -> lower
        pad = 3.0
        return [("arc", (0.5, 0.5, rx, ry, a0 + pad, a1 - pad))]

    UP, DOWN, LEFT, RIGHT = (0, -1), (0, 1), (-1, 0), (1, 0)
    arm_inset = 0.04 * g.w  # bar ends stop just short of the tip, like E

    def rev(d):
        return (-d[0], -d[1])

    def poly(pts):
        return ("poly", g.norm(pts))

    if ch == "F":
        top, bot, sx = g.stem(0, (0.75, 0.92))   # below the middle arm
        ta, ma = g.col_mid(0.62, 0), g.col_mid(0.62, 1)
        return [
            g.seg(top, bot),
            g.seg((sx, ta[1]), g.to_edge(ta, RIGHT, arm_inset)),
            g.seg((sx, ma[1]), g.to_edge(ma, RIGHT, arm_inset)),
        ]

    if ch == "G":
        # Round the ring from the upper terminal and up the right side, then
        # a HARD turn left along the bar — the letter has a square corner
        # there, so the path must too, not a rounded one.
        bar = g.col_mid(0.75, 1)                       # the bar, in the middle run
        bar_y = bar[1]
        bar_inner = float(_runs(g.mask[int(round(bar_y))])[-1][0])
        side = _runs(g.mask[int(round(g.b - 0.30 * g.h))])[-1]   # right side, below the bar
        w_pt = (g.nx((side[0] + side[1]) / 2), 0.30)
        # the ring is open on the right, so the only route from the terminal
        # to the right side goes the correct way round
        ring = g.ridge_route([(0.84, 0.74), w_pt], head="face-down", tail="none")
        corner = (ring[-1][0], bar_y)
        return [poly(ring + [corner, (bar_inner + arm_inset, bar_y)])]

    if ch == "H":
        lt, lb, lx = g.stem(0, (0.2, 0.8))
        rt, rb, rx = g.stem(-1, (0.2, 0.8))
        y = g.col_mid(0.5, 0)[1]
        return [g.seg(lt, lb), g.seg(rt, rb), g.seg((lx, y), (rx, y))]

    if ch == "I":
        top, bot, _ = g.stem(0, (0.3, 0.7))
        return [g.seg(top, bot)]

    if ch == "J":
        # begin below the flat top: near a flat end the ridge forks toward the
        # corners, so the head is run straight up to the edge instead
        # ...and the hook ends in a flat cut, so land on its middle
        return [poly(g.ridge_route([(0.78, 0.75), (0.14, 0.26)], head="edge", tail="face-up"))]

    if ch == "K":
        top, bot, sx = g.stem(0, (0.15, 0.85))
        stem_line = ((sx, 0.0), DOWN)
        arm = g.line(g.run_mid(0.3, 1), g.run_mid(0.08, 1))       # pointing up-right
        leg = g.line(g.run_mid(0.72, 1), g.run_mid(0.93, 1))      # pointing down-right
        arm_top = g.to_edge(arm[0], arm[1])
        # stop where the arm meets the stem's edge; continuing to the stem's
        # centreline would dive through the notch under the arm
        stem_edge = float(_runs(g.mask[int(round(g.t + 0.85 * g.h))])[0][1])
        at_stem = g.meet(arm, ((stem_edge, 0.0), DOWN))
        # ...or where the centreline leaves the ink into that notch, if sooner
        at_notch = g.to_edge(arm[0], rev(arm[1]))
        arm_end = min((at_stem, at_notch),
                      key=lambda p: math.hypot(p[0] - arm[0][0], p[1] - arm[0][1]))
        leg_start = g.meet(leg, arm)
        return [g.seg(top, bot), g.seg(arm_top, arm_end),
                g.seg(leg_start, g.to_edge(leg[0], leg[1]))]

    if ch == "L":
        top, bot, sx = g.stem(0, (0.3, 0.6))
        b = g.col_mid(0.75, 0)
        return [g.seg(top, bot), g.seg((sx, b[1]), g.to_edge(b, RIGHT, arm_inset))]

    if ch == "M":
        lt, lb, _ = g.stem(0, (0.5, 0.85))
        rt, rb, _ = g.stem(-1, (0.5, 0.85))
        dl = g.line(g.run_mid(0.44, 1), g.run_mid(0.56, 1))
        dr = g.line(g.run_mid(0.44, 2), g.run_mid(0.56, 2))
        v = g.meet(dl, dr)
        if not g.inside(*v):
            v = g.pull_inside(v, UP, 6)
        tl = g.to_edge(dl[0], rev(dl[1]))
        tr = g.to_edge(dr[0], rev(dr[1]))
        return [g.seg(lt, lb), poly([tl, v, tr]), g.seg(rt, rb)]

    if ch == "N":
        lt, lb, _ = g.stem(0, (0.75, 0.9))     # left stem stands alone low down
        rt, rb, _ = g.stem(-1, (0.1, 0.25))    # right stem stands alone up top
        d = g.line(g.run_mid(0.45, 1), g.run_mid(0.55, 1))
        return [g.seg(lt, lb),
                g.seg(g.to_edge(d[0], rev(d[1])), g.to_edge(d[0], d[1])),
                g.seg(rb, rt)]                 # push up

    if ch == "O":
        side = g.row_runs(0.5)[0]
        tx = g.nx(side[1]) - g.nx(side[0])
        ty = g.ring_thickness_y(0.5)
        return [("arc", (0.5, 0.5, 0.5 - tx / 2, 0.5 - ty / 2, 90, 435))]

    if ch == "P":
        top, bot, sx = g.stem(0, (0.8, 0.92))
        return [g.seg(top, bot), ("poly", g.medial_bowl(0, sx))]

    if ch == "Q":
        # the tail hangs below the ring, so measure the ring on its own
        # lowest point of the ring, on a column near its centre but left of
        # where the tail begins
        ring_b = float(_runs(g.mask[:, int(round(g.l + 0.45 * g.w))])[-1][1])
        ym = (g.t + ring_b) / 2
        row = _runs(g.mask[int(round(ym))])
        left, right = row[0][0], row[-1][1]
        tx_px = row[0][1] - row[0][0]
        cxp = (left + right) / 2
        ty_px = _runs(g.mask[:, int(round(cxp))])[0]
        ty_px = ty_px[1] - ty_px[0]
        rxp = (right - left) / 2 - tx_px / 2
        ryp = (ring_b - g.t) / 2 - ty_px / 2
        ring = ("arc", (g.nx(cxp), g.ny(ym), rxp / g.w, ryp / g.h, 90, 435))

        def frac(y):
            return (y - g.t) / g.h
        tail = g.line(g.run_mid(frac(ring_b + 0.3 * (g.b - ring_b)), -1),
                      g.run_mid(frac(ring_b + 0.75 * (g.b - ring_b)), -1))
        # start the tail where it crosses the ring's own centreline
        (px, py), (dx, dy) = tail
        s = 0.0
        while ((px - dx * s - cxp) / rxp) ** 2 + ((py - dy * s - ym) / ryp) ** 2 > 1 and s < g.h:
            s += 0.5
        start = (px - dx * s, py - dy * s)
        return [ring, g.seg(start, g.to_edge(tail[0], tail[1]))]

    if ch == "R":
        top, bot, sx = g.stem(0, (0.75, 0.9))
        # Trace the bowl with the leg cleared away: otherwise the leg's ink
        # drags the bowl's centreline down where the two meet.
        # (x=0.36 is right of the stem but left of where the leg joins the
        # bar, so the bar's run there is the bar alone)
        bar = _runs(g.mask[:, int(round(g.l + 0.36 * g.w))])[1]
        stem_edge = _runs(g.mask[int(round(g.t + 0.85 * g.h))])[0][1]
        full = g.mask.copy()
        g.mask[bar[1] + 1:, stem_edge + 1:] = False
        bowl = g.medial_bowl(0, sx)
        g.mask = full
        bar_y = g.b - bowl[-1][1] * g.h
        leg = g.line(g.run_mid(0.74, -1), g.run_mid(0.93, -1))
        start = g.meet(leg, ((0.0, bar_y), RIGHT))
        return [g.seg(top, bot), ("poly", bowl), g.seg(start, g.to_edge(leg[0], leg[1]))]

    if ch == "S":
        # both ends are flat cuts: start and finish on their middles
        return [poly(g.ridge_route([(0.8, 0.8), (0.18, 0.2)], head="face-down", tail="face-up"))]

    if ch == "T":
        top, bot, _ = g.stem(0, (0.4, 0.8))
        b = g.col_mid(0.08, 0)
        return [g.seg(top, bot),
                g.seg(g.to_edge(b, LEFT), g.to_edge(b, RIGHT, arm_inset))]

    if ch == "U":
        return [poly(g.ridge_route([(0.13, 0.75), (0.87, 0.75)]))]

    if ch == "V":
        dl = g.line(g.run_mid(0.15, 0), g.run_mid(0.55, 0))
        dr = g.line(g.run_mid(0.15, 1), g.run_mid(0.55, 1))
        v = g.meet(dl, dr)
        if not g.inside(*v):
            v = g.pull_inside(v, UP, 6)
        return [poly([g.to_edge(dl[0], rev(dl[1])), v, g.to_edge(dr[0], rev(dr[1]))])]

    if ch == "W":
        d = [g.line(g.run_mid(0.47, i), g.run_mid(0.68, i)) for i in range(4)]
        v1, peak, v2 = g.meet(d[0], d[1]), g.meet(d[1], d[2]), g.meet(d[2], d[3])
        if not g.inside(*v1):
            v1 = g.pull_inside(v1, UP, 6)
        if not g.inside(*v2):
            v2 = g.pull_inside(v2, UP, 6)
        if not g.inside(*peak):
            peak = g.pull_inside(peak, DOWN, 6)
        return [poly([g.to_edge(d[0][0], rev(d[0][1])), v1, peak, v2,
                      g.to_edge(d[3][0], rev(d[3][1]))])]

    if ch == "X":
        # this X's arms aren't collinear through the crossing, so each
        # diagonal is measured once above it and once below
        back = g.line(g.run_mid(0.1, 0), g.run_mid(0.9, 1))   # \  top-left down
        fwd = g.line(g.run_mid(0.1, 1), g.run_mid(0.9, 0))    # /  top-right down
        return [g.seg(g.to_edge(back[0], rev(back[1])), g.to_edge(back[0], back[1])),
                g.seg(g.to_edge(fwd[0], rev(fwd[1])), g.to_edge(fwd[0], fwd[1]))]

    if ch == "Y":
        al = g.line(g.run_mid(0.08, 0), g.run_mid(0.3, 0))
        ar = g.line(g.run_mid(0.08, 1), g.run_mid(0.3, 1))
        j = g.meet(al, ar)
        sx = (g.run_mid(0.75, 0)[0] + g.run_mid(0.92, 0)[0]) / 2
        # both arms end in the junction; stop each a little short so their
        # arrowheads point into it instead of landing on top of each other
        short = 0.036 * g.h   # just enough to keep the two arrowheads apart

        def before_j(line):
            (px, py), (dx, dy) = line
            return (j[0] - dx * short, j[1] - dy * short)
        return [g.seg(g.to_edge(al[0], rev(al[1])), before_j(al)),
                g.seg(g.to_edge(ar[0], rev(ar[1])), before_j(ar)),
                g.seg((sx, j[1]), g.to_edge((sx, j[1]), DOWN))]

    if ch == "Z":
        tb, bb = g.col_mid(0.5, 0), g.col_mid(0.5, -1)
        diag = g.line(g.run_mid(0.42, 0), g.run_mid(0.58, 0))
        tr = g.meet(diag, ((0.0, tb[1]), RIGHT))
        bl = g.meet(diag, ((0.0, bb[1]), RIGHT))
        return [g.seg(g.to_edge(tb, LEFT), tr), g.seg(tr, bl),
                g.seg(bl, g.to_edge(bb, RIGHT, arm_inset))]

    raise KeyError(ch)


if __name__ == "__main__":
    for ch in "ABCDE":
        print(ch)
        for s in strokes_for(ch):
            kind, data = s
            if kind == "poly":
                print("    poly", len(data), "pts",
                      tuple(round(v, 3) for v in data[0]), "->",
                      tuple(round(v, 3) for v in data[-1]))
            else:
                print("   ", kind, tuple(round(float(v), 3) for v in data))
