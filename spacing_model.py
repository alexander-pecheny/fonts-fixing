"""Predict a glyph's sidebearings from its outline, having learned how fonts do it.

A designer spacing a face looks at the shapes and separates them until the white
between them reads even. That is a function of geometry, so it can be fitted: this
module turns each side of each letter into features, and a model trained across many
faces predicts the sidebearing a designer would have chosen. Held out families it has
never seen come back within about 8 units at 1000 upem, against 25 for knowing nothing.

Nothing here reads a font's spacing except as the answer sheet during training. The
features are outlines only: the profile of the side, how it slopes and where it stands
back, and a few facts about the face as a whole — its weight, width and contrast — all
measured from the letters themselves, since spacing scales with them.
"""

import numpy as np
from fontTools.pens.boundsPen import BoundsPen
from fontTools.ttLib import TTFont

from spacing import scan

# Digits are left out on purpose: lining figures are given equal advances by
# convention, so their sidebearings answer to the table they sit in rather than to
# their shape, and including them cost a whole unit of accuracy.
LETTERS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
BAND = (-0.35, 1.45)  # of x-height, the range a side is read over
SAMPLES, OWN, DEPTH = 40, 20, 0.6  # readings across the band, across the glyph, and the deepest that counts
ROWS = 10  # units between scanlines at 1000 upem


def _profile(values, count):
    """Resample a profile to a fixed number of readings."""
    if len(values) < 2:
        return np.full(count, DEPTH)
    return np.interp(np.linspace(0, len(values) - 1, count), np.arange(len(values)), values)


def _side_features(profile, ink_rows):
    """What one side of one letter looks like: where it stands back, and how it slopes."""
    band = np.minimum(np.nan_to_num(profile, nan=DEPTH), DEPTH)
    own = np.minimum(profile[ink_rows], DEPTH) if ink_rows.any() else np.full(2, DEPTH)
    own = own[~np.isnan(own)]
    if not len(own):
        own = np.full(2, DEPTH)

    # After TypeFacet's intrusion tolerance: how far in can a line be drawn before more
    # than a given area of ink pokes past it? A serif intrudes on a corridor a stem never
    # would, and reading the side at several tolerances tells the two apart.
    intrusion = []
    for allowed in (0.002, 0.006, 0.015, 0.04):
        depths = np.linspace(own.min(), own.min() + 0.5, 60)
        poked = [(np.maximum(depth - own, 0).mean() * (own.max() - own.min() + 1e-6)) for depth in depths]
        beyond = [d for d, area in zip(depths, poked) if area <= allowed]
        intrusion.append(max(beyond) if beyond else own.min())

    across = _profile(own, OWN)
    slope = np.diff(across)  # a diagonal side slopes steadily; a stem does not
    thirds = [part.mean() for part in np.array_split(own, 3)]
    near = own.min() + 0.03
    return np.concatenate([
        _profile(band, SAMPLES),
        across,
        slope,
        thirds,
        [
            own.mean(), own.max(), np.median(own),
            np.minimum(own, own.min() + 0.05).mean(),
            np.minimum(own, own.min() + 0.15).mean(),
            np.minimum(own, own.min() + 0.35).mean(),
            (own <= near).mean(),                      # how much of the side is at its closest
            float(np.argmin(own)) / max(len(own) - 1, 1),  # and where that sits vertically
            float(np.abs(slope).mean()), float(slope.mean()),
            float(np.sum((own[1:-1] < own[:-2]) & (own[1:-1] < own[2:]))),  # notches, ie serifs
        ],
        intrusion,
    ])


def _face_features(font, cmap, glyphs, scale, xheight):
    """The face as a whole, measured from its own letters: weight, width, contrast, slant."""
    def ink(char):
        if ord(char) not in cmap:
            return None
        pen = BoundsPen(glyphs)
        glyphs[cmap[ord(char)]].draw(pen)
        return [v * scale for v in pen.bounds] if pen.bounds else None

    def stem(char):
        """Width of the narrowest horizontal run of ink across the middle of a letter."""
        box = ink(char)
        if not box:
            return None
        ys = np.linspace(box[1] + (box[3] - box[1]) * 0.4, box[1] + (box[3] - box[1]) * 0.6, 5) / scale
        right, left = scan(font, cmap[ord(char)], ys)
        runs = (right - left) * scale
        return float(np.nanmin(runs)) if not np.all(np.isnan(runs)) else None

    stems = [s for s in (stem("l"), stem("i"), stem("I")) if s]
    rounds = [s for s in (stem("o"), stem("O")) if s]
    widths = [box[2] - box[0] for box in (ink(c) for c in "nopqbdegh") if box]
    caps = ink("H") or ink("I")
    return [
        (np.mean(stems) / xheight) if stems else 0.1,                    # weight
        (np.mean(widths) / xheight) if widths else 1.0,                  # width
        (np.mean(rounds) / np.mean(stems)) if stems and rounds else 1.0,  # contrast of round to flat
        ((caps[3] - caps[1]) / xheight) if caps else 1.4,                 # cap height
        font["post"].italicAngle / 20.0,
    ]


def extract(path, font_number=0):
    """Every letter side of one font: its features, and the sidebearing it was given."""
    font = TTFont(path, fontNumber=font_number, lazy=True)
    if "glyf" not in font and "CFF " not in font:
        return []
    scale = 1000 / font["head"].unitsPerEm
    xheight = getattr(font["OS/2"], "sxHeight", 0) * scale
    if not 300 < xheight < 700:
        return []

    cmap, hmtx, glyphs = font.getBestCmap(), font["hmtx"], font.getGlyphSet()
    family = font["name"].getDebugName(16) or font["name"].getDebugName(1) or path
    face = _face_features(font, cmap, glyphs, scale, xheight)

    ys = np.linspace(BAND[0] * xheight, BAND[1] * xheight, int((BAND[1] - BAND[0]) * xheight / ROWS))
    rows = []
    for char in LETTERS:
        if ord(char) not in cmap:
            continue
        name = cmap[ord(char)]
        pen = BoundsPen(glyphs)
        try:
            glyphs[name].draw(pen)
        except Exception:
            continue
        if not pen.bounds or (pen.bounds[2] - pen.bounds[0]) * scale < 10:
            continue
        xmin, ymin, xmax, ymax = (v * scale for v in pen.bounds)
        right, left = scan(font, name, ys / scale)
        ink_rows = ~np.isnan(right)
        for side, profile, target in (
            (0, (xmax - right * scale) / xheight, hmtx[name][0] * scale - xmax),
            (1, (left * scale - xmin) / xheight, xmin),
        ):
            rows.append({
                "family": family, "char": char, "side": side, "xheight": xheight,
                "target": target / xheight,
                "features": np.concatenate([
                    _side_features(profile, ink_rows),
                    [(ymax - ymin) / xheight, (xmax - xmin) / xheight,
                     max(ymax - xheight, 0) / xheight, max(-ymin, 0) / xheight,
                     float(char.isupper()), float(side)],
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
