"""Rainbow writing worksheets — one giant hollow capital per page.

The child follows the numbered dotted strokes (correct letter formation, each
path measured off the real glyph), traces the letter once per rainbow color,
and colors a band of the rainbow after each pass.

Every page is also checked for layout collisions before it is written.
"""

import argparse
import math
import os

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter as LETTER
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import Color
from fontTools.ttLib import TTFont as FTFont

from letterform import strokes_for

FONTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "fonts")
LETTER_TTF = os.path.join(FONTS, "Poppins-Bold.ttf")
PIC_TTF = os.path.join(FONTS, "OpenMoji-black-glyf.ttf")

pdfmetrics.registerFont(TTFont("Poppins", os.path.join(FONTS, "Poppins-Regular.ttf")))
pdfmetrics.registerFont(TTFont("Poppins-Bold", LETTER_TTF))
pdfmetrics.registerFont(TTFont("Poppins-SemiBold", os.path.join(FONTS, "Poppins-SemiBold.ttf")))
pdfmetrics.registerFont(TTFont("Pic", PIC_TTF))

_lf = FTFont(LETTER_TTF)
_lupm = _lf["head"].unitsPerEm
_lglyf, _lcmap = _lf["glyf"], _lf.getBestCmap()

_pf = FTFont(PIC_TTF)
_pupm = _pf["head"].unitsPerEm
_pglyf, _pcmap = _pf["glyf"], _pf.getBestCmap()

W, H = LETTER
MARGIN = 52

INK = Color(0.15, 0.15, 0.18)
SOFT = Color(0.42, 0.42, 0.46)
LINE = Color(0.34, 0.34, 0.38)
GUIDE = Color(0.55, 0.55, 0.60)
WHITE = Color(1, 1, 1)

CAP_RATIO = 0.702
# Lowercase, as fractions of the em (Poppins Bold): the tall letters' top
# (b, d, l), the x-height (top of x), room above for i's dot and below for
# descenders (g, p, y).
ASC_RATIO = 0.74
XH_RATIO = 0.558
LOWER_TOP = 0.801
LOWER_BOTTOM = -0.275
RULE = Color(0.72, 0.72, 0.76)

HEADER_Y = H - 56
INSTRUCTION_Y = H - 90
CUE_Y = H - 110

BOX_TOP = H - 134
BOX_BOTTOM = 212
LETTER_SIDE = 22   # the letter may come this close to the page edge

# The cloud sits on the rainbow's LEFT foot. Rainbow + cloud span the same
# x range as when the cloud was on the right (24pt to 288pt).
RAIN_CX, RAIN_CY = MARGIN + 116, 66
RAIN_INNER, RAIN_BAND, RAIN_BANDS = 34, 14, 6
CLOUD_W = 128

PIC_CX = W - MARGIN - 78
PIC_CY = 146          # vertical centre of the picture's ink
PIC_SIZE = 108
PIC_MAX_H = 94        # ink height budget
PIC_MAX_W = 124
CAPTION_Y = 58        # caption baseline
CAPTION_SIZE = 17
FOOTER_Y = 26

BADGE_FORWARD = 0.085  # badge sits this far along its stroke, x cap height
BADGE_GAP = 8          # pt of white between two badges
BADGE_CLEAR = 6        # pt between a badge and another stroke's line or arrow
ARROW_AIM = 10         # arrowheads point along the stroke's last this-many pt

