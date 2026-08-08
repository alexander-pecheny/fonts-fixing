# /// script
# dependencies = ["fonttools", "uharfbuzz", "numpy"]
# ///
"""Build 'Literata Uniform' by squinting at the page it sets and evening it out.

Every earlier attempt here scored a pair on its own and lost, because a pair scored
in isolation is not what a reader looks at. This scores the composed line instead:
the document's own words are set with the font, the line is blurred the way an eye
blurs a page, and the light between each pair of letters is measured in context,
with its neighbours bleeding in. Even spacing means those readings come out alike,
so the spread across a page is the score and the kerns are walked down until it
stops falling.

Which reading of the light matters was settled by trying three of them against
fonts already judged by eye. How dark the gap stays and how much light it holds
both rank a visibly clumping font as the best of the bunch; how *wide* the light
runs ranks them the way a reader does. Clumping is variation in the width of the
white, not in its depth.

The walk overshoots if it is taken at full stride, since neighbouring gaps pull on
each other through the blur, so it is damped and the best round is kept. Only pairs
the corpus actually contains are touched, which makes this a font tuned for a text
rather than a font in general.

    uv run build_literata_uniform.py --text some-document.md
"""

import argparse
import glob
import os
import re

import numpy as np
from fontTools.ttLib import TTFont

from spacing import add_kern_lookup, gaussian, kerner, sector_columns

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.expanduser("~/Library/Fonts/Literata")
PIXEL, SECTORS, BLUR = 5, 12, 0.22  # blur as a fraction of x-height
RATE, ROUNDS, LIMIT, STEP = 0.25, 8, 60, 5
LEVEL = 60  # the page counts as light below this percentile of its own density

# The optimiser reads a dense pair as too tight, because a round letter meeting a
# recessed stem never lets the blurred line go light between them. These three were
# called wrong by eye, so they are set by eye; everything else is measured.
HAND = {("о", "р"): -10, ("а", "р"): -10, ("о", "в"): -15}


def corpus(path, limit=600):
    text = re.sub(r"<[^>]*>|`[^`]*`|https?://\S+", " ", open(path).read())
    return re.findall(r"[А-Яа-яЁёA-Za-z]{3,}", text)[:limit]


def evener(font, data, words):
    """Measure every gap the corpus contains, and walk the kerns until they agree."""
    cmap, hmtx = font.getBestCmap(), font["hmtx"]
    kernel = gaussian(BLUR * font["OS/2"].sxHeight, PIXEL)
    kern = kerner(data)

    letters = {c for word in words for c in word if ord(c) in cmap}
    stacks = {c: sector_columns(font, cmap[ord(c)], SECTORS, pixel=PIXEL) for c in letters}
    widths = {c: hmtx[cmap[ord(c)]][0] for c in letters}
    existing = {}

    def measure(deltas):
        """Every gap in the corpus: which pair it is, and how wide its light runs."""
        gaps, densities = [], []
        for word in words:
            chars = [c for c in word if c in letters]
            if len(chars) < 2:
                continue
            pen, spans = 0, []
            for index, char in enumerate(chars):
                if index:
                    pair = (chars[index - 1], char)
                    existing.setdefault(pair, kern(*pair))
                    pen += existing[pair] + deltas.get(pair, 0)
                spans.append((int(pen / PIXEL) + 20, stacks[char]))
                pen += widths[char]
            line = np.zeros((SECTORS, int(pen / PIXEL) + 60))
            for start, stack in spans:
                line[:, start : start + stack.shape[1]] += stack
            density = np.convolve(line.sum(axis=0), kernel, mode="same")
            densities.append(density)
            for index in range(1, len(chars)):
                left = spans[index - 1][0] + spans[index - 1][1].shape[1]
                lo, hi = sorted((left, spans[index][0]))
                gaps.append(((chars[index - 1], chars[index]), density[max(lo - 6, 0) : hi + 6]))
        if not hasattr(measure, "level"):
            measure.level = float(np.percentile(np.concatenate([d[d > 0] for d in densities]), LEVEL))
        return [(pair, float((w < measure.level).sum() * PIXEL)) for pair, w in gaps if len(w)]

    deltas = {}
    seen = measure(deltas)
    score = lambda rows: float(np.std([w for _, w in rows]) / np.mean([w for _, w in rows]))
    best = (score(seen), dict(deltas), )
    start = best[0]

    for _ in range(ROUNDS):
        by_pair = {}
        for pair, width in seen:
            by_pair.setdefault(pair, []).append(width)
        target = float(np.mean([w for _, w in seen]))
        for pair, found in by_pair.items():
            move = -(float(np.mean(found)) - target) * RATE
            deltas[pair] = float(np.clip(deltas.get(pair, 0) + move, -LIMIT, LIMIT))
        seen = measure(deltas)
        if score(seen) < best[0]:
            best = (score(seen), dict(deltas))

    values = {pair: int(round(value / STEP) * STEP) for pair, value in best[1].items()}
    values.update(HAND)
    return {pair: value for pair, value in values.items() if value}, start, best[0]


def rename(font):
    names = font["name"]
    for record in names.names:
        if record.nameID in (1, 3, 4, 6, 16):
            joined = record.nameID in (3, 6)
            value = str(record).replace("Literata", "LiterataUniform" if joined else "Literata Uniform")
            names.setName(value, record.nameID, record.platformID, record.platEncID, record.langID)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--text", required=True, help="document whose words the font is evened out on")
    args = parser.parse_args()

    words = corpus(args.text)
    out = os.path.join(HERE, "fonts", "LiterataUniform")
    os.makedirs(out, exist_ok=True)
    for path in sorted(glob.glob(f"{SOURCE}/*.ttf")) + sorted(glob.glob(f"{SOURCE}/static/*.ttf")):
        font = TTFont(path)
        values, before, after = evener(font, open(path, "rb").read(), words)
        cmap = font.getBestCmap()
        add_kern_lookup(font, {(cmap[ord(a)], cmap[ord(b)]): v for (a, b), v in values.items()})
        rename(font)
        name = os.path.basename(path).replace("Literata", "LiterataUniform")
        font.save(os.path.join(out, name))
        moves = np.array(list(values.values()))
        print(f"{name:36s} spread {before:.3f} -> {after:.3f}   {len(values)} pairs, "
              f"median {np.median(moves):+.0f}, {moves.min()}..{moves.max()}")


if __name__ == "__main__":
    main()
