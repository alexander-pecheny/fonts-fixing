# /// script
# dependencies = ["fonttools", "uharfbuzz", "numpy", "joblib", "scikit-learn>=1.9"]
# ///
"""Build 'Geist Fix' — Geist with Cyrillic mark positioning switched on and respaced.

Geist already anchors U+0301 over every Cyrillic vowel, but its GPOS `cyrl` script
lists only `kern`. A shaper that finds the script tag stops looking, so the `mark`
lookups never run for Russian text and the stress mark lands after the letter.
Registering `mark`/`mkmk` under `cyrl` is that fix.

The sidebearings then come from `spacing-model.joblib`, which reads them off the
outlines; see `respacing.py`. Geist draws half its Cyrillic as composites of the Latin
letter, so both scripts are respaced together and every glyph built on a moved one
follows it. A model that reads one side at a time cannot see a pair, so afterwards any
pair that was already open and has been opened further is kerned back to where the
designer left it. A last pass evens out how close the ink of a pair ever comes, which is
the reading that catches the eye in a word like играм, and is the one place here where
the designer's own kerning is overruled.

    uv run build_geist_fix.py
"""

import glob
import io
import os

import joblib
import numpy as np
from fontTools.ttLib import TTFont

from acutefix import enable_features, recenter_acute
from respacing import even, hold, respace

YERY = (0x042B, 0x044B)  # Ы ы — Geist anchors these over the right stroke

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.expanduser("~/Library/Fonts/Geist/ttf/*.ttf")
DST = os.path.join(HERE, "fonts", "GeistFix")


def rename(font):
    name = font["name"]
    for rec in name.names:
        if rec.nameID in (1, 4, 16):
            name.setName(str(rec).replace("Geist", "Geist Fix"), rec.nameID,
                         rec.platformID, rec.platEncID, rec.langID)
        elif rec.nameID in (3, 6):
            name.setName(str(rec).replace("Geist", "GeistFix"), rec.nameID,
                         rec.platformID, rec.platEncID, rec.langID)


def main():
    os.makedirs(DST, exist_ok=True)
    model = joblib.load(os.path.join(HERE, "spacing-model.joblib"))
    for src in sorted(glob.glob(SRC)):
        font = TTFont(src)
        added = enable_features(font, "cyrl")
        moves, floored, noise = respace(font, src, model)
        kerns = hold(font, src)
        current = io.BytesIO()
        font.save(current)  # the shaper has to see the kerning just added
        evened = even(font, current.getvalue())
        moved = recenter_acute(font, YERY)
        rename(font)
        out = os.path.join(DST, os.path.basename(src).replace("Geist-", "GeistFix-"))
        font.save(out)
        shifts = " ".join(f"{g} {a}→{b}" for g, a, b in moved)
        print(f"{os.path.basename(out):32s} cyrl +{','.join(added) or 'nothing'}  "
              f"{len(moves) // 2} letters, mean move {np.abs(moves).mean():.0f}, "
              f"{moves.min()}..{moves.max()}, noise {noise:.0f} subtracted, "
              f"floor held back {floored:.0f}; {len(kerns)} pairs kerned back, "
              f"{len(evened)} evened ({(evened > 0).sum()} opened), "
              f"median {np.median(evened):.0f}  {shifts}")


if __name__ == "__main__":
    main()