# Every word on a page is in that page's language. Translations other than
# English are first drafts: have a native speaker check them before printing
# for real.
PAGE_TEXT = {
    "en": {"title": "Rainbow writing", "name": "Name:",
           "trace": "Trace the numbered strokes in order. Use a new color each time.",
           "say": "Say it:", "is_for": "{L} is for {word}", "page": "{n} of {total}"},
    "es": {"title": "Escritura arcoíris", "name": "Nombre:",
           "trace": "Repasa los trazos numerados en orden. Usa un color nuevo cada vez.",
           "say": "Dilo:", "is_for": "{L} de {word}", "page": "{n} de {total}"},
    "tr": {"title": "Gökkuşağı yazısı", "name": "Adın:",
           "trace": "Numaralı çizgilerin üzerinden sırayla geç. Her seferinde yeni bir renk kullan.",
           "say": "Söyle:", "is_for": "{L} harfi: {word}", "page": "{n} / {total}"},
    "sv": {"title": "Regnbågsskrivning", "name": "Namn:",
           "trace": "Följ de numrerade dragen i ordning. Byt färg varje gång.",
           "say": "Säg:", "is_for": "{L} som i {word}", "page": "{n} av {total}"},
    "da": {"title": "Regnbueskrivning", "name": "Navn:",
           "trace": "Følg de nummererede streger i rækkefølge. Brug en ny farve hver gang.",
           "say": "Sig:", "is_for": "{L} som i {word}", "page": "{n} af {total}"},
    "hr": {"title": "Dugino pisanje", "name": "Ime:",
           "trace": "Prati numerirane poteze redom. Svaki put uzmi novu boju.",
           "say": "Reci:", "is_for": "{L} kao {word}", "page": "{n} od {total}"},
    "pl": {"title": "Tęczowe pisanie", "name": "Imię:",
           "trace": "Obrysuj ponumerowane linie po kolei. Za każdym razem użyj nowego koloru.",
           "say": "Powiedz:", "is_for": "{L} jak {word}", "page": "{n} z {total}"},
    "fr": {"title": "Écriture arc-en-ciel", "name": "Prénom :",
           "trace": "Repasse les traits numérotés dans l'ordre. Change de couleur à chaque fois.",
           "say": "Dis :", "is_for": "{L} comme {word}", "page": "{n} sur {total}"},
}

# letter -> (keyword, picture, spoken formation cue[, language]). The picture
# is an OpenMoji codepoint, or the name of a drawing made here. The language
# (a PAGE_TEXT key) defaults to English.
LETTERS = {
    "A": ("Apple", 0x1F34E, "slant down, slant down, across"),
    "B": ("Bear", 0x1F43B, "down, around, around"),
    "C": ("Cat", 0x1F431, "curve all the way around"),
    "D": ("Duck", 0x1F986, "down, then big curve around"),
    "E": ("Egg", 0x1F95A, "down, across, across, across"),
    "F": ("Fish", 0x1F41F, "down, across, across"),
    "G": ("Grapes", 0x1F347, "curve around, up, then across"),
    "H": ("House", 0x1F3E0, "down, down, across"),
    "I": ("Ice cream", 0x1F366, "straight down"),
    "J": ("Jellyfish", 0x1FABC, "down, then curve back"),
    "K": ("Kite", 0x1FA81, "down, slant in, slant out"),
    "L": ("Lion", 0x1F981, "down, across"),
    "M": ("Moon", 0x1F319, "down, slant down, slant up, down"),
    "N": ("Nose", 0x1F443, "down, slant down, up"),
    "O": ("Octopus", 0x1F419, "curve all the way around"),
    "P": ("Pig", 0x1F437, "down, around"),
    "Q": ("Queen", 0x1FAC5, "curve all the way around, then slant"),
    "R": ("Rabbit", 0x1F430, "down, around, slant down"),
    "S": ("Sun", 0x2600, "curve back, curve forward"),
    "T": ("Turtle", 0x1F422, "down, then across the top"),
    "U": ("Umbrella", 0x2602, "down, curve around, up"),
    "V": ("Van", 0x1F690, "slant down, slant up"),
    "W": ("Whale", 0x1F433, "slant down, up, down, up"),
    "X": ("Xylophone", "xylophone", "slant down, slant down"),
    "Y": ("Yo-yo", 0x1FA80, "slant in, slant in, down"),
    "Z": ("Zebra", 0x1F993, "across, slant down, across"),
    # Letters with marks. Not in the default alphabet: ask for them with
    # --letters. Each page is in a language that uses the letter.
    "Ñ": ("ñame", 0x1F360, "abajo, en diagonal, arriba, y la onda", "es"),       # yam
    "Ç": ("çay", 0x2615, "yuvarlak çiz, sonra çengel", "tr"),                   # tea
    "Ü": ("üzüm", 0x1F347, "aşağı, yuvarla, yukarı, nokta, nokta", "tr"),       # grapes
    "Å": ("åsna", 0x1FACF, "snett ner, snett ner, tvärs över, sedan ringen", "sv"),  # donkey
    "Ø": ("øre", 0x1F442, "hele vejen rundt, så skråstregen", "da"),           # ear
    "Ž": ("žirafa", 0x1F992, "preko, koso dolje, preko, pa kvačica", "hr"),    # giraffe
    "Ł": ("łódka", 0x26F5, "w dół, w prawo, potem kreska", "pl"),               # boat
    "É": ("étoile", 0x2B50, "en bas, trois traits, puis l'accent", "fr"),      # star
    # Lowercase (English). Not in the default alphabet: ask for them with
    # --letters (lowercase letters stay lowercase).
    "a": ("apple", 0x1F34E, "circle back around, then down"),
    "b": ("bear", 0x1F43B, "down, then circle forward"),
    "c": ("cat", 0x1F431, "curve back around"),
    "d": ("duck", 0x1F986, "circle back around, then tall down"),
    "e": ("egg", 0x1F95A, "across, then circle back around"),
    "i": ("inchworm", 0x1F41B, "down, then a dot"),
    "l": ("lion", 0x1F981, "tall down"),
    "n": ("nose", 0x1F443, "down, then over the hump and down"),
    "o": ("octopus", 0x1F419, "circle all the way around"),
    "t": ("turtle", 0x1F422, "down and curve, then across"),
}


