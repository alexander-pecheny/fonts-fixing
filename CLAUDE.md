# fonts-fixing

Scripts that patch fonts for Russian typesetting. Everything runs through `uv run`; proofs
need `typst` on PATH. Built copies live in `fonts/` and are the deliverable. `scratchpad/`
is gitignored and is where proofs, trial faces and one-off scripts go.

## Spacing and kerning a font

`respacing.py` holds the pipeline, and `build_geist_fix.py` is the example of it run in
full. Two passes and two models, in this order:

1. `respace(font, path, model)` — `spacing-model.joblib` predicts each sidebearing from
   the outline. Both scripts go together, since a font that draws а as a has spaced them
   alike on purpose. Two corrections come off every proposal first: the model's mean
   disagreement with the face's own Latin on each side, which is a convention rather than
   a judgement, and then the noise that remains, so only a move the model can tell apart
   from its own error survives. `shift(font, moves)` applies them: a composite drawn from
   one other glyph takes that glyph's move; anything else built on a moved glyph follows
   it; anchors travel with the outline, or the stress mark ends up off the letter.
2. `fit(font, data, model)` — `pair-model.joblib` predicts how far apart each pair of
   letters should stand, from the two facing profiles and the shape of the white between
   them. This is what sees the cavity in кт and the overhang in гр, which no reading of a
   single side can. It needs the font's current bytes, so serialise to a `BytesIO` after
   `respace` and pass that. The face's own tracking comes off first; then the model's
   held-out error, which travels in the joblib beside it — never the disagreement
   measured on the font at hand, since on a badly spaced face that is the face being
   wrong and shrinking by it leaves the fault in place.

Nothing in either is particular to one font, and neither needs the font to have been
spaced or kerned at all: the models supply every judgement and the only thing read off
the face is its tracking, one number. Constants sit at the top of `respacing.py`.

`spacing.py` holds the geometry — scanline profiles, the soft-minimum channel, the blurred
page reading, `add_kern_lookup`. `spacing_model.py` and `pair_model.py` extract the
features; `train_spacing.py` and `train_pairs.py` fit the two models on the fonts macOS
ships.

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
