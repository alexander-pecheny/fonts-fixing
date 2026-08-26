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
from spacing import BAND, add_kern_lookup, kerner, scan
from spacing_model import LETTERS, centred, extract

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(HERE, "scratchpad", "jost")
FONTS = os.path.join(HERE, "fonts")
UPSTREAM = "https://raw.githubusercontent.com/google/fonts/main/ofl/jost"
TEXT = "Здесь будет сайт ЧР по интеллектуальным играм"
CYRILLIC = "абвгдежзийклмнопрстуфхцчшщъыьэюяАБВГДЕЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯЁё"
ROWS = 10  # units between the scanlines a pair is checked on
FLOOR = 2  # percentile of the font's own approaches that nothing may go under
ROUNDS = 20
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


def respace(font, path, model):
    """Move each Cyrillic letter's sidebearings to what the model reads off its outline.

    The model earns that on the romans, where it reproduces Jost's own Latin to 6 units.
    On the italics it is off by 14, and asking it there cut У and Ч so far that letters
    ran into each other.

    Both scripts are respaced together. Jost draws Cyrillic р as Latin p and а as Latin a,
    and had spaced ра exactly as pa; moving one script alone pulled them apart, which is
    what opened ра by sixteen units. Nothing measured on a side can see that, because
    nothing is wrong with either side. Treating the two alike is the whole fix.

    Seven units is also what it cannot tell apart, and a pair collects two sides, so
    every pair carries fifteen units of noise the model has no opinion about. That is
    the size of the complaints: ра opened by sixteen, though Jost had drawn it exactly
    as its own pa, while every move worth having — д by forty, Ч by thirty —
    was several times larger. So each proposal has the model's error on this face's own
    Latin subtracted from it. Small moves vanish, large ones survive nearly whole, and
    the italics shrink twice as far as the romans because that is how much worse the
    model is on them.

    What is left is held to a floor, since Ч and У in the italic were cut far enough to
    run into the letter before. No pair may end up nearer than the font's own tightest
    fit, or than it already was, which keeps the ё that sits under Т's arm.
    """
    latin = extract(path)
    centre, tracking = centred(latin)  # the font's own Latin tracking, which stays
    unit = latin[0]["xheight"] * font["head"].unitsPerEm / 1000
    noise = float(np.abs(centre - model.predict(np.array([row["features"] for row in latin]))).mean()) * unit

    rows = extract(path, letters=LETTERS + CYRILLIC)
    wanted = model.predict(np.array([row["features"] for row in rows])) + tracking
    sides = {}
    for row, value in zip(rows, wanted):
        move = (value - row["target"]) * unit
        sides.setdefault(row["char"], {})[row["side"]] = np.sign(move) * max(abs(move) - noise, 0)
    letters = [char for char, both in sorted(sides.items()) if len(both) == 2]

    proposed = [np.array([sides[c][side] for c in letters]) for side in (0, 1)]

    kern = kerner(open(path, "rb").read())
    room = clearances(font, kern, letters)
    floor = np.minimum(np.percentile(room[np.isfinite(room)], FLOOR), room)
    right, left = (part.copy() for part in proposed)
    for _ in range(ROUNDS):
        short = floor - (room + right[:, None] + left[None, :])
        if short.max() <= 0.5:
            break
        right += np.clip(short.max(axis=1), 0, None) / 2
        left += np.clip(short.max(axis=0), 0, None) / 2
    held = float(np.mean([np.abs(part - was).mean() for part, was in zip((right, left), proposed)]))

    cmap, glyf, hmtx, moves = font.getBestCmap(), font["glyf"], font["hmtx"], []
    for index, char in enumerate(letters):
        glyph_name = cmap[ord(char)]
        glyph, advance = glyf[glyph_name], hmtx[glyph_name][0]
        wants = (round(glyph.xMin + left[index]), round(advance - glyph.xMax + right[index]))
        moves += [wants[0] - glyph.xMin, wants[1] - (advance - glyph.xMax)]
        glyph.coordinates.translate((wants[0] - glyph.xMin, 0))
        glyph.recalcBounds(glyf)
        hmtx[glyph_name] = (glyph.xMax + wants[1], wants[0])

    return np.array(moves), held, noise


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