def page_text(ch):
    entry = LETTERS[ch]
    return PAGE_TEXT[entry[3] if len(entry) > 3 else "en"]


# --------------------------------------------------------------------------
def letter_bbox(ch):
    g = _lglyf[_lcmap[ord(ch)]]
    return (g.xMin / _lupm, g.yMin / _lupm, g.xMax / _lupm, g.yMax / _lupm)


def pic_bbox(cp):
    g = _pglyf[_pcmap[cp]]
    return (g.xMin / _pupm, g.yMin / _pupm, g.xMax / _pupm, g.yMax / _pupm)


def text_at(c, x, y, s, font, size, color):
    """Always draw filled text. (The hollow letter's text render mode is
    reset inside its own text object — see draw_letter.)"""
    t = c.beginText(x, y)
    t.setFont(font, size)
    t.setTextRenderMode(0)
    t.setFillColor(color)
    t.textOut(s)
    c.drawText(t)


def centered(c, text, font, size, y, color):
    text_at(c, (W - pdfmetrics.stringWidth(text, font, size)) / 2, y, text, font, size, color)


def draw_header(c, title, name_label):
    text_at(c, MARGIN, HEADER_Y, title, "Poppins-Bold", 20, INK)
    text_at(c, W - 236, HEADER_Y - 4, name_label, "Poppins", 13, INK)
    c.setStrokeColor(INK)
    c.setLineWidth(1)
    c.setDash([], 0)
    # the line starts just after the label, however long the word is
    line_x = max(W - 192, W - 236 + pdfmetrics.stringWidth(name_label, "Poppins", 13) + 6)
    c.line(line_x, HEADER_Y - 8, W - MARGIN, HEADER_Y - 8)


# --------------------------------------------------------------------------
def draw_letter(c, ch):
    """Giant hollow capital. Every letter gets the same cap height except one
    that reaches past it (Q's tail, Ç's cedilla below the baseline; Ñ's
    tilde, Ü's dots above the cap height), which is sized so the whole
    character fits the box."""
    gx0, gy0, gx1, gy1 = letter_bbox(ch)
    # Width only binds for W and M; let them use nearly the full page so they
    # keep the same height as every other letter.
    box_w, box_h = (W - 2 * LETTER_SIDE), (BOX_TOP - BOX_BOTTOM)
    by_width = box_w / (gx1 - gx0)
    lower = ch.islower()
    if lower:
        # Every lowercase letter gets the SAME size and baseline, so x-height
        # letters (a, e, o) are shorter than tall ones (b, d, l) as they are
        # on ruled paper, with room kept for i's dot and for descenders.
        size = box_h / (LOWER_TOP - LOWER_BOTTOM)
        y = BOX_BOTTOM - LOWER_BOTTOM * size
    elif gy0 < -0.02 or gy1 > CAP_RATIO + 0.03:
        size = min(by_width, box_h / (gy1 - gy0))
        y = BOX_BOTTOM + (box_h - (gy1 - gy0) * size) / 2 - gy0 * size
    else:
        size = min(by_width, box_h / CAP_RATIO)
        y = BOX_BOTTOM + (box_h - CAP_RATIO * size) / 2

    glyph_w = pdfmetrics.stringWidth(ch, "Poppins-Bold", size)
    x = (W - glyph_w) / 2
    if x + gx0 * size < LETTER_SIDE or x + gx1 * size > W - LETTER_SIDE:
        x = W / 2 - (gx0 + gx1) / 2 * size   # centre the ink itself

    if lower:
        # handwriting guide lines: top line, dashed middle line, baseline.
        # Drawn first; the letter is then filled white so the lines don't
        # cross the dotted path inside it.
        c.setStrokeColor(RULE)
        c.setLineWidth(1.2)
        for level, dash in ((ASC_RATIO, []), (XH_RATIO, [6, 5]), (0.0, [])):
            c.setDash(dash, 0)
            c.line(MARGIN - 20, y + level * size, W - MARGIN + 20, y + level * size)
        c.setDash([], 0)

    c.setStrokeColor(LINE)
    c.setLineWidth(2.4)
    c.setLineJoin(1)
    c.setDash([], 0)
    tx = c.beginText(x, y)
    tx.setFont("Poppins-Bold", size)
    tx.setTextRenderMode(2 if lower else 1)    # 2: filled white, then outlined
    tx.setStrokeColor(LINE)
    tx.setFillColor(WHITE)
    tx.textOut(ch)
    # Tr lives in the graphics state and survives ET, so hand it back before
    # closing or every later string on the page renders as an outline too.
    tx.setTextRenderMode(0)
    c.drawText(tx)
    ink = (x + gx0 * size, y + gy0 * size, x + gx1 * size, y + gy1 * size)
    return x, y, size, ink


