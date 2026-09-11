# /// script
# dependencies = ["fonttools"]
# ///
"""Build 'Inter Fix RA' — Inter Fix with the a and the 1 of Raveo.

Raveo (github.com/jakubfoglar/raveo) is a fork of Inter that redraws a with a tail
and R with a curled leg, and bakes in Inter's cv01 "1", the one without the long
flag. This takes the a and the 1 and leaves the R. Every other digit in Raveo is
Inter's to the pixel, so the digits are otherwise untouched.

Each roman face takes its two glyphs from the Raveo static of the same style name.
Raveo draws its Medium, SemiBold and Bold a step darker than Inter's, and that
darker glyph is what goes in. Cyrillic а and every accented a are composites of a
in Inter, so they follow on their own. Raveo has no italics, and Inter's italic a
is single-storey, so the italics keep Inter's a.

The 1 is baked the way Raveo does it, but through Inter's own cv01 rule rather than
by copying the glyph: that reaches the tabular, superscript and fraction forms that
Raveo never drew, so the digit reads the same in a table as in a line of text. The
romans then take Raveo's proportional 1 on top, which is that alternate redrawn.

    git clone https://github.com/jakubfoglar/raveo scratchpad/raveo
    uv run build_inter_fix_ra.py
"""

import copy
import os

from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTCollection, TTFont

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "fonts", "InterFix", "InterFix.ttc")
RAVEO = os.path.join(HERE, "scratchpad", "raveo", "fonts", "static")
DST = os.path.join(HERE, "fonts", "InterFixRA")
TAKEN = ("a", "one")


def bake(font, tag):
    """Make a one-to-one substitution feature the default form of each glyph it touches."""
    gsub, glyf, hmtx = font["GSUB"].table, font["glyf"], font["hmtx"]
    for record in gsub.FeatureList.FeatureRecord:
        if record.FeatureTag != tag:
            continue
        for index in record.Feature.LookupListIndex:
            for subtable in gsub.LookupList.Lookup[index].SubTable:
                for src, dst in getattr(subtable, "mapping", {}).items():
                    glyf[src] = copy.deepcopy(glyf[dst])
                    hmtx[src] = hmtx[dst]


def take(font, donor, name):
    """Copy a glyph out of a CFF donor, and widen whatever Inter draws on top of it."""
    glyf, hmtx = font["glyf"], font["hmtx"]
    pen = TTGlyphPen(None)
    donor.getGlyphSet()[name].draw(Cu2QuPen(pen, max_err=1.0, reverse_direction=True))
    glyph = pen.glyph()
    glyph.recalcBounds(glyf)
    delta = donor["hmtx"][name][0] - hmtx[name][0]
    glyf[name] = glyph
    hmtx[name] = (donor["hmtx"][name][0], glyph.xMin)
    for other in font.getGlyphOrder():
        composite = glyf[other]
        if composite.isComposite() and composite.components[0].glyphName == name:
            composite.recalcBounds(glyf)
            hmtx[other] = (hmtx[other][0] + delta, composite.xMin)
    return delta


def rename(font):
    name = font["name"]
    for rec in name.names:
        if rec.nameID in (1, 4, 16):
            name.setName(str(rec).replace("Inter Fix", "Inter Fix RA"), rec.nameID,
                         rec.platformID, rec.platEncID, rec.langID)
        elif rec.nameID in (3, 6):
            name.setName(str(rec).replace("InterFix", "InterFixRA"), rec.nameID,
                         rec.platformID, rec.platEncID, rec.langID)


def main():
    os.makedirs(DST, exist_ok=True)
    collection = TTCollection(SRC)
    for font in collection.fonts:
        style = font["name"].getDebugName(4).removeprefix("Inter Fix ")
        bake(font, "cv01")
        report = "cv01 baked"
        if "Italic" not in style:
            donor = TTFont(os.path.join(RAVEO, f"Raveo {style}.otf"))
            deltas = [take(font, donor, name) for name in TAKEN]
            report += "  " + "  ".join(f"{n} {d:+d}" for n, d in zip(TAKEN, deltas))
        rename(font)
        print(f"{style:24s} {report}")
    collection.save(os.path.join(DST, "InterFixRA.ttc"))


if __name__ == "__main__":
    main()
