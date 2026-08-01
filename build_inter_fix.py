# /// script
# dependencies = ["fonttools"]
# ///
"""Build 'Inter Fix' — the Inter collection with a working Russian stress mark.

Inter has both faults at once: its GPOS `cyrl` script lists only `kern`, so the
mark positioning it does have never runs for Russian; and Ю and я are the two
vowels it never anchored. Everything else keeps the designer's own anchors.

    uv run build_inter_fix.py
"""

import os

from fontTools.ttLib import TTCollection

from acutefix import add_acute_anchors, enable_features

SRC = os.path.expanduser("~/Library/Fonts/Inter.ttc")
DST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", "InterFix")


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
    collection = TTCollection(SRC)
    for font in collection.fonts:
        added = enable_features(font, "cyrl")
        anchors = add_acute_anchors(font)
        style = font["name"].getDebugName(4)
        rename(font)
        print(f"{style:32s} cyrl +{','.join(added) or 'nothing'}  anchors +{' '.join(anchors) or '0'}")
    collection.save(os.path.join(DST, "InterFix.ttc"))


if __name__ == "__main__":
    main()