def stroke_points(kind, data, ox, oy, iw, ih, n=90):
    """Normalized stroke (fractions of the glyph's ink box) -> page points."""
    if kind == "line":
        a, b, cc, d = data
        return [(ox + a * iw, oy + b * ih), (ox + cc * iw, oy + d * ih)]
    if kind == "poly":
        return [(ox + px * iw, oy + py * ih) for px, py in data]
    if kind == "dot":
        return [(ox + data[0] * iw, oy + data[1] * ih)]
    cx, cy, rx, ry, a0, a1 = data
    return [(ox + (cx + rx * math.cos(math.radians(a))) * iw,
             oy + (cy + ry * math.sin(math.radians(a))) * ih)
            for a in [a0 + (a1 - a0) * i / n for i in range(n + 1)]]


def point_back(pts, dist):
    """The point `dist` back from the end of a polyline, measured along it."""
    travelled = 0.0
    for (x1, y1), (x0, y0) in zip(reversed(pts), list(reversed(pts))[1:]):
        seg = math.hypot(x1 - x0, y1 - y0)
        if travelled + seg >= dist:
            t = (dist - travelled) / seg if seg else 0.0
            return (x1 + (x0 - x1) * t, y1 + (y0 - y1) * t)
        travelled += seg
    return pts[0]


def point_along(pts, dist):
    travelled = 0.0
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        seg = math.hypot(x1 - x0, y1 - y0)
        if travelled + seg >= dist:
            t = (dist - travelled) / seg if seg else 0.0
            return (x0 + (x1 - x0) * t, y0 + (y1 - y0) * t)
        travelled += seg
    return pts[-1]


def draw_strokes(c, ch, x, y, size):
    """Numbered dotted formation strokes. Returns their geometry for checks."""
    gx0, gy0, gx1, gy1 = letter_bbox(ch)
    ox, oy = x + gx0 * size, y + gy0 * size
    iw, ih = (gx1 - gx0) * size, (gy1 - gy0) * size
    cap = CAP_RATIO * size
    r = max(11.0, 0.028 * cap)

    strokes = []
    for n, (kind, data) in enumerate(strokes_for(ch), start=1):
        pts = stroke_points(kind, data, ox, oy, iw, ih)
        if kind == "dot":
            # a dot is one tap: its numbered badge sits on it, no line or arrow
            strokes.append({"n": n, "pts": pts, "arrow": []})
            continue
        # Aim along the stroke's last few points of LENGTH, not its last few
        # points by count: M, V and W are zigzags stored as 3-5 corners, where
        # "three points back" is the far side of the letter.
        (ax, ay), (bx, by) = pts[-1], point_back(pts, ARROW_AIM)
        ang = math.atan2(ay - by, ax - bx)
        head = 13
        arrow = [(ax, ay),
                 (ax - head * math.cos(ang - 0.45), ay - head * math.sin(ang - 0.45)),
                 (ax - head * math.cos(ang + 0.45), ay - head * math.sin(ang + 0.45))]
        strokes.append({"n": n, "pts": pts, "arrow": arrow})

    # Badges go a little way FORWARD along their own stroke, then keep
    # sliding forward until they are clear of every other badge, every other
    # stroke's dotted line, and every arrowhead.
    for s in strokes:
        # On a closed loop (O, Q's ring) there is no terminal to mark the
        # start, so a badge set forward leaves stray dots behind it; sit it
        # on the start point instead.
        (sx0, sy0), (sx1, sy1) = s["pts"][0], s["pts"][-1]
        closed = math.hypot(sx1 - sx0, sy1 - sy0) < 0.2 * cap
        along = 0.0 if closed else BADGE_FORWARD * cap
        while True:
            bx_, by_ = point_along(s["pts"], along)
            if along >= 0.35 * cap or not badge_conflicts(bx_, by_, r, s, strokes, cap):
                break
            along += 2.0
        s["badge"] = (bx_, by_, r)

    for s in strokes:
        pts = s["pts"]
        if not s["arrow"]:
            continue          # a dot: nothing to draw but its badge
        c.setStrokeColor(GUIDE)
        c.setLineWidth(3.0)
        c.setLineCap(1)
        c.setDash([0.1, 9], 0)
        p = c.beginPath()
        p.moveTo(*pts[0])
        for pt in pts[1:]:
            p.lineTo(*pt)
        c.drawPath(p, stroke=1, fill=0)
        c.setDash([], 0)
        c.setFillColor(GUIDE)
        ah = c.beginPath()
        ah.moveTo(*s["arrow"][0])
        ah.lineTo(*s["arrow"][1])
        ah.lineTo(*s["arrow"][2])
        ah.close()
        c.drawPath(ah, stroke=0, fill=1)

    for s in strokes:
        bx_, by_, r = s["badge"]
        c.setFillColor(INK)
        c.circle(bx_, by_, r, stroke=0, fill=1)
        label = str(s["n"])
        fs = r * 1.25
        text_at(c, bx_ - pdfmetrics.stringWidth(label, "Poppins-SemiBold", fs) / 2,
                by_ - r * 0.45, label, "Poppins-SemiBold", fs, WHITE)
    return strokes


