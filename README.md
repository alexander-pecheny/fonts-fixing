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
sibling never flatters the score. It comes back within 9.5 units at 1000 upem on Latin and
13.5 on Cyrillic, against 29 for knowing nothing. Which fonts to learn from matters as much
as the features: `care()` reads a face's kerning coverage and how many of its sidebearings
are multiples of ten, since a font that kerns nothing and rounds everything has been
defaulted rather than spaced.

Italics are sheared upright before anything is measured. Otherwise every reading of a
slanted face carries the slant rather than the shape, and one italic-angle number cannot
undo that across a hundred features. Shearing about the baseline leaves the advance alone,
so a prediction still applies as a plain shift.

The features read outlines, not codepoints, and each side carries only which script it
belongs to, so the two are learned together without being averaged. Cyrillic costs Latin
accuracy nothing and buys a unit on Cyrillic, and it is the only way the model ever sees a
ж, whose arm overhangs in a way no Latin letter does.

`respacing.py` is where a prediction becomes a font, and two things come off it first.
How a face splits its space between the two sides of a letter is a convention like
tracking: shift every glyph the same way inside its own advance and the page is
unchanged. So the model's mean disagreement with the face's own Latin is subtracted per
side. Geist's Italic reads +40 units on the left against −9 on the right, and left
standing that bias comes out as a uniform widening, because the floor is applied to each
side on its own and only the left side survives it. What remains is the noise the model
cannot see past, 7 to 11 units, which comes off as well; on that italic it was 26 units
before the bias was removed and 11 after, so the same subtraction that stops the widening
also stops throwing away the real moves. The floor itself is the last thing: no pair may
end up nearer than the font's own tightest fit, which keeps the tucks a designer meant,
like the ё that sits under Т's arm.

Half of Geist's Cyrillic is drawn as composites of the Latin letters — а is a, Н is H —
which the Jost work never had to deal with. Moving a base glyph drags everything built on
it, so a composite takes its base's move rather than its own reading, which is also the
only way а stays exactly where a is. Glyphs not being respaced at all, á and Ǎ, inherit
their base's move, and mark anchors travel with the outline they were placed on.

## Kerning from the pair

A sidebearing is one side at a time, and two sides are not a pair. Neither side of к nor
of т can see the cavity the two of them make between them, and neither side of г knows
that its arm reaches over whatever comes next. Kerning is the answer to both, and it is
as much a function of the two shapes as a sidebearing is of one — so `pair_model.py`
fits it the same way. The features are the two facing profiles, measured from each
letter's own extreme so the pair is described with its spacing taken out, plus the shape
of the white they enclose: where it is narrowest, how much of the height stands at that
narrowest point, how much of the band the two letters share. The target is how close the
designer left their ink to coming, kerning included. That is the same fact as the
distance between the two bounding extremes — one is the other plus the overhang, and the
overhang is a feature either way — but a tree fits a number in a leaf and reproduces a
subtraction badly, and the distance between extremes is one: Г's arm sets it while its
stem is what а stands next to. Asking for the approach instead is worth 1.3 units, and
2 on the Cyrillic, where the overhanging capitals are.

`train_pairs.py` fits it on the same corpus and under the same rules as the sidebearing
model: the fonts macOS ships, families held out whole, this repository's own fonts
excluded. 588,000 pairs from 113 families, and it comes back within 11.9 units at 1000
upem — 11.6 on Latin, 13.7 on Cyrillic — against 33.2 for knowing nothing about the pair
beyond how loose the face is set. Two sidebearings predicted separately carry about 21
units between them, so reading the pair as a pair is worth nearly half the error. Telling
it which script it is looking at turns out to be worth nothing at all, 11.8 units against
11.9, so it is reading shapes and not alphabets.

Two things follow from the target being a distance between two shapes rather than a
number attached to one. Capitals come out further apart than lowercase: across the 359
text faces on this machine two capitals stand 144 units of ink apart against 121 for two
lowercase letters, 19% more, in 86% of them. Nothing in the model says so — it reads the
heights and the profiles and the answer follows. And a pair that already holds a cavity
comes out closer, because the white it holds is in the features.

