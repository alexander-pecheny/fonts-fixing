"""Space a font by the two models: sidebearings from each outline, then kerning per pair.

`respace` asks `spacing-model.joblib` what sidebearing each letter's outline calls for.
Both scripts are asked at once: a font that draws Cyrillic а as Latin a has spaced the
two alike on purpose, and moving one script alone pulls such a pair apart for no reason
anything measured on a side can see.

`fit` then asks `pair-model.joblib` how far apart each pair of letters should stand. A
sidebearing is one side at a time, and the sum of two sides is not a pair: it cannot see
the cavity between кт or the pinch under г's arm, which is what kerning is for.

Both subtract the model's error on the face's own Latin before proposing anything, so a
move survives only if the model can tell it apart from its own noise.
"""

import io

import numpy as np
from fontTools.ttLib.tables import otTables as ot

import pair_model
from spacing import BAND, add_kern_lookup, kerner, scan
from spacing_model import CYRILLIC, LETTERS, centred, extract

ROWS = 10  # units between the scanlines a pair is checked on
NEAREST = 2  # percentile of the predicted approaches that nothing may end up under
ROUNDS = 20
LIMIT = 100  # units a pair may be kerned by
QUANTUM = 5  # units a kern is rounded to


def clearances(font, kern, letters):
    """How close each ordered pair of letters ever comes, kerning included."""
    cmap, hmtx = font.getBestCmap(), font["hmtx"]
    ys = np.arange(*BAND, ROWS)
    sides = {}
    for char in letters:
        far, near = scan(font, cmap[ord(char)], ys)
        sides[char] = (hmtx[cmap[ord(char)]][0] - far, near)
    room = np.full((len(letters), len(letters)), np.inf)
    for i, a in enumerate(letters):
        for j, b in enumerate(letters):
            gap = sides[a][0] + sides[b][1] + kern(a, b)
            seen = gap[~np.isnan(gap)]
            if len(seen):
                room[i, j] = seen.min()
    return room


def shift(font, moves):
    """Move each glyph's sidebearings, following the glyphs that are drawn from it.

    Geist builds half its Cyrillic out of the Latin letter — а is a, Н is H — and its
    accented letters out of the plain ones, so translating a base drags everything drawn
    on it. A composite being respaced in its own right subtracts the shift it inherits;
    one that is not, á or Ǎ, takes its base's move as its own, which is the spacing it
    would have been given anyway. Anchors travel with the outline they were placed on,
    or a stress mark ends up off the letter by however far the letter moved.
    """
    glyf, hmtx, done = font["glyf"], font["hmtx"], {}

    def apply(name):
        if name in done:
            return done[name]
        done[name] = (0, 0)  # a cycle would be a broken font, but do not hang on one
        glyph, move = glyf[name], moves.get(name, (0, 0))
        if glyph.isComposite():
            leaks = [apply(part.glyphName) for part in glyph.components]
            if name not in moves:
                move = next((leak for leak in leaks if leak != (0, 0)), (0, 0))
            for part, leak in zip(glyph.components, leaks):
                part.x += move[0] - leak[0]
        elif move[0]:
            glyph.coordinates.translate((move[0], 0))
        if move != (0, 0):
            glyph.recalcBounds(glyf)
            hmtx[name] = (hmtx[name][0] + move[0] + move[1], glyph.xMin)
        done[name] = move
        return move

    for name in font.getGlyphOrder():
        apply(name)
    _shift_anchors(font, {name: move[0] for name, move in done.items() if move[0]})
    return done


def _shift_anchors(font, dx):
    """Anchors are glyph coordinates, so they move with the glyph they belong to."""
    if "GPOS" not in font:
        return
    for lookup in font["GPOS"].table.LookupList.Lookup:
        for subtable in lookup.SubTable:
            subtable = getattr(subtable, "ExtSubTable", subtable)
            if isinstance(subtable, ot.MarkBasePos):
                for name, record in zip(subtable.BaseCoverage.glyphs, subtable.BaseArray.BaseRecord):
                    for anchor in record.BaseAnchor:
                        if anchor is not None and dx.get(name):
                            anchor.XCoordinate += dx[name]
            elif isinstance(subtable, ot.CursivePos):
                for name, record in zip(subtable.Coverage.glyphs, subtable.EntryExitRecord):
                    for anchor in (record.EntryAnchor, record.ExitAnchor):
                        if anchor is not None and dx.get(name):
                            anchor.XCoordinate += dx[name]


