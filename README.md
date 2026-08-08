# fonts-fixing

Scripts that tweak fonts for Russian typesetting, plus the proof renderer used to check
the results by eye. Everything runs through `uv` and needs `typst` on PATH for proofs.

## Stress marks (U+0301)

Most fonts list only Latin glyphs in their GPOS mark-to-base coverage, so a combining
acute lands after the letter instead of over it. `acutefix.py` adds the missing anchors:
X from the glyph's bounding-box center, Y copied from the font's own Latin `O`/`o` anchors
so the result matches its precomposed `Á`/`á`. Two refinements matter in practice:

- A font that anchors one case and not the other (Inter has ю but not Ю) has already said
  where it wants the mark, so the missing one copies its counterpart's relative position.
- Otherwise Ю and ю take the center of the bowl's counter. The crossbar usually merges stem
  and bowl into a single contour, so the hole inside it is the only way to find the bowl.
- The acute is usually a steeply slanted parallelogram. Centering its bounding box makes it
  read as pointing at the left half of the letter, so the midpoint of its lower edge — the
  end it visually points with — is what gets centered instead.
- That last one is a default rather than a law: a font whose own anchors already sit where the
  acute reads right has said the same thing in its outline, and applying the tip rule on top
  shifts every added mark further right than the ones the designer placed. IBM Plex is such a
  font, so its build passes `point_at_center=False`.
- Ё and ё get the acute raised by however far their dots clear plain Е, so it stacks above the
  diaeresis instead of landing in it.

`recenter_acute` handles the opposite case, where an anchor exists but sits somewhere
Russian does not want it: Geist hangs the mark over ы's right stroke rather than the middle.

A font can also have every anchor it needs and still leave the acute unplaced. GPOS lists
its features per script, and a shaper that finds the script tag stops looking instead of
falling back to `DFLT` — so a `cyrl` entry that lists `kern` and not `mark` turns mark
positioning off for Russian while the lookups sit unused in the file. `enable_features`
copies the missing feature indices over; `inspect_acute.py` reports which scripts run
`mark`, because the anchor listing alone gives such a font a clean bill of health.

```
uv run inspect_acute.py fonts/RobotoFlexFix/RobotoFlexFix-Regular.ttf
uv run build_roboto_flex_fix.py
uv run proof.py "Roboto Flex Fix" some/older-version.ttf --size 100
```

`proof.py` takes installed family names and/or .ttf paths and renders them as rows of one
image, so before/after versions of the same font can sit side by side.

## Cyrillic spacing

Sidebearings are a poor guide to how a serif face is spaced. The stem stands well back
from the advance and only its serifs reach out, so two flat-sided letters keep a white
channel two or three times wider than their sidebearings suggest. `spacing.py` measures
the pair itself: a soft minimum of that channel over the scanlines where both letters
have ink, which tracks what the eye calls the gap.

How those gaps are boiled down to one number matters more than it looks. A power mean
with a low exponent counts the narrowest scanline for almost everything; with a high one
it becomes the plain average. Both look reasonable and they rank pairs differently, so
the exponent is not something to pick by eye. It can be fitted: a measure worth trusting
comes out the same for every pair a designer set correctly, so the exponent to use is the
one that varies least across the font's own Latin, kerning included. For Literata that is
about −0.5, and the flat-versus-round split that steeper exponents report is an artefact
of the aggregation rather than a property of the font.

Fitted that way, Literata's Cyrillic needs no respacing. Its О is the Latin O outline on
the same advance, н is the stems of n, Р is P; wherever a pair of letters is shared, the
two scripts measure identically — ОС and OC both come to 168 units, НН and HH to 248. The
difference is kerning coverage. The font kerns about a third of its Latin pairs and half
as many Cyrillic ones, so РО keeps a gap that PO does not.

`build_literata_fix.py` closes that gap and nothing else. Each Cyrillic side is matched to
the nearest Latin profile — н to i on both sides, Р to P and B, Ч to H and V — and a pair
inherits the kerning of the Latin pair behind it, but only where that tightens. Around 340
pairs move in the Regular, by a median of 10 units. Sides with no Latin analogue, ъ and ь
on the left and Ч to the right of its arm, fall outside the tolerance and keep what they
have.

What this does not do is close the gaps that a reader notices in a word like ОСЧР. Ч|Р
there is spaced exactly as H|B is, and о|в as o|i: it is the font's own rhythm, and the
Latin inherits it too. Tightening those is a taste call about the typeface, not a repair.

## Making every pair read alike

`build_literata_uniform.py` is that taste call, made deliberately. A reader does not
measure the gap between two letters, they see how light the page goes between them, so
each pair is rasterised, blurred the way an eye blurs a page at text size, and read at
its lightest column. The kern that brings every pair to one common reading is what ships.
Blurring commutes with summing down the columns, so this never needs a glyph in two
dimensions: a pair is the sum of two shifted column profiles.

