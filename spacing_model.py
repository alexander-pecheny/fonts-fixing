"""Predict a glyph's sidebearings from its outline, having learned how fonts do it.

A designer spacing a face looks at the shapes and separates them until the white
between them reads even. That is a function of geometry, so it can be fitted: this
module turns each side of each letter into features, and a model trained across many
faces predicts the sidebearing a designer would have chosen.

Nothing here reads a font's spacing except as the answer sheet during training. The
features are outlines only: the profile of the side, how it slopes and where it stands
back, how much ink stands behind the edge, and a few facts about the face as a whole —
its weight, width, contrast and the counter of its n — all measured from the letters
themselves, since spacing scales with them.

Italics are sheared upright first. Otherwise every reading of a slanted face carries
the slant rather than the shape, and one italic-angle number cannot undo that across a
hundred features. Designers space an italic on the sheared frame too. Shearing about
the baseline leaves the advance alone, so a prediction still applies as a plain shift.
"""

import math

import numpy as np
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

from spacing import runs

# Digits are left out on purpose: lining figures are given equal advances by
# convention, so their sidebearings answer to the table they sit in rather than to
# their shape, and including them cost a whole unit of accuracy.
LETTERS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
CYRILLIC = "абвгдежзийклмнопрстуфхцчшщъыьэюяАБВГДЕЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ"
BAND = (-0.35, 1.45)  # of x-height, the range a side is read over
SAMPLES, OWN, DEPTH = 40, 20, 0.6  # readings across the band, across the glyph, and the deepest that counts
FAR = 1.0  # a second, looser cap, so a body far behind a jutting arm is still visible
ROWS = 10  # units between scanlines at 1000 upem
# Scripts space alike but not identically, and a model told which one it is looking at
# can keep their habits apart instead of averaging them.
SCRIPTS = ((0x0000, 0x024F, 0.0), (0x0370, 0x03FF, 2.0), (0x0400, 0x04FF, 1.0))
ZONES = 4  # vertical bands the ink beside a side is counted in
STRIPS = (0.06, 0.18, 0.40)  # of x-height, how far from the edge that ink is counted


def _script(char):
    """Which script a letter belongs to, as a number the model can split on."""
    for low, high, index in SCRIPTS:
        if low <= ord(char) <= high:
            return index
    return 3.0


def _profile(values, count):
    """Resample a profile to a fixed number of readings."""
    if len(values) < 2:
        return np.full(count, DEPTH)
    return np.interp(np.linspace(0, len(values) - 1, count), np.arange(len(values)), values)


def _zone(band, low, high):
    """The part of the fixed-grid profile lying between two heights, in x-heights."""
    edges = [int(round((y - BAND[0]) / (BAND[1] - BAND[0]) * len(band))) for y in (low, high)]
    part = band[edges[0] : max(edges[1], edges[0] + 1)]
    return part if len(part) else band


def _side_features(profile, ink_rows, ink):
    """What one side of one letter looks like: where it stands back, and how it slopes.

    `ink` is the density of ink beside the side, in a grid of vertical zones by depth.
    Everything else reads the extreme crossing alone, which cannot tell a wire-thin
    serif from a slab, and so reads an open letter like c or ч as tighter than it looks.
    """
    band = np.minimum(np.nan_to_num(profile, nan=DEPTH), DEPTH)
    deep = np.minimum(np.nan_to_num(profile, nan=FAR), FAR)
    own = np.minimum(profile[ink_rows], DEPTH) if ink_rows.any() else np.full(2, DEPTH)
    own = own[~np.isnan(own)]
    if not len(own):
        own = np.full(2, DEPTH)

    # After TypeFacet's intrusion tolerance: how far in can a line be drawn before more
    # than a given depth of ink pokes past it? A serif intrudes on a corridor a stem never
    # would, and reading the side at several tolerances tells the two apart.
    intrusion = []
    for allowed in (0.002, 0.006, 0.015, 0.04):
        depths = np.linspace(own.min(), own.min() + 0.5, 60)
        poked = np.maximum(depths[:, None] - own[None, :], 0).mean(axis=1) * (own.max() - own.min() + 1e-6)
        beyond = depths[poked <= allowed]
        intrusion.append(float(beyond.max()) if len(beyond) else float(own.min()))

    across = _profile(own, OWN)
    slope = np.diff(across)  # a diagonal side slopes steadily; a stem does not
    near = own.min() + 0.03
    waist = _zone(band, 0.0, 1.0)
    return np.concatenate([
        _profile(band, SAMPLES),
        across,
        slope,
        [
            waist.mean(), waist.min(), float((waist <= waist.min() + 0.03).mean()),
            _zone(band, 1.0, BAND[1]).mean(),   # what the ascender does, kept apart from
            _zone(band, BAND[0], 0.0).mean(),   # the x-height zone letters actually meet in
        ],
        [part.mean() for part in np.array_split(own, 3)],
        [
            own.mean(), own.max(), np.median(own),
            np.minimum(own, own.min() + 0.05).mean(),
            np.minimum(own, own.min() + 0.15).mean(),
            np.minimum(own, own.min() + 0.35).mean(),
            (own <= near).mean(),                          # how much of the side is at its closest
            float(np.argmin(own)) / max(len(own) - 1, 1),  # and where that sits vertically
            float(np.abs(slope).mean()), float(slope.mean()),
            float(np.sum((own[1:-1] < own[:-2]) & (own[1:-1] < own[2:]))),  # notches, ie serifs
        ],
        intrusion,
        [float((deep >= DEPTH).mean()), deep.mean(), deep.max()],  # what stands beyond the cap
        ink,
    ])