def shared_start(s, t, cap):
    return math.hypot(s["pts"][0][0] - t["pts"][0][0], s["pts"][0][1] - t["pts"][0][1]) < 0.15 * cap


def badge_conflicts(bx, by, r, s, strokes, cap):
    """Would a badge at (bx, by) hide anything that isn't its own stroke?
    Two strokes starting at the same corner (B, D, E...) are allowed to share
    that corner: the first badge may cover the second stroke's opening dots."""
    for t in strokes:
        if t is s:
            continue
        if "badge" in t:
            tx, ty, tr = t["badge"]
            if math.hypot(bx - tx, by - ty) < r + tr + BADGE_GAP:
                return True
        rest = trim_start(t["pts"], 0.14 * cap) if shared_start(s, t, cap) else t["pts"]
        if len(rest) > 1 and path_dist(bx, by, rest) < r + BADGE_CLEAR:
            return True
        if any(math.hypot(ax - bx, ay - by) < r + BADGE_CLEAR for ax, ay in t["arrow"]):
            return True
    return False


# --------------------------------------------------------------------------
def draw_rainbow(c):
    c.setStrokeColor(SOFT)
    c.setLineWidth(1.3)
    c.setDash([], 0)
    for i in range(RAIN_BANDS):
        r_in = RAIN_INNER + i * RAIN_BAND
        r_out = r_in + RAIN_BAND
        p = c.beginPath()
        p.moveTo(RAIN_CX + r_in, RAIN_CY)
        p.lineTo(RAIN_CX + r_out, RAIN_CY)
        p.arcTo(RAIN_CX - r_out, RAIN_CY - r_out, RAIN_CX + r_out, RAIN_CY + r_out, 0, 180)
        p.lineTo(RAIN_CX - r_in, RAIN_CY)
        p.arcTo(RAIN_CX - r_in, RAIN_CY - r_in, RAIN_CX + r_in, RAIN_CY + r_in, 180, -180)
        p.close()
        c.drawPath(p, stroke=1, fill=0)
    outer = RAIN_INNER + RAIN_BANDS * RAIN_BAND
    return (RAIN_CX - outer, RAIN_CY, RAIN_CX + outer, RAIN_CY + outer)