The blur radius decides the answer rather than refining it. Wide, and two stems read as
tight because their ink bleeds across the gap; narrow, and the same pair reads as loose.
So it is swept rather than chosen, for the radius at which evening out the Latin disturbs
the designer's own Latin kerning least — about 0.15 of the x-height here. Latin is
adjusted alongside the Cyrillic, because evening out one script and not the other only
moves the unevenness somewhere else.

Even at its best radius the model still disagrees with the designer by some 16 units on
the average Latin pair, which is the honest measure of what is being overruled. ОС opens
by 40 and Ч|Р closes by 20, which is the point; nn closes by 40, which is the cost. At
text size the paragraphs are hard to tell apart, and in letterspaced capitals the
difference is obvious.

## Math in Literata

A math font is one file that carries a MATH table, every symbol, and the letters that
formulas set variables in. Literata has the letters and nothing else, so `unicode-math`
falls back to whatever math font the document names and formulas stop looking like the
text around them. `build_literata_math.py` keeps STIX Two Math — table, symbols, glyph
variants, stretchy assemblies — and redraws every letter and digit the two fonts share.

- STIX is drawn 7% smaller than Literata, so the donor is scaled to bring the x-heights
  together before anything is swapped in. `fontTools`' `scale_upem` covers most of that,
  but it only knows MATH's value records: the operator thresholds, connector overlaps and
  assembly part lengths are plain design units and need scaling by hand.
- Italic corrections are remeasured rather than inherited. Literata's italic leans much
  less than STIX's yet overshoots further on letters like `f`, so the donor's numbers
  describe shapes that are no longer there — as does its per-glyph script kerning, which
  is dropped for redrawn letters.
- Accent attachment points are recentred for the same reason: STIX places them right of
  centre by as much as its italics lean, which hangs a `\vec` arrow off the letter's side.
- STIX draws a second, sturdier set of letters for script size and reaches them through
  `ssty`. Literata says that with its optical size axis, so those variants come from an
  opsz 7 instance instead of a shrunken one.

## Fonts built here

Built copies live in `fonts/`; install with `cp -r fonts/GeistFix ~/Library/Fonts/`.

| Font | What the script changes |
| --- | --- |
| `build_geist_fix.py` → Geist Fix | Anchors U+0301 over every Cyrillic vowel, but registers `mark` only under `latn`, so none of it applied to Russian. Also moves ы off its right stroke. Patches all 18 static styles. |
| `build_inter_fix.py` → Inter Fix | Same unregistered `cyrl` script as Geist, plus Ю and я were never anchored. Rewrites the whole 36-face collection, Inter and Inter Display alike. |
| `build_ibm_plex_fix.py` → IBM Plex Sans Fix, IBM Plex Serif Fix | Ё, Э, Ю and Я are the vowels Plex never anchored; the rest of its Cyrillic already works. Both families, 16 styles each. |
| `build_roboto_flex_fix.py` → Roboto Flex Fix | No Cyrillic acute anchors, and typst ignores variable axes so every weight rendered as Regular. Emits static Regular/Italic/Bold/Bold Italic. |
| `build_sofia_sans_ru.py` → Sofia Sans Ru | Sofia Sans ships Bulgarian letterforms as the default; this variant makes the Russian ones default and keeps the Bulgarian set on ss01. Also adds acute anchors on Cyrillic vowels. |
| `pliant-kerning/batch.py` → Pliant | Almost no Cyrillic kerning. Also promotes the double-storey `a` to the default, which is a taste call rather than a fix. |
| `build_literata_fix.py` → Literata Fix | Cyrillic reuses the Latin outlines but not the Latin kerning, so РО keeps a gap PO does not. Matches each Cyrillic side to the Latin shape it is drawn from and carries the kerning over; both variable fonts and all four statics. |
| `build_literata_uniform.py` → Literata Uniform | Kerns every letter pair, Latin and Cyrillic, so that all of them read equally light under a blur fitted to the font's own Latin. Overrules the designer by design; see the section above. |
| `build_literata_math.py` → Literata Math | Literata has no MATH table. Puts its letters, digits, Greek and Cyrillic into STIX Two Math, scaled to Literata's x-height. |

All seven upstreams are under the SIL Open Font License, which the patched copies inherit.
`OFL.txt` ships next to the fonts that came with one; [Geist](https://github.com/vercel/geist-font),
[Inter](https://github.com/rsms/inter), [Roboto Flex](https://github.com/googlefonts/roboto-flex),
[Literata](https://github.com/googlefonts/literata) and [STIX Two](https://github.com/stipub/stixfonts)
keep theirs upstream.

The Sofia and Pliant scripts are kept as they were run rather than refactored onto
`acutefix.py` — those fonts are installed and correct, and the scripts carry work
(the Russian-default transform, the autokerning model) that is the point of keeping them.

## Why variable fonts get instanced

Typst 0.14 warns `variable fonts are not currently supported` and uses only the default
instance, so `chgksuite compose pdf --font 'Roboto Flex'` rendered every bold run at
weight 400. `typst fonts --variants` is the quick check: a usable family lists more than
one weight.
