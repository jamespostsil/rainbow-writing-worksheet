# Pictures drawn for the pages

Most pictures come from the OpenMoji font (see `../fonts/README.md`). These are the exceptions:

- **sweet-potato-canva.png:** a sweet potato (ñame) for the Spanish Ñ page. It was made with Canva's AI image tool on a nonprofit Canva account, from the prompt "A whole sweet potato. Simple black outline coloring-page drawing, white background, no color, no scenery." OpenMoji's own sweet potato looked like a leaf.
- **sweet-potato.json:** the same drawing as vector lines, made by `scripts/trace_picture.py`. The page draws from this file, so the outline matches the OpenMoji pictures' line weight.

To trace a new picture:

```
python scripts/trace_picture.py assets/pictures/NAME.png assets/pictures/NAME.json
```

Then add a small drawing function in `make_rainbow.py` that calls `draw_traced(c, cx, cy, "NAME")`, add it to `DRAWINGS`, and use its name as the picture in the `LETTERS` table.

**What makes a good source drawing:** black lines on white, one object, no shading, and lines that don't touch the edge of the image.

The xylophone (X) is drawn directly in code (`draw_xylophone`).
