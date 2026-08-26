# /// script
# dependencies = ["fonttools", "uharfbuzz", "numpy", "joblib", "scikit-learn>=1.9"]
# ///
"""Set one Cyrillic line in Jost three ways: as drawn, kerned even, and respaced.

Jost kerns its Cyrillic about as much as its Latin, so neither method here is
repairing neglect. That makes it a fair test of what each one proposes on its own.

Jost Uniform is `build_literata_uniform.py`'s optimiser pointed at Jost: the line is
set, blurred the way an eye blurs a page, and the kerns walked until the light
between letters runs an even width. Only the pairs the line contains are touched.

Jost Spaced asks `spacing-model.joblib` — trained on the Latin of the fonts macOS
ships and on nothing Cyrillic — what sidebearing each Cyrillic outline calls for.
The model reproduces Jost's own Latin to 7 units, so its Cyrillic is worth reading.
Advances move; the kerning is left alone.

    uv run build_jost_variants.py
    typst compile --font-path fonts jost-sample.typ scratchpad/jost/jost-sample.pdf
"""

import os
import re
import shutil
import urllib.parse
import urllib.request

import joblib
import numpy as np
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

from build_literata_uniform import evener
from spacing import add_kern_lookup
from spacing_model import centred, extract

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(HERE, "scratchpad", "jost")
FONTS = os.path.join(HERE, "fonts")
UPSTREAM = "https://raw.githubusercontent.com/google/fonts/main/ofl/jost"
TEXT = "Здесь будет сайт ЧР по интеллектуальным играм"
CYRILLIC = "абвгдежзийклмнопрстуфхцчшщъыьэюяАБВГДЕЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯЁё"


def source():
    """The upstream variable font, instanced at Regular and kept for comparison."""
    os.makedirs(WORK, exist_ok=True)
    for name in ("Jost[wght].ttf", "OFL.txt"):
        if not os.path.exists(os.path.join(WORK, name)):
            urllib.request.urlretrieve(f"{UPSTREAM}/{urllib.parse.quote(name)}", os.path.join(WORK, name))
    variable = TTFont(os.path.join(WORK, "Jost[wght].ttf"))
    path = os.path.join(FONTS, "Jost", "Jost-Regular.ttf")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    shutil.copy(os.path.join(WORK, "OFL.txt"), os.path.dirname(path))
    instancer.instantiateVariableFont(variable, {"wght": 400}, updateFontNames=True).save(path)
    return path


def publish(font, family):
    """Save under a family name of its own, with the licence the upstream carries."""
    for record in font["name"].names:
        if record.nameID in (1, 3, 4, 6, 16):
            joined = record.nameID in (3, 6)
            value = str(record).replace("Jost", family.replace(" ", "") if joined else family)
            font["name"].setName(value, record.nameID, record.platformID, record.platEncID, record.langID)
    folder = os.path.join(FONTS, family.replace(" ", ""))
    os.makedirs(folder, exist_ok=True)
    shutil.copy(os.path.join(WORK, "OFL.txt"), folder)
    font.save(os.path.join(folder, f"{family.replace(' ', '')}-Regular.ttf"))


def respace(font, path, model):
    """Move each Cyrillic letter's sidebearings to what the model reads off its outline."""
    _, tracking = centred(extract(path))  # the font's own Latin tracking, which stays
    rows = extract(path, letters=CYRILLIC)
    unit = rows[0]["xheight"] * font["head"].unitsPerEm / 1000
    wanted = model.predict(np.array([row["features"] for row in rows])) + tracking

    sides = {}
    for row, value in zip(rows, wanted):
        sides.setdefault(row["char"], {})[row["side"]] = value * unit

    cmap, glyf, hmtx, moves = font.getBestCmap(), font["glyf"], font["hmtx"], []
    for char, both in sorted(sides.items()):
        if len(both) < 2:
            continue
        name = cmap[ord(char)]
        glyph, advance = glyf[name], hmtx[name][0]
        left, right = round(both[1]), round(both[0])
        moves += [left - glyph.xMin, right - (advance - glyph.xMax)]
        glyph.coordinates.translate((left - glyph.xMin, 0))
        glyph.recalcBounds(glyf)
        hmtx[name] = (glyph.xMax + right, left)
    return np.array(moves)


def main():
    path = source()
    words = re.findall(r"[А-Яа-яЁё]+", TEXT)

    font = TTFont(path)
    values, before, after = evener(font, open(path, "rb").read(), words)
    cmap = font.getBestCmap()
    add_kern_lookup(font, {(cmap[ord(a)], cmap[ord(b)]): v for (a, b), v in values.items()})
    publish(font, "Jost Uniform")
    moves = np.array(list(values.values()))
    print(f"Jost Uniform   spread {before:.3f} -> {after:.3f}, {len(values)} pairs, "
          f"median {np.median(moves):+.0f}, {moves.min()}..{moves.max()}")

    font = TTFont(path)
    moves = respace(font, path, joblib.load(os.path.join(HERE, "spacing-model.joblib")))
    publish(font, "Jost Spaced")
    print(f"Jost Spaced    {len(moves) // 2} letters respaced, median {np.median(moves):+.0f}, "
          f"mean move {np.abs(moves).mean():.0f}, {moves.min()}..{moves.max()}")


if __name__ == "__main__":
    main()
