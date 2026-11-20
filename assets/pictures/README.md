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

**Making them with Claude and the Canva connector:** generate the first one, get it approved, then generate the rest with the approved one passed as a style reference. The generator only hands back a 200 px preview. For the full-size file, place the image on a 1600x1600 page in one working design, export that page as a PNG, and download it. Several pages can be filled in one edit.

**Check each one at full size, zoomed in, before using it.** The small preview hides every one of these, and all of them happened:

- **An arm that floats** off the body instead of joining it (the first 3).
- **An outline left open** where the face meets an inner line: under the curl of the 2 and the 3, and the 4's triangle hole. A child coloring it finds a gap.
- **A hole that reads as a shouting mouth** right under the smile (the first 6, and the 0 in 10). That's too close to scary for small children. The 6 and 9 now have no hole, with the face on the round part.
- **A shape that stops reading as its number** (the second 6 looked like a bean).

To fix one, generate again with the faulty drawing as the reference and a specific instruction: "the outline of the 3 has a gap on its left side, under the top curve; close it with one continuous black line". A vague "fix it" fixed only half the problem.
