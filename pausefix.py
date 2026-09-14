"""Draw U+23F8, the pause sign, for a font that has the rest of the media controls.

Inter carries ▶ U+25B6, ■ U+25A0 and ⏏ U+23CF and no pause, so a player's buttons
cannot be set in one face. The substitute, ‖ U+2016, is a text sign: two hairlines at
stem weight, which next to a solid triangle reads as a gap in the row.

So the sign is drawn from the two the face already has, and nothing here is a number
chosen by hand. The play triangle gives the proportion — bars a quarter of its width
hold the ink it holds — and the stop square gives the box: its height, its baseline,
its advance, and in an italic its shear, since Inter slants these symbols with the
letters. Scaling the bars onto that box leaves them at 64% of the triangle's ink, which
is what the eye wants: two bars separated by white read heavier than one solid shape of
the same area. Inter Regular comes out at 317 units to a bar of 2048, Black at 332,
because Inter grows its play triangle by 5% across the weights and leaves its square
alone, and the pause follows the pair rather than the letters.
"""

from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.ttGlyphPen import TTGlyphPen

PLAY, STOP, PAUSE = 0x25B6, 0x25A0, 0x23F8


def _corners(glyphs, name):
    pen = DecomposingRecordingPen(glyphs)
    glyphs[name].draw(pen)
    return [point for _, args in pen.value for point in args]


def add_pause(font):
    """Add U+23F8 to `font`, and return the width of one bar in font units."""
    cmap, glyphs = font.getBestCmap(), font.getGlyphSet()
    if PAUSE in cmap or PLAY not in cmap or STOP not in cmap:
        return 0
    square = _corners(glyphs, cmap[STOP])
    floor, ceiling = min(y for _, y in square), max(y for _, y in square)
    height = ceiling - floor
    slant = (min(x for x, y in square if y == ceiling)
             - min(x for x, y in square if y == floor)) / height
    flat = lambda points: [x - slant * y for x, y in points]
    left, right = min(flat(square)), max(flat(square))
    play = _corners(glyphs, cmap[PLAY])
    tall = max(y for _, y in play) - min(y for _, y in play)
    bar = round((max(flat(play)) - min(flat(play))) / 4 * height / tall)

    pen = TTGlyphPen(None)
    start = left + (right - left - 3 * bar) / 2
    for x in (start, start + 2 * bar):
        low, high = x + slant * floor, x + slant * ceiling
        pen.moveTo((low, floor))  # clockwise, as TrueType wants an outer contour
        pen.lineTo((high, ceiling))
        pen.lineTo((high + bar, ceiling))
        pen.lineTo((low + bar, floor))
        pen.closePath()
    glyph = pen.glyph()
    glyph.recalcBounds(font["glyf"])

    name = "uni23F8"
    font.setGlyphOrder(list(font.getGlyphOrder()) + [name])
    font["glyf"].glyphs[name] = glyph
    font["hmtx"].metrics[name] = (font["hmtx"][cmap[STOP]][0], glyph.xMin)
    for table in font["cmap"].tables:
        table.cmap[PAUSE] = name
    font["maxp"].numGlyphs = len(font.getGlyphOrder())
    return bar