`fit()` applies it, with the same two subtractions as `respace()`. The model's mean
disagreement with the face's own Latin pairs comes off first: that is tracking, one
decision for the whole face and not a fact about any pair, and on Geist it runs to 90
units. Then the model's own held-out error comes off every move, so a pair moves only if
the model can tell the move apart from its own noise. That figure is the model's and not
this font's. Measuring the disagreement on the font at hand and calling it noise reads a
badly spaced face as a noisy one and leaves it alone — on a Geist whose spacing had been
thrown away it came to 16.6 units, twice the model's error, and shrinking by it undid
most of the repair. It comes off in quadrature rather than straight, since subtracting it
whole taxes a move that is past doubt as hard as one that is not.

In Geist's Regular it kerns 2,043 pairs by a median 19 units. кт and са and ту come back
to within a few units of where Geist drew them — the cavity in each is in the features,
so the model asks for no more room than the designer did — while уд, which the respacing
had opened from 194 units to 216, is pulled back to 181. гр opens from 54 to 107, which
is what играм needed: г's arm is the only ink at its height, and the pair reads clumped
against a plain иг at 160. Two capitals keep their distance: ЧР, НН and HI all come out
exactly where Geist set them.

The floor is the last thing applied. Nothing may end up closer at its nearest approach
than the tightest pair the model itself asks for anywhere in the font — the model's own
judgement rather than the font's, because a face may already draw a pair that touches and
Geist does. As drawn it brings 16 Cyrillic pairs and 16 Latin within 30 units of touching,
гт and гх within 8; the build has none, and comes no nearer than 30. On a serif the same
floor comes out negative, since Ty and rn overlap in any face with serifs, and the pass
allows exactly as much overlap as the model expects.

## The hole after Г

Both models above answer to a corpus, and there is one place where that corpus is not
worth following. Most of the Cyrillic the macOS fonts carry was added to a Latin face
that had already been drawn, and it shows in exactly one pair type: an overhanging
capital against a lowercase letter. Those faces kern To and Ta and leave Гд and Ти open.
Measured against each face's own median lowercase approach, Gill Sans, Hoefler Text and
Marion leave 190 to 217 units of hole after Г, Т and У; PT Serif, PT Serif Caption and
PT Sans, drawn in Russia, leave −35 to 0. The median of the 61 faces that kern their
Cyrillic at all is 105, which is the average of two populations and belongs to neither,
and that is what the model learns and reproduces.

Nothing separates the two populations from the outside. How much Cyrillic a face kerns
does not: the half that kerns most leaves the same 105-unit hole as the half that kerns
least. Nor does whether anyone ever kerned an overhanging capital against a lowercase
letter, which 56 of the 61 did. And the script tag is not the lever either, since a model
blind to it scores the same.

So `tuck()` caps the white a pair may hold, and it is the one rule here that overrules
the model as well as the designer. Only pairs that share the same band are compared,
which is what a capital against a capital and a capital against a lowercase letter do
not do: two capitals share the whole cap height, so their column of white is taller and
wider and stays that way, while Гд shares only the x-height with нд and is judged against
it. That is the whole of the case for setting capitals loose, and it is why ЧР, НН and
HI come through this pass untouched.

Two conditions have to hold before a pair counts as a hole. Its white must stand more
than 1.55 times the middle of its group — a multiple rather than a percentile, since a
percentile moves the same share of pairs in every font however well it is spaced — and
its ink must never come as close as the middle pair of that group does. кт and гр hold as
much white as Гд and are not holes: an arm reaches over in each, so the ink meets
somewhere, and the eye reads a tuck rather than a gap. Without the second condition a
hard enough cap pulls гр back under Geist's own kerning and undoes what играм needed.

In Geist's Regular it caps 309 pairs by a median 50 units: Гд from 342 to 223, Га from
336 to 255, Ул from 277 to 199, Ту from 235 to 205. Against the 61 hand-kerned Cyrillic
faces, the Cyrillic pairs standing more than 60 units wider than the room full of them
fall from 36 to 11, and the Latin from 7 to none. The floor is exact here rather than
read off the resampled profiles, which read е against Э — a pair whose ink meets at the
very edge of the band — as further apart than it is, and let it be pulled to 11 units.