def draw_cloud(c, x, y_base, w):
    """A round, bubbly cloud: a pill-shaped base under five overlapping puffs.
    Stroked at double weight then filled white, so only the outside edge of
    the union survives and no seams show where the puffs overlap."""
    lw = 1.3
    # Five puffs; the two end puffs rest on the base line. The base is a plain
    # rectangle running between the end puffs' centres, so its flat bottom
    # meets each puff exactly where the puff touches the line — no seam.
    puffs = [(-0.40, 0.135, 0.135), (-0.21, 0.29, 0.165), (0.02, 0.38, 0.205),
             (0.25, 0.29, 0.16), (0.42, 0.125, 0.125)]
    (lx, _, _), (rx, _, _) = puffs[0], puffs[-1]
    # Height 0.22w: must be above 0.175 (the highest puff bottom, or a hole
    # shows under the middle puff) and below 0.249 (else the base's top
    # corners poke out of the end puffs and its top edge shows in a valley).
    shapes = [("rect", (x + lx * w, y_base, (rx - lx) * w, 0.22 * w))]
    for dx, dy, r in puffs:
        shapes.append(("circle", (x + dx * w, y_base + dy * w, r * w)))

    def paint(stroke, fill):
        for kind, v in shapes:
            if kind == "rect":
                c.rect(*v, stroke=stroke, fill=fill)
            else:
                c.circle(*v, stroke=stroke, fill=fill)

    c.setDash([], 0)
    c.setStrokeColor(SOFT)
    c.setLineWidth(lw * 2)
    paint(stroke=1, fill=0)
    c.setFillColor(WHITE)
    paint(stroke=0, fill=1)
    circles = [v for k, v in shapes if k == "circle"]
    left = min(v[0] - v[2] for v in circles)
    right = max(v[0] + v[2] for v in circles)
    top = max(v[1] + v[2] for v in circles)
    return (left - lw, y_base - lw, right + lw, top + lw)


def draw_xylophone(c, cx, cy):
    """Toy xylophone in the OpenMoji line style: seven bars stepping down in
    length along two converging rails, each pinned top and bottom, with two
    mallets crossed in front, heads apart (heads together read as scissors)."""
    lw = 3.0
    c.setStrokeColor(LINE)
    c.setLineWidth(lw)
    c.setLineCap(1)
    c.setLineJoin(1)
    c.setDash([], 0)
    n, bw, pitch = 7, 12.0, 16.5
    total = (n - 1) * pitch + bw
    left = cx - total / 2
    mid = cy + 10                       # bars centre here; mallets below
    heights = [78 - 6.5 * i for i in range(n)]
    xs = [left + i * pitch for i in range(n)]

    def pin(i, sign):
        return (xs[i] + bw / 2, mid + sign * (heights[i] / 2 - 10))

    # each rail is the straight line through its pins, run a little past
    # the first and last bar
    for sign in (1, -1):
        (ax, ay), (bx, by) = pin(0, sign), pin(n - 1, sign)
        L = math.hypot(bx - ax, by - ay)
        ux, uy = (bx - ax) / L, (by - ay) / L
        ext = bw / 2 + 6
        c.line(ax - ux * ext, ay - uy * ext, bx + ux * ext, by + uy * ext)
    c.setFillColor(WHITE)
    for x, h in zip(xs, heights):
        c.roundRect(x, mid - h / 2, bw, h, 3.5, stroke=1, fill=1)
    c.setFillColor(LINE)
    for i in range(n):
        for sign in (1, -1):
            c.circle(*pin(i, sign), 1.9, stroke=0, fill=1)

    # mallets: crossed sticks in front of the short end, heads well apart
    low = mid - heights[-1] / 2
    for (x0, y0), (x1, y1) in (((cx - 8, cy - 44), (cx + 52, low - 2)),
                               ((cx + 58, cy - 44), (cx - 2, low - 2))):
        c.setStrokeColor(LINE)
        c.line(x0, y0, x1, y1)
        c.setFillColor(WHITE)
        c.circle(x1, y1, 7, stroke=1, fill=1)
    return (left - 8, cy - 46, max(left + total + 8, cx + 66), mid + heights[0] / 2 + lw)


def draw_picture(c, ch):
    """Line drawing of something that starts with the letter, and its caption."""
    keyword, pic = LETTERS[ch][:2]
    if pic == "xylophone":
        ink = draw_xylophone(c, PIC_CX, PIC_CY)
    else:
        x0, y0, x1, y1 = pic_bbox(pic)
        # tall pictures (rabbit ears) are held to the same height budget
        size = min(PIC_SIZE, PIC_MAX_H / (y1 - y0), PIC_MAX_W / (x1 - x0))
        gx = PIC_CX - (x0 + x1) / 2 * size      # centre the ink, not the em box
        gy = PIC_CY - (y0 + y1) / 2 * size
        text_at(c, gx, gy, chr(pic), "Pic", size, LINE)
        ink = (gx + x0 * size, gy + y0 * size, gx + x1 * size, gy + y1 * size)

    label = page_text(ch)["is_for"].format(L=ch, word=keyword)
    lw = pdfmetrics.stringWidth(label, "Poppins", CAPTION_SIZE)
    text_at(c, PIC_CX - lw / 2, CAPTION_Y, label, "Poppins", CAPTION_SIZE, INK)
    caption = (PIC_CX - lw / 2, CAPTION_Y - 4, PIC_CX + lw / 2, CAPTION_Y + 12.5)
    return ink, caption


