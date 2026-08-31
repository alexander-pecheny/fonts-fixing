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
It knows Jost's own Latin to 6 units, so its Cyrillic is worth reading. Both scripts
are respaced together; the kerning is left alone.

Spaced is built for all four styles, from the two variable fonts upstream ships.
Uniform is built for the Regular alone, since it is tuned to the one line the sample sets.

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
from respacing import respace
from spacing import add_kern_lookup

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(HERE, "scratchpad", "jost")
FONTS = os.path.join(HERE, "fonts")
UPSTREAM = "https://raw.githubusercontent.com/google/fonts/main/ofl/jost"
TEXT = "Здесь будет сайт ЧР по интеллектуальным играм"
STYLES = (("Regular", "Jost[wght].ttf", 400), ("Bold", "Jost[wght].ttf", 700),
          ("Italic", "Jost-Italic[wght].ttf", 400), ("BoldItalic", "Jost-Italic[wght].ttf", 700))


def source():
    """The upstream variable fonts, instanced to four statics and kept for comparison."""
    os.makedirs(WORK, exist_ok=True)
    for upstream in ("Jost[wght].ttf", "Jost-Italic[wght].ttf", "OFL.txt"):
        if not os.path.exists(os.path.join(WORK, upstream)):
            urllib.request.urlretrieve(f"{UPSTREAM}/{urllib.parse.quote(upstream)}", os.path.join(WORK, upstream))
    folder = os.path.join(FONTS, "Jost")
    os.makedirs(folder, exist_ok=True)
    shutil.copy(os.path.join(WORK, "OFL.txt"), folder)
    for style, variable, weight in STYLES:
        font = instancer.instantiateVariableFont(TTFont(os.path.join(WORK, variable)), {"wght": weight})
        yield style, publish(font, "Jost", style, folder)


def publish(font, family, style, folder):
    """Name a face properly and save it; instancing leaves the family name behind."""
    spaced = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", style)
    records = {1: family, 2: spaced, 3: f"{family} {spaced} 1.000", 4: f"{family} {spaced}",
               6: f"{family.replace(' ', '')}-{style}", 16: None, 17: None}
    for record in list(font["name"].names):
        if record.nameID in records:
            font["name"].removeNames(record.nameID)
    for identifier, value in records.items():
        if value:
            font["name"].setName(value, identifier, 3, 1, 0x409)
    path = os.path.join(folder, f"{family.replace(' ', '')}-{style}.ttf")
    font.save(path)
    return path


def main():
    words = re.findall(r"[А-Яа-яЁё]+", TEXT)
    model = joblib.load(os.path.join(HERE, "spacing-model.joblib"))
    for family in ("Jost Uniform", "Jost Spaced"):
        folder = os.path.join(FONTS, family.replace(" ", ""))
        os.makedirs(folder, exist_ok=True)
        shutil.copy(os.path.join(WORK, "OFL.txt"), folder)

    for style, path in source():
        font = TTFont(path)
        moves, held, noise = respace(font, path, model)
        publish(font, "Jost Spaced", style, os.path.join(FONTS, "JostSpaced"))
        print(f"Jost Spaced  {style:11s} {len(moves) // 2} letters, median {np.median(moves):+.0f}, "
              f"mean move {np.abs(moves).mean():.0f}, {moves.min()}..{moves.max()}, "
              f"noise {noise:.0f} subtracted, floor held back {held:.0f}")

        if style != "Regular":  # the optimiser is tuned to one line, which the sample sets once
            continue
        font = TTFont(path)
        values, before, after = evener(font, open(path, "rb").read(), words)
        cmap = font.getBestCmap()
        add_kern_lookup(font, {(cmap[ord(a)], cmap[ord(b)]): v for (a, b), v in values.items()})
        publish(font, "Jost Uniform", style, os.path.join(FONTS, "JostUniform"))
        moves = np.array(list(values.values()))
        print(f"Jost Uniform {style:11s} spread {before:.3f} -> {after:.3f}, {len(values)} pairs, "
              f"median {np.median(moves):+.0f}, {moves.min()}..{moves.max()}")


if __name__ == "__main__":
    main()