def _side_ink(spans, ys, edge, side, xheight):
    """How much ink stands within a few depths of one edge, zone by zone up the letter."""
    out = []
    bounds = np.linspace(BAND[0] * xheight, BAND[1] * xheight, ZONES + 1)
    for low, high in zip(bounds, bounds[1:]):
        rows = [row for y, row in zip(ys, spans) if low <= y < high]
        for depth in STRIPS:
            reach = depth * xheight
            near, far = (edge, edge + reach) if side else (edge - reach, edge)
            covered = sum(max(min(b, far) - max(a, near), 0) for row in rows for a, b in row)
            out.append(covered / (max(len(rows), 1) * reach))
    return out


def _face_features(font, cmap, glyphs, scale, xheight, ys):
    """The face as a whole, measured from its own letters: weight, width, contrast, rhythm."""
    def ink(char):
        if ord(char) not in cmap:
            return None
        pen = BoundsPen(glyphs)
        glyphs[cmap[ord(char)]].draw(pen)
        return [v * scale for v in pen.bounds] if pen.bounds else None

    def spans(char, low, high):
        if ord(char) not in cmap:
            return []
        rows = np.linspace(low, high, 5) / scale
        return [[(a * scale, b * scale) for a, b in row] for row in runs(font, cmap[ord(char)], rows)]

    def stem(char):
        """Width of the narrowest horizontal run of ink across the middle of a letter."""
        widths = [row[-1][1] - row[0][0] for row in spans(char, xheight * 0.4, xheight * 0.6) if row]
        return min(widths) if widths else None

    def counter(char):
        """The white a designer measures every bearing against: the gap inside n, or o."""
        gaps = [row[i + 1][0] - row[i][1] for row in spans(char, xheight * 0.4, xheight * 0.6)
                for i in range(len(row) - 1)]
        return max(gaps) if gaps else None

    stems = [s for s in (stem("l"), stem("i"), stem("I")) if s]
    rounds = [s for s in (stem("o"), stem("O")) if s]
    widths = [box[2] - box[0] for box in (ink(c) for c in "nopqbdegh") if box]
    caps = ink("H") or ink("I")
    counters = [c for c in (counter("n"), counter("o"), counter("H")) if c]
    upright = ink("l") or ink("I")
    return [
        (np.mean(stems) / xheight) if stems else 0.1,                    # weight
        (np.mean(widths) / xheight) if widths else 1.0,                  # width
        (np.mean(rounds) / np.mean(stems)) if stems and rounds else 1.0,  # contrast of round to flat
        ((caps[3] - caps[1]) / xheight) if caps else 1.4,                 # cap height
        font["post"].italicAngle / 20.0,
        (np.mean(counters) / xheight) if counters else 0.5,               # the face's own rhythm
        # A serif l is three times wider at the foot than at the waist; a sans is barely
        # wider at all, and the two are spaced by different habits.
        ((upright[2] - upright[0]) / np.mean(stems)) if upright and stems else 1.0,
    ]