# --------------------------------------------------------------------------
def seg_dist(px, py, a, b):
    (x0, y0), (x1, y1) = a, b
    dx, dy = x1 - x0, y1 - y0
    L = dx * dx + dy * dy
    t = 0.0 if L == 0 else max(0.0, min(1.0, ((px - x0) * dx + (py - y0) * dy) / L))
    return math.hypot(px - (x0 + dx * t), py - (y0 + dy * t))


def path_dist(px, py, pts):
    return min(seg_dist(px, py, a, b) for a, b in zip(pts, pts[1:]))


def overlap(a, b, pad=0.0):
    return not (a[2] + pad <= b[0] or b[2] + pad <= a[0] or a[3] + pad <= b[1] or b[3] + pad <= a[1])


def trim_start(pts, dist):
    """Polyline with its first `dist` points removed."""
    travelled = 0.0
    for i, ((x0, y0), (x1, y1)) in enumerate(zip(pts, pts[1:])):
        seg = math.hypot(x1 - x0, y1 - y0)
        if travelled + seg >= dist:
            t = (dist - travelled) / seg if seg else 0.0
            return [(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t)] + pts[i + 1:]
        travelled += seg
    return []


def letter_hit_test(ch, x, y, size):
    """Page point -> is it on the letter's ink? Uses the same measured glyph
    mask the strokes come from, so round letters' empty corners count as
    empty (a bounding box would not)."""
    from letterform import Glyph
    g = Glyph(ch)
    gx0, gy0, gx1, gy1 = letter_bbox(ch)
    ox, oy = x + gx0 * size, y + gy0 * size
    iw, ih = (gx1 - gx0) * size, (gy1 - gy0) * size

    def hit(px, py):
        nx, ny = (px - ox) / iw, (py - oy) / ih
        if not (0 <= nx <= 1 and 0 <= ny <= 1):
            return False
        return g.inside(g.l + nx * g.w, g.b - ny * g.h)
    return hit


def ink_gap(hit, box, reach=24, step=2.0):
    """Smallest distance (pt) from a box to the letter's ink, if within reach."""
    best = None
    x0, y0, x1, y1 = box
    yy = y0 - reach
    while yy <= y1 + reach:
        xx = x0 - reach
        while xx <= x1 + reach:
            if hit(xx, yy):
                dx = max(x0 - xx, 0, xx - x1)
                dy = max(y0 - yy, 0, yy - y1)
                d = math.hypot(dx, dy)
                best = d if best is None else min(best, d)
            xx += step
        yy += step
    return best


def check_page(ch, strokes, letter_ink, letter_hit, cap, pic_ink, caption, rain, cloud):
    """Every layout collision the review has turned up, as numbers."""
    issues = []
    for s in strokes:
        bx, by, r = s["badge"]
        if badge_conflicts(bx, by, r, s, strokes, cap):
            issues.append(f"badge {s['n']} hides part of another stroke or badge")
        if by + r > CUE_Y - 4:
            issues.append(f"badge {s['n']} rises into the instructions")
    # every arrowhead must point along the end of its own stroke
    for s in strokes:
        if not s["arrow"]:
            continue          # a dot has no arrow
        (tx, ty), (bx0, by0) = s["pts"][-1], point_back(s["pts"], 4.0)
        tip, b1, b2 = s["arrow"]
        base = ((b1[0] + b2[0]) / 2, (b1[1] + b2[1]) / 2)
        want = math.atan2(ty - by0, tx - bx0)
        got = math.atan2(tip[1] - base[1], tip[0] - base[0])
        off = abs((got - want + math.pi) % (2 * math.pi) - math.pi)
        if off > math.radians(20):
            issues.append(f"stroke {s['n']}'s arrow points {math.degrees(off):.0f} degrees off its stroke")
    # arrowheads that land on top of each other
    for i, s in enumerate(strokes):
        for t in strokes[i + 1:]:
            if not s["arrow"] or not t["arrow"]:
                continue
            if math.hypot(s["arrow"][0][0] - t["arrow"][0][0],
                          s["arrow"][0][1] - t["arrow"][0][1]) < 6:
                issues.append(f"arrows {s['n']} and {t['n']} end on the same spot")
    if letter_ink[3] > CUE_Y - 6:
        issues.append("letter reaches the instruction line")
    for name, box in (("picture", pic_ink), ("rainbow", rain), ("cloud", cloud), ("caption", caption)):
        gap = ink_gap(letter_hit, box)
        if gap is not None and gap < 6:
            issues.append(f"letter within {gap:.0f}pt of the {name}")
    if pic_ink[1] - caption[3] < 6:
        issues.append(f"picture only {pic_ink[1] - caption[3]:.1f}pt above its caption")
    if overlap(pic_ink, rain, 6) or overlap(pic_ink, cloud, 6):
        issues.append("picture crowds the rainbow")
    foot_l = FOOTER_Y + 10
    number_box = (W / 2 - 22, FOOTER_Y - 3, W / 2 + 22, foot_l)
    for name, box in (("rainbow", rain), ("cloud", cloud), ("caption", caption), ("picture", pic_ink)):
        if overlap(box, number_box, pad=8):
            issues.append(f"page number crowded by the {name}")
    for name, box in (("rainbow", rain), ("cloud", cloud), ("picture", pic_ink), ("letter", letter_ink)):
        if box[0] < 18 or box[2] > W - 18 or box[1] < 14:
            issues.append(f"{name} runs into the printer margin")
    return issues


