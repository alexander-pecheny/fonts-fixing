# /// script
# dependencies = ["fonttools"]
# ///
"""Build 'IBM Plex Sans Fix' and 'IBM Plex Serif Fix' with a working Russian stress mark.

Plex registers `mark` under `cyrl` and anchors most Cyrillic vowels, but leaves
Ё, Э, Ю and Я out of the mark-to-base coverage, so a combining acute after any
of them lands past the letter.

Plex draws its acute so that the designer's own anchors already read right, so
the added letters keep the font's mark anchor rather than the pointing-tip one.

    uv run build_ibm_plex_fix.py
"""

import glob
import os

from fontTools.ttLib import TTFont

from acutefix import add_acute_anchors
from naming import rename_family

HERE = os.path.dirname(os.path.abspath(__file__))
FAMILIES = ["Sans", "Serif"]


def main():
    for family in FAMILIES:
        dst = os.path.join(HERE, "fonts", f"IBMPlex{family}Fix")
        os.makedirs(dst, exist_ok=True)
        src = os.path.expanduser(f"~/Library/Fonts/ibm-plex-{family.lower()}/fonts/complete/ttf/*.ttf")
        for path in sorted(glob.glob(src)):
            font = TTFont(path)
            anchors = add_acute_anchors(font, point_at_center=False)
            rename_family(font, f"IBM Plex {family}", f"IBM Plex {family} Fix")
            stem = os.path.basename(path).replace(f"IBMPlex{family}-", f"IBMPlex{family}Fix-")
            out = os.path.join(dst, stem)
            font.save(out)
            print(f"{os.path.basename(out):36s} anchors +{' '.join(anchors) or '0'}")


if __name__ == "__main__":
    main()
