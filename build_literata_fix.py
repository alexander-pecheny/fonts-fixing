# /// script
# dependencies = ["fonttools", "uharfbuzz", "numpy"]
# ///
"""Build 'Literata Fix', carrying Literata's Latin kerning across to its Cyrillic.

The two scripts are drawn from the same parts. Cyrillic О is the Latin O outline
with the same metrics, н is built of the stems of n, Р of P — and where a pair of
letters is shared, Literata spaces it identically. What is not shared is the
kerning: the font kerns about a third of its Latin pairs and half as many
Cyrillic ones, so РО keeps a gap that PO does not.

So each Cyrillic letter's left and right profile is matched to the nearest Latin
one, and a pair inherits whatever the designer did to the Latin pair behind it.
Nothing is invented and nothing is loosened: the fix only closes gaps the font
already closes elsewhere. Letters with no Latin analogue — ъ and ь on the left,
Ч on the right of its arm — fall outside the tolerance and are left alone.

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

from spacing import add_kern_lookup, kerner, scan

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.expanduser("~/Library/Fonts/Literata")
LATIN = "abcdefghijklmnopqrstuvwxyz"
CYRILLIC = "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"
TOLERANCE = 40  # mean units two profiles may differ by and still count as the same shape
BANDS = {False: 520, True: 710}  # how far up to compare, by case


def profiles(font, chars, top):
    """Ink set back from each edge at every scanline, with the empty rows filled in flat."""
    cmap, hmtx = font.getBestCmap(), font["hmtx"]
    ys = np.arange(0, top, 10)
    out = {}
    for char in chars:
        right, left = scan(font, cmap[ord(char)], ys)
        advance = hmtx[cmap[ord(char)]][0]
        out[char] = (np.nan_to_num(advance - right, nan=advance), np.nan_to_num(left, nan=0.0))
    return out


def twins(font):
    """For each Cyrillic side, the Latin letter drawn like it and how far off it is."""
    out = {}
    for upper, top in BANDS.items():
        latin = LATIN.upper() if upper else LATIN
        cyrillic = CYRILLIC.upper() if upper else CYRILLIC
        shapes = profiles(font, latin + cyrillic, top)
        for char in cyrillic:
            for side in (0, 1):
                distances = {l: np.abs(shapes[char][side] - shapes[l][side]).mean() for l in latin}
                match = min(distances, key=distances.get)
                out[(char, side)] = (match, distances[match])
    return out


def adjustments(font, data):
    """Kerning each Cyrillic pair is missing relative to the Latin pair it is drawn like."""
    kern = kerner(data)
    matched = twins(font)
    alike = {key: name for key, (name, distance) in matched.items() if distance <= TOLERANCE}

    out = {}
    letters = CYRILLIC + CYRILLIC.upper()
    for a in letters:
        for b in letters:
            if (a, 0) not in alike or (b, 1) not in alike:
                continue
            value = kern(alike[(a, 0)], alike[(b, 1)]) - kern(a, b)
            if value <= -5:
                out[(a, b)] = int(round(value / 5) * 5)
    return out, matched


def report(path, values):
    """What the transfer does to the letter pairs a given document actually uses."""
    text = re.sub(r"<[^>]*>|`[^`]*`|https?://\S+", " ", open(path).read())
    counts = collections.Counter()
    for word in re.findall(r"[А-Яа-яЁё]+", text):
        for pair in zip(word, word[1:]):
            counts[pair] += 1
    touched = {pair: count for pair, count in counts.items() if pair in values}
    print(f"\n{os.path.basename(path)}: {sum(touched.values())} of {sum(counts.values())} letter "
          f"pairs kerned, {len(touched)} of {len(counts)} distinct")
    for pair, count in sorted(touched.items(), key=lambda item: -item[1])[:10]:
        print(f"  {''.join(pair)}  {count:5d}  {values[pair]:+3d}")


def rename(font):
    names = font["name"]
    for record in names.names:
        if record.nameID in (1, 3, 4, 6, 16):
            joined = record.nameID in (3, 6)
            value = str(record).replace("Literata", "LiterataFix" if joined else "Literata Fix")
            names.setName(value, record.nameID, record.platformID, record.platEncID, record.langID)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--text", help="document whose letter pairs to report on")
    args = parser.parse_args()

    out = os.path.join(HERE, "fonts", "LiterataFix")
    os.makedirs(out, exist_ok=True)
    for path in sorted(glob.glob(f"{SOURCE}/*.ttf")) + sorted(glob.glob(f"{SOURCE}/static/*.ttf")):
        font = TTFont(path)
        values, matched = adjustments(font, open(path, "rb").read())
        cmap = font.getBestCmap()
        add_kern_lookup(font, {(cmap[ord(a)], cmap[ord(b)]): v for (a, b), v in values.items()})
        rename(font)
        name = os.path.basename(path).replace("Literata", "LiterataFix")
        font.save(os.path.join(out, name))

        skipped = sorted({c for (c, _), (_, d) in matched.items() if d > TOLERANCE})
        print(f"{name:32s} {len(values)} pairs, median {np.median(list(values.values())):.0f}"
              f"  no latin match: {''.join(skipped)}")
        if args.text and "static/Literata-Regular" in path:
            report(args.text, values)


if __name__ == "__main__":
    main()
