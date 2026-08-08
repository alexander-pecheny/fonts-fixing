# /// script
# dependencies = ["fonttools", "uharfbuzz", "numpy"]
# ///
"""Build 'Literata Uniform', where every pair of letters is meant to read the same.

A reader does not measure the gap between two letters, they see how light the page
goes between them. So each pair is rasterised, blurred the way an eye blurs a page
at text size, and read at its lightest column; the kern that brings that reading to
a common level is the one this ships. Blurring commutes with summing down the
columns, so a pair is only ever two shifted column profiles added together.

How much blur is the whole question, because it decides the answer: a wide blur
reports two stems as tight, their ink bleeding into the gap, and a narrow one
reports the same pair as loose. It cannot honestly be fitted. Asking which radius
disturbs the designer's own Latin kerning least rewards a model that proposes
nothing, and duly bottoms out at the smallest radius offered; asking which radius
makes the designer's Latin read most uniformly rewards blurring the page to mush,
and falls all the way to the largest. The sweep below is the first of those, so it
picks the cautious end and this build moves little. It is still run per face, which
at least stops a heavy weight inheriting a light one's figure: lending the Regular's
0.15 to the Bold had it pulling отб together twice as hard as the Bold asks.

Blur alone will happily push two letters until they touch, because thin ink reads
light however close it is. So no pair may end up with less clearance than the font
already allows somewhere: the floor is the tightest fit found among the designer's
own pairs, and the kern is capped at it. Without that, ал collided — a pair Literata
had deliberately opened by 10 units.

Even so the model disagrees with the designer by some 15 units on the average Latin
pair, and the fitted minimum is shallow. This is not a repair of anything: it is a
decision to let one measurement of evenness overrule a designer, pair by pair.
`build_literata_fix.py` is the conservative alternative.

    uv run build_literata_uniform.py
"""

import glob
import os

import numpy as np
from fontTools.ttLib import TTFont

from spacing import BAND, STEP, add_kern_lookup, gaussian, ink_columns, kerner, scan, trough

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.expanduser("~/Library/Fonts/Literata")
LATIN = "abcdefghijklmnopqrstuvwxyz"
CYRILLIC = "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"
RADII = (0.08, 0.10, 0.12, 0.15, 0.20)  # gaussian sigma to try, as fractions of x-height
CLEARANCE = 2  # percentile of the font's own pair clearances taken as the floor
LIMIT, ROUND = 40, 5  # how far a pair may be moved, and the units it is rounded to


def columns(font, letters):
    """Ink per column of each letter, with the ends of its ink noted."""
    cmap = font.getBestCmap()
    out = {}
    for char in letters:
        ink, advance = ink_columns(font, cmap[ord(char)])
        inked = np.nonzero(ink)[0]
        out[char] = (ink, advance, inked.min(), inked.max())
    return out


def edges(font, letters):
    """How far the ink stands back from each edge, scanline by scanline."""
    cmap, hmtx = font.getBestCmap(), font["hmtx"]
    ys = np.arange(*BAND, STEP)
    out = {}
    for char in letters:
        right, left = scan(font, cmap[ord(char)], ys)
        out[char] = (hmtx[cmap[ord(char)]][0] - right, left)
    return out


def uniform_kerns(font, data):
    letters = LATIN + LATIN.upper() + CYRILLIC + CYRILLIC.upper()
    latin = LATIN + LATIN.upper()
    drawn, sides = columns(font, letters), edges(font, letters)
    kern = kerner(data)
    existing = {(a, b): kern(a, b) for a in letters for b in letters}

    def clearance(a, b):
        """Narrowest ink-to-ink gap the pair has as the font sets it today."""
        gap = sides[a][0] + sides[b][1] + existing[(a, b)]
        both = gap[~np.isnan(gap)]
        return both.min() if len(both) else np.inf

    room = {pair: clearance(*pair) for pair in existing}
    floor = np.percentile([v for v in room.values() if np.isfinite(v)], CLEARANCE)

    def solve(a, b, kernel, target):
        low, high = -LIMIT, LIMIT
        for _ in range(11):  # the trough only gets lighter as the letters separate
            middle = (low + high) / 2
            reading = trough(drawn[a], drawn[b], existing[(a, b)] + middle, kernel)
            low, high = (low, middle) if reading < target else (middle, high)
        value = int(round((low + high) / 2 / ROUND) * ROUND)
        return max(value, int(np.ceil((floor - room[(a, b)]) / ROUND)) * ROUND)

    def pass_over(fraction, pairs):
        kernel = gaussian(fraction * font["OS/2"].sxHeight)
        targets = {}
        for case in ((False, False), (False, True), (True, False), (True, True)):
            readings = [trough(drawn[a], drawn[b], existing[(a, b)], kernel)
                        for a in latin for b in latin if (a.isupper(), b.isupper()) == case]
            targets[case] = float(np.median(readings))
        return {(a, b): solve(a, b, kernel, targets[(a.isupper(), b.isupper())]) for a, b in pairs}

    latin_pairs = [(a, b) for a in latin for b in latin]
    fits = {fraction: pass_over(fraction, latin_pairs) for fraction in RADII}
    scores = {f: np.mean(np.abs(list(values.values()))) for f, values in fits.items()}
    best = min(scores, key=scores.get)

    values = pass_over(best, [(a, b) for a in letters for b in letters])
    return {pair: v for pair, v in values.items() if v}, best, scores[best], floor


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
        values, blur, disagreement, floor = uniform_kerns(font, open(path, "rb").read())
        cmap = font.getBestCmap()
        add_kern_lookup(font, {(cmap[ord(a)], cmap[ord(b)]): v for (a, b), v in values.items()})
        rename(font)
        name = os.path.basename(path).replace("Literata", "LiterataUniform")
        font.save(os.path.join(out, name))

        moves = np.array(list(values.values()))
        print(f"{name:36s} blur {blur:.2f}  floor {floor:3.0f}  {len(values):5d} pairs, "
              f"{(moves < 0).sum()} tighter, {(moves > 0).sum()} looser, latin off by {disagreement:.0f}")


if __name__ == "__main__":
    main()
