# Adding a letter

This guide shows how to add a new letter to the worksheets. Eight letters with marks were added by following these steps, so they are worked examples:

| Letter | Mark | Page language |
|---|---|---|
| Ñ | tilde above | Spanish |
| Ç | cedilla below | Turkish |
| Ü | two dots | Turkish |
| Å | ring above | Swedish |
| Ø | slash through the letter | Danish |
| Ž | caron (a small v) above | Croatian |
| Ł | bar across the stem | Polish |
| É | acute accent | French |

Read [SKILL.md](SKILL.md) first. Its "What the pages must get right" list is the standard every new letter must meet.

## The short version

1. **Check that the font has the letter.** See [Step 1](#step-1-check-the-font-has-the-letter).
2. **Write the strokes** in `strokes_for()` in [scripts/letterform.py](scripts/letterform.py).
3. **Test the strokes** with all three tests in [Step 3](#step-3-test-the-strokes): the checker on every letter, a check that the checker can catch your kind of bug, and a 3x zoom of every stroke end and mark on the real page.
4. **Add a row to the `LETTERS` table** in [scripts/make_rainbow.py](scripts/make_rainbow.py): the keyword, the picture, the "Say it" cue, and the page's language.
5. **Make the page** and make sure it says `ok`:
   ```
   python scripts/make_rainbow.py --letters Ñ --out test.pdf
   ```
6. **Render the page and look at it closely.** Zoom in on anything that looks slightly wrong. If it looks wrong, it is wrong.
7. **Run every letter again,** both the checker and the pages. Shared code changes can move other letters.

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

### Letters with marks

**Don't measure the base letter again.** Add the character to `COMPOSED` in `letterform.py`:

```python
COMPOSED = {"Ñ": "N", "Ç": "C", "Ü": "U", "Å": "A", "Ø": "O", "Ž": "Z", "Ł": "L", "É": "E"}
```

The code then:
1. **Takes the base letter's strokes** (N) and moves them into the new character's box with `rebase()`. Both letters are drawn at the same origin. Some fonts shift the base sideways inside the new character (Poppins moves Ł's L 11 px right to make room for the bar), so `g.offset_to(base)` measures that shift first.
2. **Finds the marks** with `g.marks(base)`: the ink that the base letter does not have, sorted left to right. Small specks are dropped. They appear where the font draws the base a pixel differently: Ç's C is about 1 px different from a plain C.
3. **Adds a stroke for each mark.** This is the only part you write:

| Mark | How it is traced |
|---|---|
| Tilde (Ñ) | `ridge_route` left to right. Both ends are flat level cuts, so `head="face-down"` and `tail="face-up"` land on the middle of each. |
| Cedilla (Ç) | Starts where its neck leaves the C, goes down and round the hook, ends on its flat end. `head="none"` and the start point is added by hand. |
| Dots (Ü) | One `"dot"` stroke per dot, at its centre, left then right. |
| Ring (Å) | An `"arc"`, started at the top like O. |
| Caron (Ž) | Each arm's centre line from two **columns**, meeting at the point. |
| Slash (Ø) | A line through two centre points measured on **rows**, one in each end piece outside the ring. |
| Bar (Ł), accent (É) | A line through two centre points measured on **columns**. |

**Measure across a band so the cut meets both long edges** of the band:
- **Rows for a steep band** (Ø's slash).
- **Columns for a shallow band** (Ž's arms, Ł's bar, É's accent).
- **Never through an end cut.** Ž's arms end in upright cuts, so rows near the top hit the end instead of crossing the arm. Their "middles" were off, and both ends of the caron finished in its top corners.

**Use two centre points far apart,** not the mark's overall direction. Ø's ring cuts the slash into uneven pieces, which tilted the overall direction. Over the long slash, that small tilt walked the bottom end into a corner.

### Lowercase letters

Ten are built: **a b c d e i l o t n.** Their branches are in `_lowercase()` in `letterform.py`. Poppins's lowercase letters are already school-style (single-storey a and g, round letters made of a circle and a stick), so they use the same font.

- **Order:** ball-and-stick print order. Where that order goes back over a stroke already drawn (a's stick runs back down the right side of its circle), the stroke stops where it meets the earlier one, so no dotted line runs on top of another.
- **Bowls (a, b, d):** `_bowl_ring()` traces the middle of the ring and stops where it reaches the stem. Running the ends sideways to the stem's centre line, as B's bowls do, put a flat jog in a round bowl.
- **Size:** every lowercase letter is the same size, on the same baseline, so short letters (a, e, o) sit lower than tall ones (b, d, l), as they do on ruled paper. Room is kept above for i's dot and below for g, p and y.
- **Guide lines:** a top line, a dashed middle line and a baseline. They're drawn first, then the letter is filled white, so the lines don't cross the dotted path.
- **Asking for them:** lowercase letters with their own table entry stay lowercase (`--letters abc`). Any other lowercase letter is read as its capital (`ñ` asks for `Ñ`).

**Use a small `snap` for marks.** `ridge_route` first moves each waypoint to the thickest ink nearby. The default search radius is 5% of the cap height. Near the cedilla, the thickest ink nearby is the C itself, so the waypoint jumped into the C. The tilde and cedilla use `snap=0.01`.

**The page sizes these letters for you.** A character that goes below the baseline or above the cap height is made smaller until the whole thing fits (Q, Ñ, Ç, Ü, Å, Ž, É). Other letters keep the full 6.19 inch cap height.

## Step 3: test the strokes

Do all three tests. Each one has caught a bug the other two missed.

### Test 1: run the checker on every letter

```
python scripts/verify.py ABCDEFGHIJKLMNOPQRSTUVWXYZÑÇÜÅØŽŁÉ
```

Run it from a scratch folder: it writes overlay pictures (`verify_sheet_*.png`) into the current folder. **Run every letter, not just yours.** Shared code (`rebase`, `ridge_route`, the checker itself) can change other letters.

It prints one row per stroke:

| Column | Meaning | Flagged when |
|---|---|---|
| outside | Points of the path outside the ink | more than 0 |
| lopsided | How far the path sits from the middle of the stroke, along its length. 0% is centred. | more than 25% |
| worst at | Where the worst lopsided point is (x, y in the ink box) | |
| doubles back | Places where the path turns back on itself, which bunches the dots | more than 0 |
| start, end | How far each end sits from the middle of the cut it ends on. 0% is centred, 100% is a corner. `-` means the end is inside the ink (a junction). | more than 25% |

**Every flag is either expected or NEW.** Expected flags are listed in [scripts/verify_expected.txt](scripts/verify_expected.txt), each with a limit and a reason. The checker prints the reason next to the row. Anything not in the list, or worse than its limit, prints `<-- NEW`, and the checker exits with an error. **The test passes only with 0 NEW.**

**Why "start, end" exists:** the lopsided column skips the first and last 10% of each stroke, because junctions make the ends noisy. That's exactly where three bugs were: Ñ's tilde, Ž's caron and Ø's slash all ended in a corner, and the checker said nothing. The end check follows the letter's outline both ways from the end until it turns a corner. That stretch is the cut, and a centred end sits in its middle.

### Test 2: prove the checker can catch your kind of bug

When you find a bug the checker missed, **first add a check that fails on the old code, then fix the code.** To run the new checker on the old code:

```
mkdir old && cd old && mkdir scripts assets
git show HEAD:scripts/letterform.py > scripts/letterform.py
cp ../scripts/verify.py ../scripts/verify_expected.txt scripts/
cp -r ../assets/fonts assets/
python scripts/verify.py Ñ
```

The end check was proved this way: on v1.1's tilde it reports `85% 85% <-- NEW: start, end`. On the fixed tilde it reports 1% and 0%.

### Test 3: look at every end and every mark, zoomed in on the real page

Render the page at 3x and crop each mark and each stroke end. For every end, ask: **is this the middle of the cut?** For every stroke, ask: **do the dots ride the middle?** At full-page size, an end in a corner looks fine. The tilde bug was only visible zoomed in.

### Adding a flag to the expected list

Only after looking at it zoomed in. Give the reason, and a limit just above the measured value.

**Never because a similar letter has the same flag.** Ž's caron was flagged 77% lopsided, and that was written off as "like V's sharp tip". It was a real bug: the line ran along the top edge of the caron.

### Know what kind of end a stroke has before you change it

Zoom in and name the end first: a **flat level cut** (top or bottom), an **upright cut** at the side, a **round end**, or a **junction** with another stroke. Then choose the finish (`"face-up"`/`"face-down"`, `"edge"`, or stop at the other stroke).

e's tail is a lesson. It ends in a flat cut on top, facing up. It looked like the path stopped short, so it was pushed on to the side of the letter. That put the end in the outer corner, and the end check said 68%. The first version had been right (3%). Zoomed in, the flat top was obvious.

**A check that doesn't work is worse than none.** To catch "stopped short", a check that measured across the stroke just before each end was tried. It flagged 17 correct ends next to junctions (the top of E's stem crosses the top arm) and still missed nothing real, so it was removed.

### What the checker can't judge

- **Stroke order and direction,** and whether they match the "Say it" cue.
- **Lopsided numbers on curves that change width.** The checker measures straight out to each side of the path, so a curve that gets thicker or thinner can read lopsided when it isn't. Ñ's tilde reads 33% but the dots are centred at 3x zoom. Judge these by eye.
- **Pictures and translations.**

### Bugs in the checker itself

- **Use `g.cap_px`, never `g.h`, for "how far is near".** The checker looks sideways 35% of the cap height to find a stroke's edges. At first it used 35% of the ink box's height. Ñ's tilde made the box taller, so the checker found the far wall of the N and reported Ñ's diagonal as 55% off-centre. The diagonal was identical to N's.
- **Store per-letter data on the letter object,** not in a dict keyed by `id()`. Python reuses ids once an object is freed, and later letters were checked against an earlier letter's outline. H's straight stems scored 100%.

## Step 4: add the keyword, picture and cue

Add a row to the `LETTERS` table in `make_rainbow.py`:

```python
"Ñ": ("ñame", 0x1F360, "abajo, en diagonal, arriba, y la onda", "es"),
```

- **Keyword:** a word that starts with the letter, in a language that uses it. Keep short-vowel words for vowels.
- **Picture:** an OpenMoji code point, or the name of a drawing function in `make_rainbow.py` (like `xylophone`).
- **"Say it" cue:** one short phrase per stroke, in the same order as the strokes. Call a mark by what it is ("the wave", "the hook", "dot, dot").
- **Language:** a key in the `PAGE_TEXT` table. **Every word on the page is in this language:** the title, "Name", the instructions, "Say it", the caption ("Ñ de ñame") and the page number ("1 de 8"). Leave it out for English.

**Adding a language:** add an entry to `PAGE_TEXT` with all six phrases. The page checks flag an instruction line or caption that's too wide for the page. **Have a native speaker check the phrases.** The ones in the table now are first drafts.

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
- **Flat stroke ends pull the path to a corner.** Near a flat cut, the middle of the ink splits toward the cut's two corners. Use `"face-down"`/`"face-up"`. Check what kind of end a mark has before choosing: the tilde's ends are flat level cuts, so `"edge"` ran it into a corner.
- **A cut that hits an end cut has the wrong middle.** Cut across a band where it meets both long edges: rows for steep bands, columns for shallow ones.
- **The base letter can move inside a composed letter** (Ł's L). `offset_to()` measures it.
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

- **The other 16 lowercase letters.** The letters that hang below the baseline (g, j, p, q, y) are the first real test of the space kept for them. f, j and r end in hooks whose end cuts must be named before tracing (see Test 3).
- **Checked translations.** Seven languages have first-draft page text. A native speaker should check each before real use.
- **Checked stroke directions for marks.** Ł's bar goes left to right, and É's accent and Ø's slash go from the top end down. These follow the manuscript rules (start at the top, bars go left to right) but haven't been checked against how each country teaches handwriting.
