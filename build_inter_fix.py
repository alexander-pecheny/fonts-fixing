# /// script
# dependencies = ["fonttools", "uharfbuzz", "numpy", "joblib", "scikit-learn>=1.9"]
# ///
"""Build 'Inter Fix' — the Inter collection with a working Russian stress mark, respaced.

Inter has both faults at once: its GPOS `cyrl` script lists only `kern`, so the
mark positioning it does have never runs for Russian; and Ю and я are the two
vowels it never anchored. Everything else keeps the designer's own anchors.

The sidebearings and the kerning then come from the two models; see `respacing.py`.
Inter draws much of its Cyrillic as composites of the Latin letter, so both scripts
are respaced together and every glyph built on a moved one follows it.

    uv run build_inter_fix.py
"""

import os

import joblib
from fontTools.ttLib import TTCollection

from acutefix import add_acute_anchors, enable_features
from respacing import space, summary

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.expanduser("~/Library/Fonts/Inter.ttc")
DST = os.path.join(HERE, "fonts", "InterFix")


def fix(font):
    """Inter's own two faults: `cyrl` listing only `kern`, and Ю and я never anchored."""
    return enable_features(font, "cyrl"), add_acute_anchors(font)


def rename(font):
    name = font["name"]
    for rec in name.names:
        if rec.nameID in (1, 4, 16):
            name.setName(str(rec).replace("Inter", "Inter Fix"), rec.nameID,
                         rec.platformID, rec.platEncID, rec.langID)
        elif rec.nameID in (3, 6):
            name.setName(str(rec).replace("Inter", "InterFix"), rec.nameID,
                         rec.platformID, rec.platEncID, rec.langID)


def main():
    os.makedirs(DST, exist_ok=True)
    model = joblib.load(os.path.join(HERE, "spacing-model.joblib"))
    pairs = joblib.load(os.path.join(HERE, "pair-model.joblib"))
    collection = TTCollection(SRC)
    for font in collection.fonts:
        added, anchors = fix(font)
        stats = space(font, model, pairs)
        style = font["name"].getDebugName(4)
        rename(font)
        print(f"{style:32s} cyrl +{','.join(added) or 'nothing'}  "
              f"anchors +{' '.join(anchors) or '0'}  {summary(stats)}", flush=True)
    collection.save(os.path.join(DST, "InterFix.ttc"))


if __name__ == "__main__":
    main()
