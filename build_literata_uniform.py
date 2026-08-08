# /// script
# dependencies = ["fonttools", "uharfbuzz", "numpy"]
# ///
"""Build 'Literata Uniform', where every pair of letters is meant to read the same.

A reader does not measure the gap between two letters, they see how light the page
goes between them. So each pair is rasterised, blurred the way an eye blurs a page
at text size, and read at its lightest column; the kern that brings that reading to
a common level is the one this ships. Latin is treated with the Cyrillic, since
evening out one script and not the other would only move the unevenness.

How much blur is the whole question, and it decides the answer: a wide blur reports
two stems as tight because their ink bleeds into the gap, a narrow one reports the
same pair as loose. It is fitted rather than chosen — swept for the radius at which
evening out the Latin disturbs the designer's own Latin kerning least, which for
Literata is about 0.15 of the x-height.

Even there the model still disagrees with the designer by some 16 units on the
average Latin pair, so this is not a repair of anything. It is a decision to let one
measurement of evenness overrule a designer's judgement, pair by pair, and it is
worth looking at a proof before believing it. `build_literata_fix.py` is the
conservative alternative: it only carries kerning the font already has.

    uv run build_literata_uniform.py
"""

import glob
import os

import numpy as np
from fontTools.ttLib import TTFont

from spacing import add_kern_lookup, gaussian, ink_columns, kerner, trough

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.expanduser("~/Library/Fonts/Literata")
LATIN = "abcdefghijklmnopqrstuvwxyz"
CYRILLIC = "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"
BLUR = 0.15  # gaussian sigma, as a fraction of x-height
LIMIT, STEP = 40, 5  # how far a pair may be moved, and the units it is rounded to


def shapes(font, letters):
    cmap = font.getBestCmap()
    out = {}
    for char in letters:
        columns, advance = ink_columns(font, cmap[ord(char)])
        inked = np.nonzero(columns)[0]
        out[char] = (columns, advance, inked.min(), inked.max())
    return out


def uniform_kerns(font, data):
    """The kern that brings each pair to the level the font's own Latin sits at."""
    letters = LATIN + LATIN.upper() + CYRILLIC + CYRILLIC.upper()
    drawn = shapes(font, letters)
    kernel = gaussian(BLUR * font["OS/2"].sxHeight)
    kern = kerner(data)
    existing = {(a, b): kern(a, b) for a in letters for b in letters}

    def read(a, b, extra=0):
        return trough(drawn[a], drawn[b], existing[(a, b)] + extra, kernel)

    latin = LATIN + LATIN.upper()
    targets = {}
    for case in ((False, False), (False, True), (True, False), (True, True)):
        pairs = [(a, b) for a in latin for b in latin if (a.isupper(), b.isupper()) == case]
        targets[case] = float(np.median([read(a, b) for a, b in pairs]))

    out, disagreement = {}, []
    for a in letters:
        for b in letters:
            target = targets[(a.isupper(), b.isupper())]
            low, high = -LIMIT, LIMIT
            for _ in range(11):  # the trough only gets lighter as the letters separate
                middle = (low + high) / 2
                low, high = (low, middle) if read(a, b, middle) < target else (middle, high)
            value = int(round((low + high) / 2 / STEP) * STEP)
            if a in latin and b in latin:
                disagreement.append(abs(value))
            if value:
                out[(a, b)] = value
    return out, float(np.mean(disagreement))


def rename(font):
    names = font["name"]
    for record in names.names:
        if record.nameID in (1, 3, 4, 6, 16):
            joined = record.nameID in (3, 6)
            value = str(record).replace("Literata", "LiterataUniform" if joined else "Literata Uniform")
            names.setName(value, record.nameID, record.platformID, record.platEncID, record.langID)


def main():
    out = os.path.join(HERE, "fonts", "LiterataUniform")
    os.makedirs(out, exist_ok=True)
    for path in sorted(glob.glob(f"{SOURCE}/*.ttf")) + sorted(glob.glob(f"{SOURCE}/static/*.ttf")):
        font = TTFont(path)
        values, disagreement = uniform_kerns(font, open(path, "rb").read())
        cmap = font.getBestCmap()
        add_kern_lookup(font, {(cmap[ord(a)], cmap[ord(b)]): v for (a, b), v in values.items()})
        rename(font)
        name = os.path.basename(path).replace("Literata", "LiterataUniform")
        font.save(os.path.join(out, name))

        moves = np.array(list(values.values()))
        print(f"{name:36s} {len(values):5d} pairs, {(moves < 0).sum()} tighter, {(moves > 0).sum()} looser, "
              f"disagreement with the latin {disagreement:.0f}")


if __name__ == "__main__":
    main()
