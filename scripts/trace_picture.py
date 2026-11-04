"""Turn a black-and-white line drawing (PNG) into vector lines for a page
picture, so it prints in the same line style as the OpenMoji pictures.

    python scripts/trace_picture.py assets/pictures/sweet-potato-cut-canva.png assets/pictures/sweet-potato-cut.json

Pasting the picture in as an image doesn't work: at its printed size (about
124 pt wide) the drawing's thin lines nearly disappear. Instead:

- outlines: the outer edge of each object, as a closed line. They are
  drawn at the same weight as the OpenMoji pictures.
- marks: every line inside the shape, thinned to its centre line. They are
  drawn thinner.

Coordinates are fractions of the shape's width (x) and height (y, upward).
"""

import json
import sys

import cv2
import numpy as np
from skimage.morphology import skeletonize


def order_path(pixels):
    """Order a thin (skeleton) piece's pixels into one line, end to end."""
    pts = set(map(tuple, pixels))

    def neighbours(p):
        return [(p[0] + dy, p[1] + dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                if (dy or dx) and (p[0] + dy, p[1] + dx) in pts]

    ends = [p for p in pts if len(neighbours(p)) == 1]
    start = ends[0] if ends else next(iter(pts))
    path, seen, cur = [start], {start}, start
    while True:
        nxt = [q for q in neighbours(cur) if q not in seen]
        if not nxt:
            break
        cur = nxt[0]
        seen.add(cur)
        path.append(cur)
    return path


def trace(png):
    grey = cv2.imread(png, cv2.IMREAD_GRAYSCALE)
    ink = (grey < 128).astype(np.uint8)

    # the whole shape: everything not reachable from the outside
    flood = ink.copy() * 255
    mask = np.zeros((flood.shape[0] + 2, flood.shape[1] + 2), np.uint8)
    cv2.floodFill(flood, mask, (0, 0), 128)
    shape = (flood != 128).astype(np.uint8)
    cs, _ = cv2.findContours(shape, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    # every separate object (a whole sweet potato AND its cut half), not
    # just the biggest one; tiny bits are specks
    biggest = max(cv2.contourArea(k) for k in cs)
    outers = [k for k in cs if cv2.contourArea(k) > 0.05 * biggest]
    x, y, w, h = cv2.boundingRect(np.vstack(outers))
    outlines = [cv2.approxPolyDP(k, 0.8, True)[:, 0, :] for k in outers]

    # the marks: centre lines of the ink, minus the outlines themselves
    near_edge = np.zeros_like(ink)
    cv2.drawContours(near_edge, outers, -1, 1, thickness=9)
    skel = skeletonize(ink.astype(bool)) & ~near_edge.astype(bool)
    n, labels = cv2.connectedComponents(skel.astype(np.uint8), connectivity=8)
    marks = []
    for k in range(1, n):
        pix = np.argwhere(labels == k)
        if len(pix) < 6:
            continue                      # specks
        path = order_path(pix)
        line = np.array([(c, r) for r, c in path], np.int32).reshape(-1, 1, 2)
        line = cv2.approxPolyDP(line, 0.8, False)[:, 0, :]
        marks.append(line)

    def norm(points):
        return [[round((px - x) / w, 4), round(1 - (py - y) / h, 4)] for px, py in points]

    return {"aspect": round(w / h, 4), "outlines": [norm(o) for o in outlines],
            "marks": [norm(m) for m in marks]}


if __name__ == "__main__":
    data = trace(sys.argv[1])
    with open(sys.argv[2], "w", encoding="utf-8") as f:
        json.dump(data, f)
    print(f"{len(data['outlines'])} outlines, {len(data['marks'])} marks, aspect {data['aspect']}")