An earlier pair of passes went at all of this by percentile, and both are in the git
history. They held every pair of a script between the 25th and 70th percentile of the
font's own closest approaches, and the two faults that fell out follow from one mistake:
the closest approach is the reading under which two capitals and two lowercase letters
come out equal — across the fonts on this machine two capitals stand 144 units of ink
apart to 121 for two lowercase, but at their closest point they are the same. So ЧР came
out 40 units tighter than Geist drew it, and кт, whose ink comes close only because к's
arm reaches over, was read as pinched and opened from 60 units to 99. A percentile also
has no opinion, only a target: it moved 2,870 pairs where the two models move 2,043, and
forced the spread of the approaches to 0.20 where a well-drawn face runs at 0.3.

None of the three passes needs the font to have been spaced or kerned. Given a Geist with
every letter set to the same sidebearing on both sides and all its kerning thrown away,
they put it back to within 22.5 units a pair of the designer, from 35.5 — against the 11.9
the pair model is worth on a face it has never seen. The one thing they cannot supply is
how loose the face is set overall, which is a single number and is read off whatever the
font already has. Run over Literata, Spectral and IBM Plex Serif the same three passes cut
the pairs within 30 units of touching from 66, 41 and 9 in the Latin to 5, 4 and 1, and
from 94, 47 and 7 in the Cyrillic to 1, 0 and 0.


Google Fonts was tried as a corpus and rejected. It has 1,821 families against the 112 macOS
ships, and adding it took the held-out error from 9.6 units to 10.6: the amateur majority
drowns the careful minority, and filtering by `care()` made it worse again by cutting the
data without concentrating it enough. The macOS set is small, curated, and none of it is a
font this repository patches.

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
| `build_geist_fix.py` → Geist Fix | Anchors U+0301 over every Cyrillic vowel, but registers `mark` only under `latn`, so none of it applied to Russian. Also moves ы off its right stroke, respaces both scripts from the sidebearing model, kerns every pair from the pair model, and caps the holes an overhanging capital leaves. Patches all 18 static styles; `geist-sample.typ` sets a line before and after. |
| `build_inter_fix.py` → Inter Fix | Same unregistered `cyrl` script as Geist, plus Ю and я were never anchored. Rewrites the whole 36-face collection, Inter and Inter Display alike. |
| `build_ibm_plex_fix.py` → IBM Plex Sans Fix, IBM Plex Serif Fix | Ё, Э, Ю and Я are the vowels Plex never anchored; the rest of its Cyrillic already works. Both families, 16 styles each. |
| `build_roboto_flex_fix.py` → Roboto Flex Fix | No Cyrillic acute anchors, and typst ignores variable axes so every weight rendered as Regular. Emits static Regular/Italic/Bold/Bold Italic. |
| `build_sofia_sans_ru.py` → Sofia Sans Ru | Sofia Sans ships Bulgarian letterforms as the default; this variant makes the Russian ones default and keeps the Bulgarian set on ss01. Also adds acute anchors on Cyrillic vowels. |
| `pliant-kerning/batch.py` → Pliant | Almost no Cyrillic kerning. Also promotes the double-storey `a` to the default, which is a taste call rather than a fix. |
| `build_literata_fix.py` → Literata Fix | Cyrillic reuses the Latin outlines but not the Latin kerning, so РО keeps a gap PO does not. Matches each Cyrillic side to the Latin shape it is drawn from and carries the kerning over; both variable fonts and all four statics. |
| `build_literata_uniform.py` → Literata Uniform | Kerns the pairs a given document contains so the blurred page shows an even width of light between letters. Tuned to a text, and overrules the designer by design; see the section above. |
| `build_jost_variants.py` → Jost Uniform, Jost Spaced | Jost kerns its Cyrillic about as much as its Latin, so these test the two methods rather than repair neglect. Uniform evens out the kerning of one line, in the Regular. Spaced gives every letter of both scripts the sidebearing the model reads off its outline, in all four styles. `jost-sample.typ` sets the line all three ways. |
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
