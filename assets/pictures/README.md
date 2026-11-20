# Pictures drawn for the pages

Most pictures come from the OpenMoji font (see `../fonts/README.md`). These are the exceptions:

- **sweet-potato-cut-canva.png** (used on the Spanish Ñ page): a whole sweet potato (ñame) and one cut in half, made with Canva's AI image tool on a nonprofit Canva account, from the prompt "A whole sweet potato next to one cut in half. Simple black outline coloring-page drawing, white background, no color, no scenery." The cut half shows it's a vegetable. OpenMoji's own sweet potato looked like a leaf.
- **sweet-potato-cut.json:** the same drawing as vector lines, made by `scripts/trace_picture.py`. The page draws from this file, so the outlines match the OpenMoji pictures' line weight.

To trace a new picture:

```
python scripts/trace_picture.py assets/pictures/NAME.png assets/pictures/NAME.json
```

Then add a small drawing function in `make_rainbow.py` that calls `draw_traced(c, cx, cy, "NAME")`, add it to `DRAWINGS`, and use its name as the picture in the `LETTERS` table.

**What makes a good source drawing:** black lines on white, one object, no shading, and lines that don't touch the edge of the image.

The xylophone (X) is drawn directly in code (`draw_xylophone`).

## Number characters (numbers/)

`numbers/0.png` to `numbers/10.png`: one cartoon character per number, shown beside the things to count. Made with Canva's AI image tool on a nonprofit Canva account, from a prompt like:

> A cute cartoon number 3 character with a big happy face, big eyes, small arms and legs and sneakers, waving. Simple black outline coloring-page drawing, white background, no color, no scenery.

(For 10: "the numbers 1 and 0 as two cute friends holding hands".)

These are **pasted in as images**, not traced: tracing dropped their mouths and pupils. The page turns their black lines to the same grey as the other pictures. A number with no file still makes a page; its things to count fill the space.
