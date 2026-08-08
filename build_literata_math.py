# /// script
# dependencies = ["fonttools"]
# ///
"""Build 'Literata Math', a math font with Literata's letters and STIX Two Math's symbols.

Literata has no MATH table, so a document set in it falls back to some other
face for formulas. STIX Two Math has the table, the symbols and the glyph
variants, but its letters are STIX's. This script keeps STIX's machinery and
redraws every letter and digit it has in common with Literata.

STIX runs 7% smaller than Literata, so the whole donor font is scaled to put the
two x-heights on the same line before any letter is swapped in.

STIX draws a second, sturdier set of letters for superscript and subscript size
and switches to them through the `ssty` feature. Literata says the same thing
with its optical size axis, so those variants are drawn at opsz 7 instead.

    uv run build_literata_math.py
"""

import os
import unicodedata

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.reverseContourPen import ReverseContourPen
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables import otTables
from fontTools.ttLib.scaleUpem import scale_upem
from fontTools.varLib import instancer

HERE = os.path.dirname(os.path.abspath(__file__))
STIX = os.path.expanduser("~/Library/Fonts/STIX/STIXTwoMath-Regular.otf")
LITERATA = os.path.expanduser("~/Library/Fonts/Literata/Literata%s[opsz,wght].ttf")
TEXT_SIZE, SCRIPT_SIZE = 12, 7
STYLES = {"Regular": ("", 400), "Italic": ("-Italic", 400), "Bold": ("", 700), "BoldItalic": ("-Italic", 700)}

UPRIGHT = [(0x30, 0x39), (0x41, 0x5A), (0x61, 0x7A), (0x391, 0x3A9), (0x3B1, 0x3C9), (0x400, 0x45F)]

# Math alphanumerics whose style Literata can draw; the rest of plane 1 (script,
# fraktur, double-struck, sans, mono) stays STIX's.
ALPHANUMERICS = [
    (0x1D400, 0x1D433, "Bold"),
    (0x1D434, 0x1D467, "Italic"),
    (0x1D468, 0x1D49B, "BoldItalic"),
    (0x1D6A8, 0x1D6E1, "Bold"),
    (0x1D6E2, 0x1D71B, "Italic"),
    (0x1D71C, 0x1D755, "BoldItalic"),
    (0x1D7CE, 0x1D7D7, "Bold"),
]


def sources(size):
    return {
        style: instancer.instantiateVariableFont(TTFont(LITERATA % slope), {"wght": weight, "opsz": size})
        for style, (slope, weight) in STYLES.items()
    }


def wanted(stix, fonts):
    """Codepoint -> (style, codepoint in that style) for everything Literata can redraw."""
    out = {}
    for first, last in UPRIGHT:
        out.update({cp: ("Regular", cp) for cp in range(first, last + 1)})
    for first, last, style in ALPHANUMERICS:
        for cp in range(first, last + 1):
            base = unicodedata.decomposition(chr(cp)).split()
            if base:
                out[cp] = (style, int(base[-1], 16))
    out[0x210E] = ("Italic", ord("h"))  # planck constant, the math italic h

    stix_cmap = stix.getBestCmap()
    return {
        cp: (style, base)
        for cp, (style, base) in sorted(out.items())
        if cp in stix_cmap and base in fonts[style].getBestCmap()
    }


def scale_math_lengths(font, factor):
    """Scale the MATH lengths that `scale_upem` leaves alone: it only knows the value
    records, and misses the raw design units in the constants and the glyph variants."""
    math = font["MATH"].table
    for attr in ("DelimitedSubFormulaMinHeight", "DisplayOperatorMinHeight"):
        setattr(math.MathConstants, attr, round(getattr(math.MathConstants, attr) * factor))

    variants = math.MathVariants
    variants.MinConnectorOverlap = round(variants.MinConnectorOverlap * factor)
    constructions = (variants.VertGlyphConstruction or []) + (variants.HorizGlyphConstruction or [])
    for construction in constructions:
        for variant in construction.MathGlyphVariantRecord:
            variant.AdvanceMeasurement = round(variant.AdvanceMeasurement * factor)
        assembly = construction.GlyphAssembly
        for part in assembly.PartRecords if assembly else []:
            for attr in ("StartConnectorLength", "EndConnectorLength", "FullAdvance"):
                setattr(part, attr, round(getattr(part, attr) * factor))