def extract(path, font_number=0, letters=LETTERS):
    """Every letter side of one font: its features, and the sidebearing it was given.

    The features read outlines, not codepoints, so a Latin-trained model can be asked
    about another script by passing its letters here.
    """
    font = TTFont(path, fontNumber=font_number, lazy=True)
    if "glyf" not in font and "CFF " not in font:
        return []
    scale = 1000 / font["head"].unitsPerEm
    xheight = getattr(font["OS/2"], "sxHeight", 0) * scale
    if not 300 < xheight < 700:
        return []

    cmap, hmtx, glyphs = font.getBestCmap(), font["hmtx"], font.getGlyphSet()
    family = font["name"].getDebugName(16) or font["name"].getDebugName(1) or path
    lean = math.tan(math.radians(-font["post"].italicAngle))  # shear the slant out
    ys = np.linspace(BAND[0] * xheight, BAND[1] * xheight, int((BAND[1] - BAND[0]) * xheight / ROWS))
    face = _face_features(font, cmap, glyphs, scale, xheight, ys)

    rows = []
    for char in letters:
        if ord(char) not in cmap:
            continue
        name = cmap[ord(char)]
        pen = BoundsPen(glyphs)
        try:
            glyphs[name].draw(TransformPen(pen, (1, 0, -lean, 1, 0, 0)))
        except Exception:
            continue
        if not pen.bounds or (pen.bounds[2] - pen.bounds[0]) * scale < 10:
            continue
        xmin, ymin, xmax, ymax = (v * scale for v in pen.bounds)

        spans = [[(a * scale - y * lean, b * scale - y * lean) for a, b in row]
                 for row, y in zip(runs(font, name, ys / scale), ys)]
        right = np.array([row[-1][1] if row else np.nan for row in spans])
        left = np.array([row[0][0] if row else np.nan for row in spans])
        ink_rows = ~np.isnan(right)
        for side, profile, target, edge in (
            (0, (xmax - right) / xheight, hmtx[name][0] * scale - xmax, xmax),
            (1, (left - xmin) / xheight, xmin, xmin),
        ):
            rows.append({
                "family": family, "char": char, "side": side, "xheight": xheight,
                "target": target / xheight,
                "features": np.concatenate([
                    _side_features(profile, ink_rows, _side_ink(spans, ys, edge, side, xheight)),
                    [(ymax - ymin) / xheight, (xmax - xmin) / xheight,
                     max(ymax - xheight, 0) / xheight, max(-ymin, 0) / xheight,
                     float(char.isupper()), float(side), _script(char)],
                    face,
                ]),
            })
    return rows


def care(path, font_number=0):
    """Signs of how much attention a face's spacing was given, rather than how good it is.

    A font that kerns three hundred Latin pairs and not one Cyrillic pair has said which
    script it reviewed. And sidebearings snapped to multiples of ten are a default being
    accepted rather than a judgement being made — a designer who looked leaves odd
    numbers behind. Neither proves anything on its own; both are worth weighting by.
    """
    import uharfbuzz as hb

    font = TTFont(path, fontNumber=font_number, lazy=True)
    scale = 1000 / font["head"].unitsPerEm
    cmap, hmtx = font.getBestCmap(), font["hmtx"]
    with open(path, "rb") as handle:
        face = hb.Face(handle.read(), font_number)
    shaper = hb.Font(face)

    def kerned(alphabet):
        # the letters that actually attract kerning, or every font looks unkerned: nobody
        # kerns b against d, and sampling a to n was measuring nothing at all
        letters = [c for c in alphabet if ord(c) in cmap]
        if len(letters) < 10:
            return None
        letters = letters[:14]
        seen = 0
        for a in letters:
            for b in letters:
                buf = hb.Buffer()
                buf.add_str(a + b)
                buf.guess_segment_properties()
                hb.shape(shaper, buf, {"kern": True})
                on = sum(g.x_advance for g in buf.glyph_positions)
                buf = hb.Buffer()
                buf.add_str(a + b)
                buf.guess_segment_properties()
                hb.shape(shaper, buf, {"kern": False})
                if on != sum(g.x_advance for g in buf.glyph_positions):
                    seen += 1
        return seen / 196

    bearings = [hmtx[cmap[ord(c)]][1] * scale for c in LETTERS if ord(c) in cmap]
    rounded = np.mean([abs(v - round(v / 10) * 10) < 1 for v in bearings]) if bearings else 1.0
    return {
        "latin kerning": kerned("AVWYTLPFvwyafrToe") or 0.0,
        "cyrillic kerning": kerned("АУФГТЬЪЯавгуфтяъь"),
        "round numbers": float(rounded),
    }


def centred(rows):
    """Targets with each face's own tracking removed, since that is a separate choice."""
    mean = np.mean([row["target"] for row in rows])
    return np.array([row["target"] - mean for row in rows]), mean
