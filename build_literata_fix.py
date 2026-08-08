# /// script
# dependencies = ["fonttools", "uharfbuzz", "numpy"]
# ///
"""Build 'Literata Fix', a Literata whose Cyrillic keeps an even rhythm.

Literata spaces its Cyrillic consistently — an additive model of the white channel
between letters fits the whole alphabet to within a few units — but it sets the
flat-sided majority of the script much wider than its round letters. Words like
ОСЧР or вопросов come out with visible holes where a stem meets a stem or a bowl,
while the round pairs beside them read tight.

So this loosens nothing and tightens the widest channels part of the way towards
the quarter of pairs the font already sets tightest, leaving anything at or below
that mark alone. No sidebearing moves — the whole adjustment is kerning, which is
undone by turning the feature off, though tighter words do set fewer lines.

    uv run build_literata_fix.py
    uv run build_literata_fix.py --text some-document.md
"""

import argparse
import collections
import glob
import os
import re

import numpy as np
from fontTools.ttLib import TTFont

from spacing import add_kern_lookup, channels

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.expanduser("~/Library/Fonts/Literata")
LOWER = "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"
UPPER = LOWER.upper()

TARGET = 25  # percentile of channel widths each group of pairs is pulled towards
STRENGTH = 0.6  # how much of the distance to that mark a pair actually travels
LIMIT, STEP = -30, 5  # tightest allowed adjustment, and the units it is rounded to


def adjustments(font, data):
    """Kerning to add to each Cyrillic pair set looser than its own group's target."""
    measured = channels(font, data, LOWER + UPPER)
    groups = collections.defaultdict(dict)
    for pair, width in measured.items():
        groups[tuple(c.isupper() for c in pair)][pair] = width

    out = {}
    for pairs in groups.values():
        target = np.percentile(list(pairs.values()), TARGET)
        for pair, width in pairs.items():
            value = int(round(min(0.0, (target - width) * STRENGTH) / STEP) * STEP)
            if value <= -STEP:
                out[pair] = max(value, LIMIT)
    return out


def report(path, values):
    """What the adjustment does to the letter pairs a given document actually uses."""
    text = re.sub(r"<[^>]*>|`[^`]*`|https?://\S+", " ", open(path).read())
    counts = collections.Counter()
    for word in re.findall(r"[А-Яа-яЁё]+", text):
        for pair in zip(word, word[1:]):
            counts[pair] += 1
    touched = {pair: count for pair, count in counts.items() if pair in values}
    print(f"\n{os.path.basename(path)}: {sum(touched.values())} of {sum(counts.values())} "
          f"letter pairs tightened, {len(touched)} of {len(counts)} distinct")
    for pair, count in sorted(touched.items(), key=lambda item: -item[1])[:12]:
        print(f"  {''.join(pair)}  {count:5d}  {values[pair]:+3d}")


def rename(font):
    names = font["name"]
    for record in names.names:
        if record.nameID in (1, 3, 4, 6, 16):
            value = str(record).replace("Literata", "LiterataFix" if record.nameID in (3, 6) else "Literata Fix")
            names.setName(value, record.nameID, record.platformID, record.platEncID, record.langID)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--text", help="document whose letter pairs to report on")
    args = parser.parse_args()

    out = os.path.join(HERE, "fonts", "LiterataFix")
    os.makedirs(out, exist_ok=True)
    sources = sorted(glob.glob(f"{SOURCE}/*.ttf")) + sorted(glob.glob(f"{SOURCE}/static/*.ttf"))
    for path in sources:
        font = TTFont(path)
        data = open(path, "rb").read()
        values = adjustments(font, data)
        cmap = font.getBestCmap()
        added = add_kern_lookup(font, {(cmap[ord(a)], cmap[ord(b)]): v for (a, b), v in values.items()})
        rename(font)
        name = os.path.basename(path).replace("Literata", "LiterataFix")
        font.save(os.path.join(out, name))
        print(f"{name:32s} {added} pairs, median {np.median(list(values.values())):.0f}")
        if args.text and "static/Literata-Regular" in path:
            report(args.text, values)


if __name__ == "__main__":
    main()
