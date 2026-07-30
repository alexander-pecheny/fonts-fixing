# /// script
# dependencies = ["fonttools"]
# ///
"""Build 'Roboto Flex Fix' — static RIBBI instances of Roboto Flex with Cyrillic acute anchors.

Two problems with using Roboto Flex for Russian typesetting, both fixed here:
its mark-to-base lookup covers no Cyrillic glyph, so U+0301 lands after the
letter; and typst ignores variable axes, so every weight renders as Regular.

    uv run build_roboto_flex_fix.py
"""

import os

from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

from acutefix import add_acute_anchors

SRC = os.path.expanduser(
    "~/Library/Fonts/RobotoFlex[GRAD,XOPQ,XTRA,YOPQ,YTAS,YTDE,YTFI,YTLC,YTUC,opsz,slnt,wdth,wght].ttf"
)
DST = os.path.expanduser("~/Library/Fonts/RobotoFlexFix")
FAMILY = "Roboto Flex Fix"
PSFAMILY = "RobotoFlexFix"

STYLES = [
    ("Regular", {"wght": 400, "slnt": 0}, 400, False),
    ("Italic", {"wght": 400, "slnt": -10}, 400, True),
    ("Bold", {"wght": 700, "slnt": 0}, 700, False),
    ("Bold Italic", {"wght": 700, "slnt": -10}, 700, True),
]


def rename(font, style, weight, italic):
    ps = f"{PSFAMILY}-{style.replace(' ', '')}"
    full = FAMILY if style == "Regular" else f"{FAMILY} {style}"
    strings = {1: FAMILY, 2: style, 3: f"{ps};acutefix", 4: full, 6: ps, 16: FAMILY, 17: style}
    name = font["name"]
    for nid, value in strings.items():
        name.setName(value, nid, 3, 1, 0x409)
        name.setName(value, nid, 1, 0, 0)
    for nid in (18, 20, 21, 22, 25):
        name.removeNames(nameID=nid)
    os2 = font["OS/2"]
    os2.usWeightClass = weight
    bits = (1 if italic else 0) | (0b100000 if weight >= 700 else 0)
    if not bits:
        bits = 0b1000000  # REGULAR
    os2.fsSelection = (os2.fsSelection & ~0b1100001) | bits
    font["head"].macStyle = (1 if weight >= 700 else 0) | (2 if italic else 0)
    font["post"].italicAngle = -10.0 if italic else 0.0


def main():
    os.makedirs(DST, exist_ok=True)
    for style, coords, weight, italic in STYLES:
        font = TTFont(SRC)
        axes = {a.axisTag: a.defaultValue for a in font["fvar"].axes}
        axes.update(coords)
        instancer.instantiateVariableFont(font, axes, inplace=True, updateFontNames=False)
        added = add_acute_anchors(font)
        rename(font, style, weight, italic)
        out = os.path.join(DST, f"{PSFAMILY}-{style.replace(' ', '')}.ttf")
        font.save(out)
        print(f"{os.path.basename(out):32s} acute anchors +{len(added)}")


if __name__ == "__main__":
    main()
