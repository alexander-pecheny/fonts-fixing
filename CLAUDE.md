# fonts-fixing

Scripts that patch fonts for Russian typesetting. Everything runs through `uv run`; proofs
need `typst` on PATH. Built copies live in `fonts/` and are the deliverable. `scratchpad/`
is gitignored and is where proofs, trial faces and one-off scripts go.

## Spacing and kerning a font

`respacing.py` holds the pipeline, and `build_geist_fix.py` is the example of it run in
full. Four passes, in this order, each fixing what the one before it cannot see:

1. `respace(font, path, model)` — `spacing-model.joblib` predicts each sidebearing from
   the outline. Both scripts go together, since a font that draws а as a has spaced them
   alike on purpose. Two corrections come off every proposal first: the model's mean
   disagreement with the face's own Latin on each side, which is a convention rather than
   a judgement, and then the noise that remains, so only a move the model can tell apart
   from its own error survives.
2. `shift(font, moves)` — applies those moves. A composite drawn from one other glyph
   takes that glyph's move; anything else built on a moved glyph follows it; anchors travel
   with the outline, or the stress mark ends up off the letter.
3. `hold(font, path)` — the model reads one side at a time and cannot see a pair, so two
   letters each given more room can end up further apart than any pair on the page. Nothing
   that already stood further apart than the median may end up further apart than the
   designer left it. This only ever gives back, so it runs over the Latin too.
4. `even(font, data)` — everything above measures the white between two letters; this
   reads how close their ink ever comes, which is what the eye catches in a word. Pairs
   pinched by an overhang are opened, pairs whose ink never approaches are pulled in, both
   held inside the band the font's own pairs occupy. It needs the font's current bytes,
   so serialise to a `BytesIO` after `hold` and pass that. This is the only pass that
   overrules the designer.

Nothing in any of it is particular to one font: thresholds are percentiles of the font's
own pairs and limits are scaled by the em. Constants sit at the top of `respacing.py`.

`spacing.py` holds the geometry — scanline profiles, the soft-minimum channel, the blurred
page reading, `add_kern_lookup`. `spacing_model.py` extracts the features and `care()`;
`train_spacing.py` fits the model on the fonts macOS ships.

## What counts as done

A number is not a result here. Every change is checked by eye before it ships:

    uv run proof.py --no-accents --size 70 --words "играм будет" a.ttf b.ttf --out scratchpad/x.png
    typst compile --font-path fonts geist-sample.typ scratchpad/geist/geist-sample.pdf

Renders are files, not chat output — give the path. Keep the previous build in
`scratchpad/` before overwriting `fonts/`, so three-way comparisons are possible.

Check for collisions after any kerning pass: no pair should end up closer at its nearest
approach than the font's own tightest, and a font as drawn may already have some.

## Writing

Prose in this repo explains why a decision was made and what was tried and rejected. Say
what the numbers were. At most one line of comment per hundred lines of code, and only for
a why the code cannot show; the reasoning belongs in docstrings and in `README.md`.
