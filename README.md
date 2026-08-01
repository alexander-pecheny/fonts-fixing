# fonts-fixing

Scripts for patching fonts that typeset Russian badly, plus the proof renderer used to
check the results by eye. Everything runs through `uv` and needs `typst` on PATH for proofs.

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

`recenter_acute` handles the opposite case, where an anchor exists but sits somewhere
Russian does not want it: Geist hangs the mark over ы's right stroke rather than the middle.

A font can also have every anchor it needs and still typeset the acute wrong. GPOS lists
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

## Fonts built here

Built copies live in `fonts/`; install with `cp -r fonts/GeistFix ~/Library/Fonts/`.

| Font | What the script changes |
| --- | --- |
| `build_geist_fix.py` → Geist Fix | Anchors U+0301 over every Cyrillic vowel, but registers `mark` only under `latn`, so none of it applied to Russian. Also moves ы off its right stroke. Patches all 18 static styles. |
| `build_inter_fix.py` → Inter Fix | Same unregistered `cyrl` script as Geist, plus Ю and я were never anchored. Rewrites the whole 36-face collection, Inter and Inter Display alike. |
| `build_roboto_flex_fix.py` → Roboto Flex Fix | No Cyrillic acute anchors, and typst ignores variable axes so every weight rendered as Regular. Emits static Regular/Italic/Bold/Bold Italic. |
| `build_sofia_sans_ru.py` → Sofia Sans Ru | Sofia Sans ships Bulgarian letterforms as the default; this variant makes the Russian ones default and keeps the Bulgarian set on ss01. Also adds acute anchors on Cyrillic vowels. |
| `pliant-kerning/batch.py` → Pliant | Almost no Cyrillic kerning. Also promotes the double-storey `a` to the default, which is a taste call rather than a fix. |

All five upstreams are under the SIL Open Font License, which the patched copies inherit.
`OFL.txt` ships next to the fonts that came with one; [Geist](https://github.com/vercel/geist-font),
[Inter](https://github.com/rsms/inter) and [Roboto Flex](https://github.com/googlefonts/roboto-flex)
keep theirs upstream.

The Sofia and Pliant scripts are kept as they were run rather than refactored onto
`acutefix.py` — those fonts are installed and correct, and the scripts carry work
(the Russian-default transform, the autokerning model) that is the point of keeping them.

## Why variable fonts get instanced

Typst 0.14 warns `variable fonts are not currently supported` and uses only the default
instance, so `chgksuite compose pdf --font 'Roboto Flex'` rendered every bold run at
weight 400. `typst fonts --variants` is the quick check: a usable family lists more than
one weight.