def redraw(stix, source, src_name, dst_name):
    """Replace one STIX glyph with a Literata one, taking its advance width along."""
    glyphs = source.getGlyphSet()
    width = round(glyphs[src_name].width)

    record = DecomposingRecordingPen(glyphs)
    glyphs[src_name].draw(record)
    bounds = BoundsPen(None)
    record.replay(bounds)

    cff = stix["CFF "].cff[stix["CFF "].cff.fontNames[0]]
    pen = T2CharStringPen(width, None)
    record.replay(ReverseContourPen(pen))  # TrueType winds its contours the other way
    cff.CharStrings[dst_name] = pen.getCharString(cff.Private)

    stix["hmtx"][dst_name] = (width, stix["hmtx"][dst_name][1])
    return width, bounds.bounds


def value_record(value):
    record = otTables.MathValueRecord()
    record.Value, record.DeviceTable = value, None
    return record


def set_italic_corrections(stix, corrections):
    """Literata slants less than STIX but overshoots further on letters like italic f, so
    the donor's corrections say nothing about the new outlines. Remeasure them instead."""
    info = stix["MATH"].table.MathGlyphInfo.MathItalicsCorrectionInfo
    values = dict(zip(info.Coverage.glyphs, (record.Value for record in info.ItalicsCorrection)))
    values.update(corrections)

    order = {name: i for i, name in enumerate(stix.getGlyphOrder())}
    info.Coverage.glyphs = sorted(values, key=order.get)
    info.ItalicsCorrection = [value_record(values[name]) for name in info.Coverage.glyphs]
    info.ItalicsCorrectionCount = len(info.ItalicsCorrection)


def drop_math_kerns(stix, names):
    """STIX kerns a letter's corners against its own scripts; those numbers describe
    STIX's shapes, so a redrawn letter is better off with its italic correction alone."""
    kerns = stix["MATH"].table.MathGlyphInfo.MathKernInfo
    keep = [(g, r) for g, r in zip(kerns.MathKernCoverage.glyphs, kerns.MathKernInfoRecords) if g not in names]
    kerns.MathKernCoverage.glyphs = [g for g, _ in keep]
    kerns.MathKernInfoRecords = [r for _, r in keep]
    kerns.MathKernCount = len(keep)


def set_top_accents(stix, centers):
    """STIX puts the attachment point right of centre by as much as its italics lean;
    on an upright Literata letter that hangs the accent off the side. Centre it."""
    accents = stix["MATH"].table.MathGlyphInfo.MathTopAccentAttachment
    for name, center in centers.items():
        if name in accents.TopAccentCoverage.glyphs:
            accents.TopAccentAttachment[accents.TopAccentCoverage.glyphs.index(name)].Value = center


def rename(font, version):
    names = [
        (0, "Literata is copyright 2017 The Literata Project Authors. STIX Two Math is "
            "copyright 2001-2021 The STIX Fonts Project Authors. Both under the SIL Open Font License."),
        (1, "Literata Math"),
        (2, "Regular"),
        (3, f"{version};LiterataMath-Regular"),
        (4, "Literata Math"),
        (5, f"Version {version}"),
        (6, "LiterataMath-Regular"),
        (16, "Literata Math"),
        (17, "Regular"),
    ]
    table = font["name"]
    table.names = [rec for rec in table.names if rec.nameID not in {n for n, _ in names} | {18, 20, 21, 22}]
    for name_id, value in names:
        table.setName(value, name_id, 3, 1, 0x409)
        table.setName(value, name_id, 1, 0, 0)


def main():
    stix = TTFont(STIX)
    fonts = sources(TEXT_SIZE)
    script = sources(SCRIPT_SIZE)

    upem = stix["head"].unitsPerEm
    grow = round(upem * fonts["Regular"]["OS/2"].sxHeight / stix["OS/2"].sxHeight) / upem
    scale_upem(stix, round(upem * grow))
    scale_math_lengths(stix, grow)
    stix["head"].unitsPerEm = upem

    stix_cmap = stix.getBestCmap()
    glyphs = set(stix.getGlyphOrder())
    corrections, centers = {}, {}
    for cp, (style, base) in wanted(stix, fonts).items():
        src_name = fonts[style].getBestCmap()[base]
        dst_name = stix_cmap[cp]
        for source, name in ((fonts[style], dst_name), (script[style], f"{dst_name}.ssty")):
            if name not in glyphs:
                continue
            width, bounds = redraw(stix, source, src_name, name)
            if bounds:
                corrections[name] = max(0, round(bounds[2] - width))
                centers[name] = round((bounds[0] + bounds[2]) / 2)

    set_italic_corrections(stix, corrections)
    set_top_accents(stix, centers)
    drop_math_kerns(stix, set(corrections))

    rename(stix, "1.000")
    out = os.path.join(HERE, "fonts", "LiterataMath")
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, "LiterataMath-Regular.otf")
    stix.save(path)
    print(f"{os.path.basename(path)}: {len(corrections)} glyphs from Literata, STIX scaled by {grow:.4f}")


if __name__ == "__main__":
    main()
