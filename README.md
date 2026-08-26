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
- A font that draws a second, flatter acute for capitals usually reaches for it only inside
  its own precomposed Á, leaving a typed mark to sit as high above a capital as above a
  lowercase letter. `case_acute_after_capitals` adds the `ccmp` rule that swaps it in after
  any capital, which every shaper runs.

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

## Spectral

Spectral needs both halves of the above. It anchors every lowercase vowel but ё and leaves
Ё Ы Э Ю Я out, and it draws `acutecomb.case` for the capitals it does anchor without ever
selecting it, so А́ came out 45 units higher than the font's own Á. With the anchors added
and the `ccmp` rule in, Cyrillic capitals whose Latin twin has a precomposed form — А О Е —
carry the mark at exactly the offset the twin's composite uses. Spectral's own ю anchor is
the one exception the build overrides: it sits halfway across the letter, on the crossbar,
so `recenter_acute` moves it and Ю onto the bowl.

Version 2.005 also swapped Spectral's comma and its comma-shaped quotes for wedges
([issue 28](https://github.com/productiontype/Spectral/issues/28)). Six glyphs carry the
shape — , ; ‘ ’ and the two combining comma accents — and “ ” ‚ „ ʻ ʼ, the comma-accent
letters and the small-cap quotes are composites of those. The 2.001 outlines drop straight
back in on advance widths that never changed. `build_spectral_fix.py` fetches both versions
from the Google Fonts repository and swaps the six, dropping their hinting, which was
written against another font's control values.

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

`build_literata_uniform.py` is a taste call made deliberately, and the several wrong
turns behind it are the interesting part. Every attempt that scored a pair on its own
lost, because a pair on its own is not what anyone looks at. Blurred darkness between
two letters ranks a visibly clumping font as the best of the bunch. So does the amount
of light. Fitting the blur radius is worse than useless: asking which radius disturbs
the designer's own kerning least rewards a model that proposes nothing, and asking
which makes the Latin read most uniformly rewards blurring the page to mush.

What works is to score the page. The document's own words are set with the font, the
line is blurred the way an eye blurs a page, and the light between each pair is
measured in context with its neighbours bleeding in. The reading that matters is how
*wide* the light runs, not how dark it goes — clumping is variation in width — and
that is the one reading of three that ranks a shelf of already-judged fonts the way a
reader does. The score is the spread of those widths, and the kerns are walked down
until it stops falling. The walk overshoots at full stride, since neighbouring gaps
pull on each other through the blur, so it is damped and the best round kept.

On the test document the spread falls from 0.24 to 0.14 with the median pair unmoved,
and the result beats Literata on all three readings at once. Only pairs the corpus
contains are touched, so this is a font tuned to a text rather than a font in general.

One blind spot needed a rule rather than a better reading of the light. A round
letter meeting a recessed stem — ор, ар, ов — never lets the blurred line go light
between the two at all, so the optimiser reads the gap as tight and pulls the pair
further apart, which is exactly backwards. What ranks those pairs correctly is the
plainest measurement available: how close the two letters ever come. It makes a poor
thing to even out on its own, since pairs like ал are tight for a reason and it opens
them, but it makes a good set of limits. Nothing that already stands further apart
than most at its closest may be opened any further, nothing may stay further apart
than the loosest sixth, and nothing may come nearer than the font's own tightest fit.

Those limits overrule the objective on about a sixth of the pairs and the page score
pays for it: the spread of widths lands at 0.25, against 0.19 for a version with the
same three pairs corrected by hand. That is what not correcting by eye costs, and it
buys a font that needs no such table.

## Spacing from the outline

A designer separates two shapes until the white between them reads even, which makes a
sidebearing a function of the outline and so something that can be fitted. `spacing_model.py`
turns each side of each letter into features — the profile of the side, where it stands
back, how deep a corridor can be cut beside it before serifs poke through — and
`train_spacing.py` fits them on the fonts macOS ships. Families are held out whole, so a
sibling never flatters the score. It comes back within about 8 units at 1000 upem, against
25 for knowing nothing. Which fonts to learn from matters as much as the features: `care()`
reads a face's kerning coverage and how many of its sidebearings are multiples of ten, since
a font that kerns nothing and rounds everything has been defaulted rather than spaced.

The features read outlines, not codepoints, so a model trained on Latin can be asked about
another script. On Jost it reproduces the designer's own Latin to 7 units and then proposes
Cyrillic. Its verdict is mostly about д, which loses nearly all its sidebearing on both
sides: the splayed feet already reach out, and Jost pays for that reach twice.

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
| `build_literata_uniform.py` → Literata Uniform | Kerns the pairs a given document contains so the blurred page shows an even width of light between letters. Tuned to a text, and overrules the designer by design; see the section above. |
| `build_jost_variants.py` → Jost Uniform, Jost Spaced | Jost kerns its Cyrillic about as much as its Latin, so these test the two methods rather than repair neglect. Uniform evens out the kerning of one line; Spaced takes the sidebearings the Latin-trained model reads off the Cyrillic outlines. `jost-sample.typ` sets the line all three ways. |
| `build_literata_math.py` → Literata Math | Literata has no MATH table. Puts its letters, digits, Greek and Cyrillic into STIX Two Math, scaled to Literata's x-height. |

Every upstream here is under the SIL Open Font License, which the patched copies inherit.
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
