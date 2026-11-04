---
name: rainbow-writing-worksheet
description: >
  Generate printable "rainbow writing" alphabet worksheets for young children:
  one giant hollow capital letter per 8.5x11 page with numbered dotted
  stroke-order guides, a rainbow the child colors one band of after each
  tracing pass, and a friendly line-art picture of something starting with
  that letter. Use when someone asks for rainbow writing, letter tracing
  pages, alphabet tracing, or letter-formation practice sheets for
  preschool/kindergarten, for the whole alphabet or a few letters.
---

# Rainbow writing worksheets

Each page: a giant hollow capital, numbered dotted strokes showing how to
form it (in standard manuscript order), a "Say it:" cue the child speaks
while writing, a six-band rainbow with a cloud to color one band per pass,
and a picture + "A is for Apple" caption. Name line and "N of M" page
numbers.

## Run it

```bash
python <SKILL_DIR>/scripts/make_rainbow.py --letters ABCDE --out rainbow-writing.pdf
```

`--letters` defaults to A-Z. `--title` replaces the heading on every page
(by default it is "Rainbow writing" in each page's language).

Needs `reportlab fonttools numpy pillow opencv-python scikit-image`
(and `pypdfium2` to render pages for review). All fonts are bundled.

The script prints one line per page. Anything but `ok` is a layout problem —
fix it before handing the file over.

## Review before handing it over

The generator checks every page for the problems found so far; that is a
floor, not the review. Do both:

1. `python <SKILL_DIR>/scripts/verify.py <letters>`: for every stroke, how
   far the dotted path sits from the middle of the stroke, whether each END
   sits on the middle of the cut it ends on (not in a corner), any point
   outside the letter, and any place the path doubles back. Run it from a
   scratch folder: it writes overlay sheets (`verify_sheet_*.png`). Every
   flag is either listed with its reason in `scripts/verify_expected.txt` or
   printed as `NEW` (and the script exits 1). **It passes only with 0 NEW.**
   Never add a flag to that list because a similar letter has one: Ž's
   caron "looked like V's tip" and was a real bug. After changing shared
   code, run it on every letter, A-Z and the marked ones.
   When the review finds a bug the checker missed, add a check that fails
   on the old code before fixing it (ADDING-LETTERS.md, Step 3).
2. Render every page and look at each one **as if you'd never seen it** —
   zoomed in on anything that looks slightly off. If a render looks a bit
   wrong, it is wrong: find out why rather than explaining it away.
3. Render at 3x and crop **every mark and every stroke end**. Ask of each
   end "is this the middle of the cut?" A corner ending looks fine at page
   size; the tilde bug only showed zoomed in.

Every page is in its letter's language (`PAGE_TEXT` in make_rainbow.py:
title, Name, instructions, Say it, caption, page number). The non-English
phrases are first drafts: say so when handing pages over.

## What the pages must get right

- **Nothing scary for young kids** — no jack-o-lanterns, zipper-mouth faces,
  skeletons, X-rays. X is a hand-drawn xylophone for that reason.
- **Pictures are plain single-line drawings** (OpenMoji black). Never stroke
  a filled emoji's outline — it doubles every line.
- **Dotted guides ride the middle of each stroke**, measured off the real
  glyph (`scripts/letterform.py`), never modelled as ellipses. Where two
  strokes run along the same bar (B's waist) each gets its own lane.
- **Stroke order is standard manuscript**, matching the "Say it" cue.
- **Strokes that end in a flat cut (S, G, J) start/finish on the middle of
  the cut, square to it.** Near a flat end the ridge forks toward the
  corners, so the traced path drifts; the last stretch is rebuilt from the
  centre of the ink on each row back from the cut (`ridge_route(...,
  head/tail="face-down"/"face-up")`).
- **Corners stay corners.** G goes up its right side and turns *sharply*
  along the bar; don't let smoothing round it off.
- **Arrowheads aim along the last ~10pt of their stroke, measured by
  length.** Aiming "a few points back" by count breaks on M, V, W, whose
  zigzags are stored as only 3-5 corners — the arrows swung sideways.
- **Badges have comfortable room**: each slides along its own stroke until
  clear of other badges, other strokes' dotted lines, and arrowheads. On a
  closed loop (O, Q) the badge sits on the start point itself.
- **Text is normal weight.** The hollow letter uses PDF text render mode 1;
  it is reset inside that same text object, or every later string on the
  page comes out outlined.
- **Letters share one cap height**, except Q (tail below the baseline), W
  (too wide), and letters with marks (Ñ, Ç, Ü, Å, Ž, É), which are shrunk only as far
  as they must be.
- **Marks are their own strokes, after the base letter**: Ñ's tilde left to
  right, Ç's hook from where it leaves the C, Ü's dots as numbered taps with
  no arrow ("dot" strokes).

## Changing things

- Keywords, pictures, and cues live in the `LETTERS` table at the top of
  `make_rainbow.py`. A picture is an OpenMoji codepoint, or the name of a
  drawing function (like `xylophone`). Check a new picture renders as clean
  line art and is friendly before using it; keep short-vowel words for
  vowels (Apple, Egg, Umbrella).
- Stroke paths live in `strokes_for()` in `letterform.py`, one branch per
  letter. After changing one, run `verify.py` for that letter and look at the
  overlay.
- **To add a letter, follow `ADDING-LETTERS.md`** (in this folder): the
  toolkit, letters with marks, how to read the checker, and the traps.
- Besides A-Z, the table has Ñ Ç Ü Å Ø Ž Ł É. They are not in the default
  alphabet: pass them in `--letters`. Letters not in the table are skipped,
  and the script prints which.
- Poppins lacks many African letters (Ŋ, Ɛ, Ɔ, Ɓ, Ɗ...). `Glyph()` refuses a
  letter the font doesn't have; supporting one means changing the font,
  which means re-checking every letter (see ADDING-LETTERS.md).
- On Windows set `PYTHONIOENCODING=utf-8`, or printing Ñ crashes the script.
- Lowercase: a b c d e i l o t n are built (`--letters abc` keeps them
  lowercase), with top/dashed-middle/baseline guide lines and one shared
  size. The rest are not built yet; see ADDING-LETTERS.md.
