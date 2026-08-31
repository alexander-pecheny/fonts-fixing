"""Give every letter the sidebearing `spacing-model.joblib` reads off its outline.

The model is asked about both scripts at once. A font that draws Cyrillic а as Latin a
has spaced the two alike on purpose, and moving one script alone pulls such a pair apart
for no reason anything measured on a side can see.

Its error on the face's own Latin is subtracted from every proposal, so a move survives
only if the model can tell it apart from its own noise. What is left is held to a floor:
no pair may end up nearer than the font's own tightest fit, or than it already was.
"""

import numpy as np
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables import otTables as ot

from spacing import BAND, FLOOR, SOFTNESS, STEP, add_kern_lookup, kerner, scan
from spacing_model import CYRILLIC, LETTERS, centred, extract

ROWS = 10  # units between the scanlines a pair is checked on
NEAREST = 2  # percentile of the font's own approaches that nothing may go under
ROUNDS = 20
PINCHED, GAPING = 25, 70  # percentiles of its own approaches the font is held between
LID, NARROW = 1.3, 0.25  # a pinch this close over less than this much height is an overhang
LIMIT = 60  # units a pair may be kerned by


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


def hold(font, path, scripts=(LETTERS, CYRILLIC + "Ёё")):
    """Kern back the pairs respacing opened that were open to begin with.

    The model reads one side at a time, so it never sees that two letters it has each
    given more room are now, together, further apart than almost any pair on the page.
    Geist's у and д both moved out and уд, already looser than nine Cyrillic pairs in ten,
    opened by another 23 units — which is what the eye catches first.

    So nothing that already stood further apart than the median may end up further apart
    than the designer left it. A pair that was tight keeps whatever the model gave it:
    ту opens from 131 units of channel to 169 and stays there. Measured against the font
    as drawn rather than against a target of its own, this can only give back, never
    override, which is why it runs over the Latin as well.
    """
    cmap, values = font.getBestCmap(), {}
    was = TTFont(path)
    kern = kerner(open(path, "rb").read())  # respacing leaves the kerning alone
    scale = font["head"].unitsPerEm / 1000
    ys = np.arange(-40 * scale, 760 * scale, STEP * scale)

    def measure(source, letters):
        metrics, sides = source["hmtx"], {}
        for char in letters:
            far, near = scan(source, cmap[ord(char)], ys)
            sides[char] = (metrics[cmap[ord(char)]][0] - far, near)
        return sides

    for letters in scripts:
        letters = [char for char in letters if ord(char) in cmap]
        drawn, now = measure(was, letters), measure(font, letters)

        def channel(sides, a, b, extra=0.0):
            gap = sides[a][0] + sides[b][1] + kern(a, b) + extra
            gap = gap[~np.isnan(gap)]
            return float(np.mean(np.maximum(gap, FLOOR) ** SOFTNESS) ** (1 / SOFTNESS)) if len(gap) else None

        before = {(a, b): channel(drawn, a, b) for a in letters for b in letters}
        middling = np.median([width for width in before.values() if width])
        for pair, width in before.items():
            after = channel(now, *pair)
            if width is None or after is None or width < middling or after <= width:
                continue
            back = width - after
            for _ in range(2):  # the channel is a soft minimum, so not quite linear in the kern
                back += width - channel(now, *pair, back)
            value = int(round(back / (STEP * scale)) * STEP * scale)
            if value:
                values[cmap[ord(pair[0])], cmap[ord(pair[1])]] = value
    add_kern_lookup(font, values)
    return np.array(list(values.values()))


def even(font, data, scripts=(LETTERS, CYRILLIC + "Ёё")):
    """Kern until the ink of one pair comes as close as the ink of the next.

    Everything above measures the white between two letters. That is what a designer
    balances, but it is not what catches the eye in a word: играм reads as clumped
    because г's arm is the only ink at its height, so г and р stand 349 units apart for
    nine tenths of their height and 67 apart at the top — while иг, a plain pair of
    stems, keeps its 160 all the way up. All four gaps in that word measure within five
    units of each other as white, which is why nothing else here flagged them.

    So this reads the other thing: how close the two letters ever come. A pair pinched
    that way is opened, one whose ink never approaches is pulled in, and both are held
    inside the band the font's own pairs occupy. Two round letters are exempt from the
    first rule — о against о comes as close as г against р does, but gradually, over a
    third of its height rather than at a single lid, and the eye reads that as a lens of
    white rather than a collision.

    This overrides the designer rather than restoring him, unlike everything above it.
    It also repairs a real fault: Geist kerns гЭ tight enough that the two letters touch.
    """
    cmap, hmtx, values = font.getBestCmap(), font["hmtx"], {}
    kern = kerner(data)
    scale = font["head"].unitsPerEm / 1000  # every limit here is in units of 1000 to the em
    ys = np.arange(BAND[0] * scale, BAND[1] * scale, ROWS * scale)

    for letters in scripts:
        letters = [char for char in letters if ord(char) in cmap]
        sides = {}
        for char in letters:
            far, near = scan(font, cmap[ord(char)], ys)
            sides[char] = (hmtx[cmap[ord(char)]][0] - far, near)
        gaps = {}
        for a in letters:
            for b in letters:
                gap = sides[a][0] + sides[b][1] + kern(a, b)
                gap = gap[~np.isnan(gap)]
                if len(gap):
                    gaps[a, b] = gap

        approach = np.array([gap.min() for gap in gaps.values()])
        closer, wider = np.percentile(approach, PINCHED), np.percentile(approach, GAPING)
        for (a, b), gap in gaps.items():
            room = float(gap.min())
            if room < closer and float((gap <= room * LID).mean()) < NARROW:
                move = closer - room
            elif room > wider:
                move = wider - room
            else:
                continue
            move = int(round(float(np.clip(move, -LIMIT * scale, LIMIT * scale)) / (STEP * scale)) * STEP * scale)
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
