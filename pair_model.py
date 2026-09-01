"""Predict how far apart two letters should stand, having learned how fonts do it.

`spacing_model` reads one side at a time, which is all a sidebearing is. But a pair is
not the sum of two sides: two letters that each stand back — к and т, с and а — leave a
cavity between them that neither side can see, and a letter whose arm overhangs — г, r,
T — pinches a pair whose sidebearings look generous. Designers answer both with kerning.

So this measures the pair. The features are the two facing profiles and the shape of the
white they enclose; the target is the distance the designer left between the rightmost
ink of one letter and the leftmost ink of the next, kerning included. Nothing is read
from the font being fixed: the target comes from faces that were spaced by hand.

Two things follow from the target being a distance rather than a ratio. Capitals come
out further apart than lowercase, because they are taller and the eye reads the column
of white between them, not its width alone. And a pair with a cavity comes out closer,
because the white it already holds is counted.
"""

import math

import numpy as np
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

from spacing import runs
from spacing_model import BAND, CYRILLIC, DEPTH, LETTERS, ROWS, SAMPLES, _face_features, _script

WIDE = 1.2  # of x-height, the widest gap worth telling apart: beyond it a pair is simply open
JOINT = 12  # readings of the white between the two letters kept as features


def _profile(values, count):
    if len(values) < 2:
        return np.full(count, DEPTH)
    return np.interp(np.linspace(0, len(values) - 1, count), np.arange(len(values)), values)


def sides(path, font_number=0, letters=LETTERS):
    """Each letter's facing profiles and its ink-to-advance bearings, in x-heights."""
    font = TTFont(path, fontNumber=font_number, lazy=True)
    if "glyf" not in font and "CFF " not in font:
        return None
    scale = 1000 / font["head"].unitsPerEm
    xheight = getattr(font["OS/2"], "sxHeight", 0) * scale
    if not 300 < xheight < 700:
        return None

    cmap, hmtx, glyphs = font.getBestCmap(), font["hmtx"], font.getGlyphSet()
    lean = math.tan(math.radians(-font["post"].italicAngle))
    ys = np.linspace(BAND[0] * xheight, BAND[1] * xheight, int((BAND[1] - BAND[0]) * xheight / ROWS))
    face = _face_features(font, cmap, glyphs, scale, xheight, ys)

    out = {}
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
        out[char] = {
            "right": _profile((xmax - right) / xheight, SAMPLES),  # back from the rightmost ink
            "left": _profile((left - xmin) / xheight, SAMPLES),
            "bearing": ((hmtx[name][0] * scale - xmax) / xheight, xmin / xheight),
            "height": ((ymax - ymin) / xheight, max(ymax - xheight, 0) / xheight, max(-ymin, 0) / xheight),
            "upper": float(char.isupper()), "script": _script(char),
        }
    return {"letters": out, "face": face, "xheight": xheight, "scale": scale}


def nearest(first, second):
    """How close the two letters come once their two extremes touch, in x-heights."""
    joint = np.minimum(first["right"], WIDE) + np.minimum(second["left"], WIDE)
    seen = joint[~np.isnan(joint)]
    return float(seen.min()) if len(seen) else WIDE


def features(first, second, face):
    """One pair: the two facing profiles, and the shape of the white between them.

    The profiles are measured from each letter's own extreme, so the pair is described
    with its spacing taken out — what is left is the shape of the cavity the two make,
    which is what the answer has to be a function of.
    """
    right = np.minimum(first["right"], WIDE)
    left = np.minimum(second["left"], WIDE)
    joint = right + left  # what the gap would be if their extremes touched
    seen = joint[~np.isnan(joint)]
    if not len(seen):
        seen = np.array([WIDE])
    near = seen.min() + 0.05
    where = np.linspace(0, 1, len(joint))[~np.isnan(joint)]
    return np.concatenate([
        np.nan_to_num(right, nan=WIDE), np.nan_to_num(left, nan=WIDE),
        _profile(seen, JOINT),
        [
            seen.min(), seen.mean(), np.median(seen), seen.max(),
            np.percentile(seen, 25), np.percentile(seen, 75),
            float((seen <= near).mean()),          # how much of the height is at its closest
            float(where[np.argmin(seen)]),         # and where that sits
            float(len(seen)) / len(joint),         # how much of the band both letters occupy
            float(where.min()), float(where.max()),
            float(np.abs(np.diff(seen)).mean()) if len(seen) > 1 else 0.0,
        ],
        first["height"], second["height"],
        [first["upper"], second["upper"], first["script"], second["script"]],
        face,
    ])


def extract(path, font_number=0, letters=LETTERS, kern=None, pairs=None):
    """Every ordered pair of one font's letters: its features, and the distance it was given."""
    read = sides(path, font_number, letters)
    if not read:
        return []
    if kern is None:
        from spacing import kerner
        with open(path, "rb") as handle:
            kern = kerner(handle.read())
    font = TTFont(path, fontNumber=font_number, lazy=True)
    family = font["name"].getDebugName(16) or font["name"].getDebugName(1) or path
    letters, face, xheight = read["letters"], read["face"], read["xheight"]

    rows = []
    for a, b in (pairs if pairs is not None else [(a, b) for a in letters for b in letters]):
        if a not in letters or b not in letters:
            continue
        first, second = letters[a], letters[b]
        gap = first["bearing"][0] + second["bearing"][1] + kern(a, b) * read["scale"] / xheight
        rows.append({"family": family, "pair": a + b, "xheight": xheight,
                     "target": gap + nearest(first, second),
                     "features": features(first, second, face)})
    return rows
