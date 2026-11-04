# Adding a letter

This guide shows how to add a new letter to the worksheets. Ñ, Ç and Ü were added by following these steps, so they are worked examples. They also cover the three kinds of marks: a mark above the letter, a mark below it, and dots.

Read [SKILL.md](SKILL.md) first. Its "What the pages must get right" list is the standard every new letter must meet.

## The short version

1. **Check that the font has the letter.** See [Step 1](#step-1-check-the-font-has-the-letter).
2. **Write the strokes** in `strokes_for()` in [scripts/letterform.py](scripts/letterform.py).
3. **Run the stroke checker** and look at its overlay picture:
   ```
   python scripts/verify.py Ñ
   ```
4. **Add a row to the `LETTERS` table** in [scripts/make_rainbow.py](scripts/make_rainbow.py): the keyword, the picture, and the "Say it" cue.
5. **Make the page** and make sure it says `ok`:
   ```
   python scripts/make_rainbow.py --letters Ñ --out test.pdf
   ```
6. **Render the page and look at it closely.** Zoom in on anything that looks slightly wrong. If it looks wrong, it is wrong.
7. **Run the whole alphabet again** and check that every page still says `ok`. Shared code changes can move other letters.

**On Windows:** run `set PYTHONIOENCODING=utf-8` first (in PowerShell: `$env:PYTHONIOENCODING="utf-8"`). If you don't, printing a letter like Ñ crashes the script.

## Step 1: check the font has the letter

The letters are measured from **Poppins Bold**. Poppins covers Western European letters (Ñ, Ç, Ü, É, Å...), but **not** many African letters, such as Ŋ, Ɛ, Ɔ, Ɓ, Ɗ, Ƙ, Ƴ, Ẹ and Ọ.

```
python -c "import sys; sys.path.insert(0,'scripts'); from letterform import in_font; print(in_font('Ŋ'))"
```

**Why this matters:** a missing letter still draws, as the font's empty "missing letter" box. The measuring code used to measure that box as if it were the letter. Now `Glyph()` stops with an error instead:

```
ValueError: 'Ŋ' (U+014A) is not in Poppins-Bold.ttf
```

If the letter is missing, see [Using another font](#using-another-font).

## Step 2: write the strokes

### How a stroke is described

Each letter is a list of strokes, in the order the child writes them. Each stroke is one of these:

| Kind | Data | Used for |
|---|---|---|
| `"line"` | `(x0, y0, x1, y1)` | Straight strokes (A, E, K...) |
| `"arc"` | `(cx, cy, rx, ry, start_deg, end_deg)` | Round strokes that are close to an ellipse (C, O, Q's ring) |
| `"poly"` | `[(x, y), ...]` | Any traced path (B's bowls, G, J, S, U, the tilde, the cedilla) |
| `"dot"` | `(x, y)` | A dot the child makes: a numbered badge with no line and no arrow (Ü) |

**Coordinates** are fractions of the character's **ink box**:
- **x:** 0 is the left edge of the ink and 1 is the right edge.
- **y:** 0 is the bottom of the ink and 1 is the top.
- **The box includes the marks.** Ñ's box includes its tilde, so it is taller than N's box.

### How the measuring works

`Glyph(ch)` draws the letter at 900 px and keeps a black-and-white **mask** of its ink. Every helper below measures that mask. **Never guess a position.** Measure it from the ink.

**Pixel space vs. normalized space:**
- Most helpers work in **pixels**, where y grows **downward**.
- Turn pixel points into stroke coordinates with `g.norm(points)` (for a list) or `g.seg(p, q)` (for a line).

**Two kinds of "how far down":**
- `g.run_mid(t, i)` and `g.row_runs(t)` take `t` as a fraction **from the top** of the ink box.
- Stroke coordinates count **from the bottom**.

### The toolkit

Find the letter that is most like yours, and copy its branch in `strokes_for()`.

| Helper | What it gives you | Copy from |
|---|---|---|
| `g.stem(i, (t0, t1))` | The centre line of a vertical stem, run to the ink's top and bottom edges. Pick rows where the stem stands alone. | H, I, L, N |
| `g.run_mid(t, i)` | The middle of the i-th piece of ink on one row. `i=-1` is the last piece. | almost all letters |
| `g.col_mid(x, i)` | The middle of the i-th piece of ink in one column. Good for horizontal bars. | E, F, L, T, Z |
| `g.line(p, q)` and `g.meet(l1, l2)` | A line through two centre points, and where two lines cross. | K, M, V, W, Y, Z |
| `g.to_edge(p, direction, inset)` | Walk from a point to the edge of the ink. | most straight strokes |
| `g.pull_inside(p, direction, margin)` | Move a corner back inside the ink (pointed tips). | M, V, W |
| `g.ridge_route(waypoints, head, tail, snap)` | A curved path along the middle of the ink, through waypoints. | G, J, S, U, Ñ, Ç |
| `g.medial_bowl(i, stem_x)` | The centre line of a bowl attached to a stem. It handles B's shared waist with two lanes. | B, P, R |
| `g.ink_arc_span(...)` | Where an open ring really starts and ends. | C |
| `g.marks(base)` and `rebase(...)` | The parts a character has that its base letter does not, and the base letter's strokes moved into the new box. | Ñ, Ç, Ü |

**How a stroke ends** (`head`/`tail` in `ridge_route`):
- **`"edge"`:** runs straight out to the edge of the ink.
- **`"face-down"` / `"face-up"`:** for a stroke that ends in a flat, level cut (S, G, J). The path lands on the middle of the cut, square to it.
- **`"none"`:** you finish the stroke yourself. G uses this for its sharp corner.

### Letters with marks (Ñ, Ç, Ü)

**Don't measure the base letter again.** Add the character to `COMPOSED` in `letterform.py`:

```python
COMPOSED = {"Ñ": "N", "Ç": "C", "Ü": "U"}
```

The code then:
1. **Takes the base letter's strokes** (N) and moves them into the new character's box with `rebase()`. Both letters are drawn at the same origin, so their pixels line up.
2. **Finds the marks** with `g.marks(base)`: the ink that the base letter does not have, sorted left to right. Small specks are dropped. They appear where the font draws the base a pixel differently: Ç's C is about 1 px different from a plain C.
3. **Adds a stroke for each mark.** This is the only part you write:
   - **Tilde (Ñ):** `ridge_route` from 12% to 88% of the way across the tilde, left to right.
   - **Cedilla (Ç):** it hangs from the C by a short neck. The stroke starts where the neck leaves the C, goes down and round the hook, and ends on its flat end. It uses `head="none"` and adds the start point by hand.
   - **Dots (Ü):** one `"dot"` stroke per dot, at its centre, left then right.

**Use a small `snap` for marks.** `ridge_route` first moves each waypoint to the thickest ink nearby. The default search radius is 5% of the cap height. Near the cedilla, the thickest ink nearby is the C itself, so the waypoint jumped into the C. The tilde and cedilla use `snap=0.01`.

**The page sizes these letters for you.** A character that goes below the baseline or above the cap height is made smaller until the whole thing fits (Q, Ñ, Ç, Ü). Other letters keep the full 6.19 inch cap height.

## Step 3: read the stroke checker

`verify.py` checks each stroke against the real letter. It prints one row per stroke and writes `verify_sheet_*.png` overlays into the current folder. Run it from a scratch folder.

| Column | Meaning | Flagged when |
|---|---|---|
| outside | Points of the path that fall outside the ink | more than 0 |
| lopsided | How far the path sits from the middle of the stroke. 0% is centred. | more than 25% |
| worst at | Where the worst lopsided point is (x, y in the ink box) | |
| doubles back | Places where the path turns back on itself, which bunches the dots | more than 0 |

**Expected flags** (these are fine, but a new flag anywhere else is not):
- **B 2-3:** the waist lanes are off-centre on purpose.
- **M, V, W:** their sharp turns count as "doubling back", and the tips read as lopsided.
- **M 1, 3 and N 1, 3 (and Ñ 1, 3):** about 25% where the stems meet the diagonals.
- **Q 1-2, R 2:** junctions, where Q's tail meets its ring and R's leg meets its bowl.

**Junctions:** the checker skips the first and last 10% of each stroke and any spot where the ink is more than 1.35 times its usual width. So a flag right at a junction is usually the other stroke, not a bad path. **Check the overlay to be sure.**

**The checker looks sideways a fixed distance** (35% of the cap height) to find the stroke's edges. At first that distance was 35% of the ink box's height. Ñ's tilde made its box taller, so the checker looked farther, found the far wall of the N, and reported Ñ's diagonal as 55% off-centre. The diagonal was actually identical to N's. **For any "how close is near" distance, use `g.cap_px`, never `g.h`.**

## Step 4: add the keyword, picture and cue

Add a row to the `LETTERS` table in `make_rainbow.py`:

```python
"Ñ": ("ñame", 0x1F360, "down, slant down, up, then the wave"),
```

- **Keyword:** the caption reads "Ñ is for ñame". Use a word in a language that has the letter. Keep short-vowel words for vowels.
- **Picture:** an OpenMoji code point, or the name of a drawing function in `make_rainbow.py` (like `xylophone`).
- **"Say it" cue:** one short phrase per stroke, in the same order as the strokes. Call a mark by what it is: "then the wave", "then the hook", "dot, dot".

**Checking a picture:**
1. **Check it's in the font:**
   ```
   python -c "from fontTools.ttLib import TTFont; print(0x1F360 in TTFont('assets/fonts/OpenMoji-black-glyf.ttf').getBestCmap())"
   ```
2. **Look at it at the size it prints.** Several pictures can look right in a list and still read as something else on the page. The teacup read as a bowl, so Ç uses the cup and saucer (`0x2615`) instead.
3. **Nothing scary,** and only plain line art.
4. **If no picture fits,** draw one in code the way `draw_xylophone` does, rather than using a picture that's nearly right.

**Open item:** Ñ's sweet potato (for ñame, yam) looks more like a leaf or seed pod than a yam. OpenMoji has no picture for ñame or ñandú (rhea). A hand-drawn ñandú would be better.

**Letters not in the table are skipped,** and the script now says so:

```
  skipped (not in the LETTERS table): 7 Ŋ
```

`--letters` makes every letter a capital, so `ñ` asks for `Ñ`. The default is still A to Z. Ask for other letters by name: `--letters "ABCÑ"`.

## Step 5: page checks

Each page line says `ok` or lists what is wrong:

| Message | What to do |
|---|---|
| badge N hides part of another stroke or badge | Move the stroke's start, or check that two strokes don't start on the same spot by mistake. Badges already slide along their own stroke to find room. |
| badge N rises into the instructions | The letter is too tall. Check that the sizing rule in `draw_letter` sees the mark. |
| stroke N's arrow points ... degrees off its stroke | The stroke's last 10 pt bends sharply. Smooth the end, or end the stroke a little earlier. |
| arrows N and M end on the same spot | Stop one stroke a little short. See Y, where two arms meet. |
| letter reaches the instruction line | The sizing rule missed a mark above the cap height. |
| letter within N pt of the picture / rainbow / cloud / caption | The letter is too wide or too low. |
| picture only N pt above its caption / picture crowds the rainbow | The picture is too big. `PIC_MAX_H` and `PIC_MAX_W` limit it. |
| ... runs into the printer margin | Something is too close to the edge of the paper. |

**`ok` is the minimum, not the review.** Render the page and look at it as if you'd never seen it.

## Traps we hit

- **Missing letters draw as an empty box.** Ŋ, Ɛ and Ɔ measured as the same size because each one was the font's "missing letter" box. `Glyph()` now refuses them.
- **The ink box is not the cap height.** A mark makes the box taller without making the strokes thicker. Use `g.cap_px` for distances.
- **Waypoints jump to thick ink.** Use a small `snap` near a big stroke.
- **Flat stroke ends pull the path to a corner.** Near a flat cut, the middle of the ink splits toward the cut's two corners. Use `"face-down"`/`"face-up"`.
- **Aim arrows by length, not by point count.** M, V and W are stored as only 3 to 5 corners. "Three points back" is the far side of the letter.
- **Two strokes on one bar need their own lanes** (B's waist), or the dots land on top of each other.
- **Keep corners sharp.** G turns sharply into its bar, so don't let smoothing round it off.
- **Outlined text spreads.** The hollow letter uses PDF text mode 1 (outline). It must be reset inside the same text object, or every later line of text on the page comes out outlined.
- **A letter not in the table used to be skipped without a word.** Now the script prints it.

## Using another font

To support letters like Ŋ, Ɛ and Ɔ, the skill needs a font that has them. For example, **Andika** (by SIL) is designed for beginning readers, has these letters, and has school-style a and g, which lowercase would need too. Check its coverage and licence before you use it.

**Changing the font is a big job:**
- **`FONT_PATH`** in `letterform.py`, and `LETTER_TTF` in `make_rainbow.py`.
- **`CAP_RATIO`** in `make_rainbow.py` (0.702 for Poppins): the cap height as a fraction of the font's em.
- **Every letter's fractions.** Numbers like `g.stem(0, (0.75, 0.9))` or `g.run_mid(0.44, 1)` say "measure on this row" and were chosen for Poppins's shapes. Run `verify.py` on every letter and look at every overlay.
- **The other OpenMoji, Poppins text and layout settings** can stay the same.

## Not built yet

- **Lowercase.** It needs its own stroke branches, a school-style font, and sizing by x-height with room for ascenders and descenders.
- **Other languages for the page text.** "Rainbow writing" can be changed with `--title`. The instructions, the "Say it" cues and "is for" in the caption are still English.
