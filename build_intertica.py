# /// script
# dependencies = ["fonttools", "uharfbuzz"]
# ///
"""Build 'Intertica' — Inter Fix RA redrawn to fill the space Arial fills.

A document set in Arial and re-set in Inter runs 7.8% longer in Russian and 7.5%
longer in English, so it reflows: lines break elsewhere, a table widens, a page turns
into two. Nothing about the letters is wrong, they are simply drawn wider on the em.
The em is a free choice, so this build changes it and nothing else — every outline,
sidebearing, kern and anchor scaled by 1902/2048, which is 0.9287, with the em left at
2048. No point ends up more than half a unit off an exact scale, so the shapes are the
ones Inter draws; they stand 7.1% smaller in the em and the line comes out the length
Arial's does.

The factor is the one that makes a paragraph measure what Arial measures. Fitted on
running text with its spaces and punctuation, since a space is 0.278 em in Arial
against 0.281 in Inter while a letter is 8.7% wider: it is the mix that has to match,
not the alphabet. Russian and English ask for 0.9276 and 0.9301 independently, and
0.9287 is where the two paragraphs together land, within 0.2% of each.

It is fitted on the Regular alone, which is what body text is made of. Inter's Bold
widens over its Regular 4.3% less than Arial's does — in stock Inter as much as here,
so it is Inter's drawing and not this repository's spacing — and no single family-wide
factor serves both. Splitting the difference was tried and dropped: it leaves a bold
run inside a paragraph set at a visibly different size from the text around it, which
is a worse fault than a heading 4% short. So the Bold comes out 4% narrower than
Arial's and the Bold Italic 5%, while the Italic lands within 2%.

The Display faces take the same factor rather than their own. Inter Display already
measures within 1.6% of Arial unscaled, so fitting it would ask for no change at all —
but Display shares Inter's cap height by design, and scaling one cut and not the other
would make the display faces draw 9.4% larger than the text faces at the same size. The
family holds together instead; the Display faces run 8.6% narrow against Arial, which
is a cut for headlines rather than for setting an Arial document in.

Vertical metrics are Arial's own, read off the file: hhea, OS/2 typographic and OS/2
win, all three, with `USE_TYPO_METRICS` cleared as Arial leaves it. Renderers disagree
about which set to read and copying all of them is how they are made to agree. The
default line comes to 1.1499 em where Inter asks for 1.2100. Typst is the exception and
none of it reaches it: its default line spacing is the leading plus the cap height, so
a line there follows the outlines and comes out 3.0% tighter than Arial's. A document
that needs the page to break where Arial breaks it can say `#set par(leading: 0.69em)`.

What the fit costs is size on the page. At the same point size the cap falls from 1490
units to 1384 against Arial's 1467 and the x-height from 1118 to 1038 against 1062, so
Intertica reads 5.7% smaller than Arial by its capitals and 2.3% by its lowercase, and
takes the same room.

    uv run build_inter_fix_ra.py && uv run build_intertica.py
"""

import io
import os
import shutil

import uharfbuzz as hb
from fontTools.ttLib import TTCollection, TTFont
from fontTools.ttLib.scaleUpem import scale_upem

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "fonts", "InterFixRA", "InterFixRA.ttc")
DST = os.path.join(HERE, "fonts", "Intertica")
ARIAL = "/System/Library/Fonts/Supplemental/Arial{}.ttf"
UPEM, SCALED = 2048, 1902
VERTICAL = ("sTypoAscender", "sTypoDescender", "sTypoLineGap", "usWinAscent", "usWinDescent")
USE_TYPO_METRICS = 1 << 7

RU = ("Все счастливые семьи похожи друг на друга, каждая несчастливая семья несчастлива "
      "по-своему. Всё смешалось в доме Облонских. Жена узнала, что муж был в связи с бывшею "
      "в их доме француженкою-гувернанткой, и объявила мужу, что не может жить с ним в одном "
      "доме. Положение это продолжалось уже третий день и мучительно чувствовалось и самими "
      "супругами. Цена 1250 рублей, скидка 15% с 3 июля.")
EN = ("It is a truth universally acknowledged, that a single man in possession of a good "
      "fortune, must be in want of a wife. However little known the feelings or views of such "
      "a man may be on his first entering a neighbourhood, this truth is so well fixed in the "
      "minds of the surrounding families. Chapter 12, page 348, printed 1813.")


def measure(font, text):
    """Width of a line of text in ems, shaped as a shaper would shape it."""
    buffer = io.BytesIO()
    font.save(buffer)
    face = hb.Face(buffer.getvalue())
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(hb.Font(face), buf, {"kern": True, "liga": True})
    return sum(p.x_advance for p in buf.glyph_positions) / face.upem


def rescale(font):
    scale_upem(font, SCALED)
    font["head"].unitsPerEm = UPEM


def vertical(font, arial):
    hhea, source = font["hhea"], arial["hhea"]
    hhea.ascender, hhea.descender, hhea.lineGap = source.ascender, source.descender, source.lineGap
    os2, source = font["OS/2"], arial["OS/2"]
    for field in VERTICAL:
        setattr(os2, field, getattr(source, field))
    os2.fsSelection &= ~USE_TYPO_METRICS


def rename(font):
    name = font["name"]
    for rec in name.names:
        if rec.nameID in (1, 3, 4, 6, 16):
            renamed = str(rec).replace("Inter Fix RA", "Intertica").replace("InterFixRA", "Intertica")
            name.setName(renamed, rec.nameID, rec.platformID, rec.platEncID, rec.langID)


def main():
    os.makedirs(DST, exist_ok=True)
    arial = {style: TTFont(ARIAL.format("" if style == "Regular" else " " + style))
             for style in ("Regular", "Bold", "Italic", "Bold Italic")}
    assert all(font["head"].unitsPerEm == UPEM for font in arial.values())
    target = {style: (measure(font, RU), measure(font, EN)) for style, font in arial.items()}
    collection = TTCollection(SRC)
    for font in collection.fonts:
        style = font["name"].getDebugName(4).removeprefix("Inter Fix RA")
        rescale(font)
        vertical(font, arial["Regular"])
        rename(font)
        report = ""
        if style.strip() in target:
            want = target[style.strip()]
            got = (measure(font, RU), measure(font, EN))
            report = "  vs Arial: ru %+.1f%%  en %+.1f%%" % tuple(
                100 * (g / w - 1) for g, w in zip(got, want))
        print(f"Intertica{style:26s}{report}", flush=True)
    collection.save(os.path.join(DST, "Intertica.ttc"))
    shutil.copy(os.path.join(os.path.dirname(SRC), "OFL.txt"), DST)


if __name__ == "__main__":
    main()