def fit(font, data, model, scripts=(LETTERS, CYRILLIC + "Ёё")):
    """Kern every pair to the distance `pair-model.joblib` reads off the two shapes.

    A sidebearing is one side at a time, and a pair is not the sum of two sides. Two
    letters that each stand back leave a cavity between them — кт, са, ту — and neither
    side can see it; a letter whose arm overhangs pinches a pair whose sidebearings look
    generous — гр, rn, Ту. Both are what kerning is for, and both are a function of the
    two facing shapes, so both can be learned: see `pair_model`.

    Two things come off every proposal, as in `respace`. First the model's mean
    disagreement with this face's own Latin pairs, since how loose a font is set is one
    decision for the whole face and not a fact about any pair. Then the model's own
    error on faces it has never seen, 13 units, so a pair moves only if the model can
    tell the move apart from its own noise. That figure is the model's and not this
    font's: how far a particular face disagrees is partly the face being wrong, and
    measuring it here would leave a badly spaced font badly spaced. Last, nothing may
    end up closer at its nearest approach than the tightest pair the model itself asks
    for anywhere in the font.
    """
    read = pair_model.sides(io.BytesIO(data), letters="".join(scripts))
    kern, letters, face = kerner(data), read["letters"], read["face"]
    xheight, scale = read["xheight"], read["scale"]  # x-height and units at 1000 to the em

    rows = []
    for index, alphabet in enumerate(scripts):
        have = [char for char in alphabet if char in letters]
        for a in have:
            for b in have:
                first, second = letters[a], letters[b]
                joint = first["right"] + second["left"]
                rows.append((index, a, b,
                             first["bearing"][0] + second["bearing"][1] + kern(a, b) * scale / xheight,
                             float(np.nanmin(joint)) if not np.all(np.isnan(joint)) else 0.0,
                             pair_model.features(first, second, face)))
    if not rows:
        return np.array([])

    want = model["model"].predict(np.array([row[-1] for row in rows]))
    have = np.array([row[3] for row in rows])
    latin = np.array([not row[0] for row in rows])
    bias = float((want - have)[latin].mean()) if latin.any() else float((want - have).mean())
    noise = model["error"]

    lowest = np.array([row[4] for row in rows])
    floor = float(np.percentile(want - bias + lowest, NEAREST))  # the model's own tightest fit,
    # rather than the font's: a face may already draw a pair that touches, and Geist does

    cmap, values = font.getBestCmap(), {}
    step, limit = QUANTUM / scale, LIMIT / scale
    for (_, a, b, gap, nearest, _), target in zip(rows, want):
        move = target - bias - gap
        move = np.sign(move) * max(abs(move) - noise, 0)
        move = max(move, floor - (gap + nearest))
        move = int(round(float(np.clip(move * xheight / scale, -limit, limit)) / step) * step)
        if move:
            values[cmap[ord(a)], cmap[ord(b)]] = move
    add_kern_lookup(font, values)
    return np.array(list(values.values()))


def respace(font, path, model, letters=LETTERS + CYRILLIC + "Ёё"):
    """Respace `font`, reading the outlines and the kerning from the file it came from.

    How a face splits its space between the left and right of a letter is a convention
    of its own, the way tracking is: shift every glyph the same distance inside its own
    advance and the page is unchanged. So the model's mean disagreement with this face's
    own Latin is taken off each side before anything is proposed. On Geist's italic that
    bias runs +40 units on the left against −9 on the right, and left standing it would
    come out as a uniform widening, because the floor below is applied to each side
    separately and only the left side survives it.

    What is left is the noise, seven to eleven units, which is what the model cannot
    tell apart. A pair collects two sides, so it carries twice that. Subtracting it makes
    small moves vanish and leaves large ones nearly whole.
    """
    latin = extract(path)
    centre, tracking = centred(latin)  # the font's own Latin tracking, which stays
    unit = latin[0]["xheight"] * font["head"].unitsPerEm / 1000
    error = (model.predict(np.array([row["features"] for row in latin])) - centre) * unit
    which = np.array([row["side"] for row in latin])
    bias = np.array([error[which == side].mean() for side in (0, 1)])
    noise = float(np.abs(error - bias[which]).mean())

    rows = extract(path, letters=letters)
    wanted = model.predict(np.array([row["features"] for row in rows])) + tracking
    sides = {}
    for row, value in zip(rows, wanted):
        move = (value - row["target"]) * unit - bias[row["side"]]
        sides.setdefault(row["char"], {})[row["side"]] = np.sign(move) * max(abs(move) - noise, 0)
    chars = [char for char, both in sorted(sides.items()) if len(both) == 2]

    proposed = [np.array([sides[c][side] for c in chars]) for side in (0, 1)]

    kern = kerner(open(path, "rb").read())
    room = clearances(font, kern, chars)
    floor = np.minimum(np.percentile(room[np.isfinite(room)], NEAREST), room)
    right, left = (part.copy() for part in proposed)
    for _ in range(ROUNDS):
        short = floor - (room + right[:, None] + left[None, :])
        if short.max() <= 0.5:
            break
        right += np.clip(short.max(axis=1), 0, None) / 2
        left += np.clip(short.max(axis=0), 0, None) / 2
    held = float(np.mean([np.abs(part - was).mean() for part, was in zip((right, left), proposed)]))

    cmap, glyf = font.getBestCmap(), font["glyf"]
    moves = {cmap[ord(c)]: (round(left[i]), round(right[i])) for i, c in enumerate(chars)}
    for name in list(moves):  # a letter the font draws as another letter is that letter,
        parts = glyf[name].components if glyf[name].isComposite() else []
        if len(parts) == 1 and parts[0].glyphName in moves:  # and must not drift off it by
            moves[name] = moves[parts[0].glyphName]  # the units the model reads per script
    shift(font, moves)
    return np.array([v for pair in moves.values() for v in pair]), held, noise
