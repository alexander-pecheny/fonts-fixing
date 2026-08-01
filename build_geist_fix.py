# /// script
# dependencies = ["fonttools"]
# ///
"""Build 'Geist Fix' — Geist with its mark positioning switched on for Cyrillic.

Geist already anchors U+0301 over every Cyrillic vowel, but its GPOS `cyrl`
script lists only `kern`. A shaper that finds the script tag stops looking, so
the `mark` lookups never run for Russian text and the stress mark lands after
the letter. Registering `mark`/`mkmk` under `cyrl` is the whole fix.

    uv run build_geist_fix.py
"""

import glob
import os

from fontTools.ttLib import TTFont

from acutefix import enable_features, recenter_acute

YERY = (0x042B, 0x044B)  # Ы ы — Geist anchors these over the right stroke

SRC = os.path.expanduser("~/Library/Fonts/Geist/ttf/*.ttf")
DST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", "GeistFix")


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
    for src in sorted(glob.glob(SRC)):
        font = TTFont(src)
        added = enable_features(font, "cyrl")
        moved = recenter_acute(font, YERY)
        rename(font)
        out = os.path.join(DST, os.path.basename(src).replace("Geist-", "GeistFix-"))
        font.save(out)
        shifts = " ".join(f"{g} {a}→{b}" for g, a, b in moved)
        print(f"{os.path.basename(out):32s} cyrl +{','.join(added) or 'nothing'}  {shifts}")


if __name__ == "__main__":
    main()