def draw_page(c, ch, title, page_no, total):
    """One page, with every word in the letter's language (PAGE_TEXT).
    `title` replaces the heading only when given (--title)."""
    words = page_text(ch)
    draw_header(c, title or words["title"], words["name"])
    lines = [words["trace"], f"{words['say']}  {LETTERS[ch][2]}"]
    centered(c, lines[0], "Poppins", 13, INSTRUCTION_Y, SOFT)
    centered(c, lines[1], "Poppins", 13, CUE_Y, SOFT)
    too_wide = [s for s in lines if pdfmetrics.stringWidth(s, "Poppins", 13) > W - 2 * MARGIN]

    x, y, size, letter_ink = draw_letter(c, ch)
    strokes = draw_strokes(c, ch, x, y, size)
    rain = draw_rainbow(c)
    foot = RAIN_INNER + RAIN_BANDS * RAIN_BAND / 2
    cloud = draw_cloud(c, RAIN_CX - foot, RAIN_CY - 12, CLOUD_W)
    pic_ink, caption = draw_picture(c, ch)

    label = words["page"].format(n=page_no, total=total)
    text_at(c, (W - pdfmetrics.stringWidth(label, "Poppins", 12)) / 2, FOOTER_Y,
            label, "Poppins", 12, SOFT)
    hit = letter_hit_test(ch, x, y, size)
    issues = check_page(ch, strokes, letter_ink, hit, CAP_RATIO * size, pic_ink,
                        caption, rain, cloud)
    issues += [f"instruction line too wide for the page: {s!r}" for s in too_wide]
    if caption[0] < PIC_CX - 110 or caption[2] > W - 18:
        issues.append("caption too wide for its spot")
    return size, issues


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--letters", default="ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    ap.add_argument("--out", default="Rainbow Writing.pdf")
    ap.add_argument("--title", default=None,
                    help="heading for every page (default: 'Rainbow writing' in each page's language)")
    args = ap.parse_args()

    # A lowercase letter with its own entry stays lowercase (a, b, c...);
    # any other is read as its capital (ñ asks for Ñ).
    asked = [ch if ch in LETTERS else ch.upper() for ch in args.letters]
    letters = [ch for ch in asked if ch in LETTERS]
    skipped = sorted(set(ch for ch in asked if ch not in LETTERS and not ch.isspace()))
    if skipped:
        print(f"  skipped (not in the LETTERS table): {' '.join(skipped)}")
    c = canvas.Canvas(args.out, pagesize=LETTER)
    c.setTitle(args.title or PAGE_TEXT["en"]["title"])
    problems = 0
    for i, ch in enumerate(letters, start=1):
        size, issues = draw_page(c, ch, args.title, i, len(letters))
        c.showPage()
        status = "ok" if not issues else "; ".join(issues)
        problems += len(issues)
        height = (f"x-height {XH_RATIO * size / 72:.2f} in" if ch.islower()
                  else f"cap {CAP_RATIO * size / 72:.2f} in")
        print(f"  {ch}: {height}  {status}")
    c.save()
    print(f"wrote {args.out}  ({problems} layout issue{'s' if problems != 1 else ''})")


if __name__ == "__main__":
    main()
