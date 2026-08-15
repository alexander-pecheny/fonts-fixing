# /// script
# dependencies = ["fonttools"]
# ///
"""Build 'Spectral Fix': a working Russian stress mark and the old curly quotes.

Spectral 2.005 anchors U+0301 over а е и о у and every lowercase vowel but ё, and
leaves Ё Ы Э Ю Я out, so a stress mark over those capitals lands past the letter.
It also draws `acutecomb.case`, a flatter acute for capitals, and uses it inside
its own Á — but nothing selects it for a typed combining acute, so even the
capitals it does anchor carry the mark 45 units too high. Its ю anchor sits on
the crossbar rather than the bowl, so ю and Ю are recentered.

Version 2.005 also replaced the comma and the comma-shaped quotes with wedges
(https://github.com/productiontype/Spectral/issues/28). The 2.001 outlines drop
straight back in: the advance widths are unchanged, and the rest of the family —
“ ” ‚ „ ʻ ʼ, the comma-accent letters, the small-cap quotes — is composites.

    uv run build_spectral_fix.py
"""

import copy
import os
import shutil
import urllib.request

from fontTools.ttLib import TTFont
from fontTools.ttLib.tables import ttProgram

from acutefix import add_acute_anchors, bowl_center, case_acute_after_capitals, recenter_acute

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "scratchpad", "spectral")
URL = "https://raw.githubusercontent.com/google/fonts/{ref}/ofl/spectral/{name}"
CURRENT = "main"
CURLY = "68de4ebfd9"  # v2.001, the last release drawn with commas rather than wedges
CURLS = [0x2C, 0x3B, 0x312, 0x326, 0x2018, 0x2019]  # , ; ̒ ̦ ‘ ’
WEIGHTS = ["ExtraLight", "Light", "Regular", "Medium", "SemiBold", "Bold", "ExtraBold"]
STYLES = WEIGHTS + [w.replace("Regular", "") + "Italic" for w in WEIGHTS]


def source(ref, name):
    path = os.path.join(CACHE, ref, name)
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        urllib.request.urlretrieve(URL.format(ref=ref, name=name), path)
    return path


def restore_curls(font, donor):
    """Take back the 2.001 outlines of every comma the font draws, minus their hinting.

    The semicolon comes too, because it sets its comma 27 units to the left to
    sit under the wedge's narrower waist.
    """
    ours, theirs = font.getBestCmap(), {g: cp for cp, g in donor.getBestCmap().items()}
    for cp in CURLS:
        name, was = ours[cp], donor.getBestCmap()[cp]
        glyph = copy.deepcopy(donor["glyf"][was])
        glyph.program = ttProgram.Program()
        for component in glyph.components if glyph.isComposite() else []:
            component.glyphName = ours[theirs[component.glyphName]]
        font["glyf"][name] = glyph
        font["hmtx"][name] = (font["hmtx"][name][0], donor["hmtx"][was][1])


def rename(font):
    name = font["name"]
    for rec in name.names:
        if rec.nameID in (1, 4, 16):
            value = str(rec).replace("Spectral", "Spectral Fix", 1)
        elif rec.nameID in (3, 6):
            value = str(rec).replace("Spectral", "SpectralFix")
        else:
            continue
        name.setName(value, rec.nameID, rec.platformID, rec.platEncID, rec.langID)


def main():
    dst = os.path.join(HERE, "fonts", "SpectralFix")
    os.makedirs(dst, exist_ok=True)
    shutil.copy(source(CURRENT, "OFL.txt"), dst)
    for style in sorted(STYLES):
        font = TTFont(source(CURRENT, f"Spectral-{style}.ttf"))
        restore_curls(font, TTFont(source(CURLY, f"Spectral-{style}.ttf")))
        anchors = add_acute_anchors(font, point_at_center=False, extra_marks=["acutecomb.case"])
        recenter_acute(font, [0x042E, 0x044E], bowl_center)
        capitals = case_acute_after_capitals(font, "acutecomb.case")
        rename(font)
        out = os.path.join(dst, f"SpectralFix-{style}.ttf")
        font.save(out)
        print(f"{os.path.basename(out):34s} anchors +{' '.join(anchors)}, {len(capitals)} capitals")


if __name__ == "__main__":
    main()
