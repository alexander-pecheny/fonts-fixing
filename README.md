# fonts-fixing

Scripts for patching fonts that typeset Russian badly, plus the proof renderer used to
check the results by eye. Everything runs through `uv` and needs `typst` on PATH for proofs.

## Stress marks (U+0301)

Most fonts list only Latin glyphs in their GPOS mark-to-base coverage, so a combining
acute lands after the letter instead of over it. `acutefix.py` adds the missing anchors:
X from the glyph's bounding-box center, Y copied from the font's own Latin `O`/`o` anchors
so the result matches its precomposed `Á`/`á`. Two refinements matter in practice:

- Ю and ю take the center of their rightmost contour — over the bowl, not the whole width.
- The acute is usually a steeply slanted parallelogram. Centering its bounding box makes it
  read as pointing at the left half of the letter, so the midpoint of its lower edge — the
  end it visually points with — is what gets centered instead.

```
uv run inspect_acute.py ~/Library/Fonts/RobotoFlexFix/RobotoFlexFix-Regular.ttf
uv run build_roboto_flex_fix.py
uv run proof.py "Roboto Flex Fix" some/older-version.ttf --size 100
```

`proof.py` takes installed family names and/or .ttf paths and renders them as rows of one
image, so before/after versions of the same font can sit side by side.

## Fonts built here

| Font | What was wrong |
| --- | --- |
| `build_roboto_flex_fix.py` → Roboto Flex Fix | No Cyrillic acute anchors, and typst ignores variable axes so every weight rendered as Regular. Emits static Regular/Italic/Bold/Bold Italic. |
| `build_sofia_sans_ru.py` → Sofia Sans Ru | Bulgarian letterforms by default (moved to ss01), no acute anchors on Cyrillic vowels. |
| `pliant-kerning/batch.py` → Pliant | Almost no Cyrillic kerning, and the single-storey `a` was the default. |

The Sofia and Pliant scripts are kept as they were run rather than refactored onto
`acutefix.py` — those fonts are installed and correct, and the scripts carry work
(the Russian-default transform, the autokerning model) that is the point of keeping them.

## Why variable fonts get instanced

Typst 0.14 warns `variable fonts are not currently supported` and uses only the default
instance, so `chgksuite compose pdf --font 'Roboto Flex'` rendered every bold run at
weight 400. `typst fonts --variants` is the quick check: a usable family lists more than
one weight.
