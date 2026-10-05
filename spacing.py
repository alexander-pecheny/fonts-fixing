"""The geometry both models and every pass stand on: where a glyph has ink, and kerning.

`outline` flattens a glyph once and `filled` cuts it along one scanline by nonzero
winding. `runs` and `scan` read a side off those cuts, `sector_columns` reads the ink
per column the blurred page in `build_literata_uniform.py` is made of. `kerner` asks a
shaper what a font already kerns, and `add_kern_lookup` adds to it.
"""

import numpy as np
from fontTools.pens.basePen import BasePen
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.ttLib.tables import otTables as ot

BAND = (-220, 760)  # vertical range a pair is read over, descenders included
PIXEL = 5  # units per column when a glyph is rasterised


class FlattenPen(BasePen):
    """Collects contours as polylines, subdividing curves into `steps` segments."""

    def __init__(self, glyphSet, steps=12):
        super().__init__(glyphSet)
        self.steps, self.polygons, self.current = steps, [], None

    def _moveTo(self, point):
        self.current = [point]

    def _lineTo(self, point):
        self.current.append(point)

    def _curveToOne(self, p1, p2, p3):
        p0 = self.current[-1]
        for t in self._ts():
            u = 1 - t
            self.current.append(
                tuple(
                    u**3 * a + 3 * u * u * t * b + 3 * u * t * t * c + t**3 * d
                    for a, b, c, d in zip(p0, p1, p2, p3)
                )
            )

    def _qCurveToOne(self, p1, p2):
        p0 = self.current[-1]
        for t in self._ts():
            u = 1 - t
            self.current.append(
                tuple(u * u * a + 2 * u * t * b + t * t * c for a, b, c in zip(p0, p1, p2))
            )

    def _ts(self):
        return [i / self.steps for i in range(1, self.steps + 1)]

    def _closePath(self):
        if self.current:
            self.polygons.append(self.current)
            self.current = None

    _endPath = _closePath


def outline(font, glyph_name):
    """The glyph's contours, components decomposed and curves flattened to polylines."""
    glyphs = font.getGlyphSet()
    record = DecomposingRecordingPen(glyphs)
    glyphs[glyph_name].draw(record)
    pen = FlattenPen(glyphs)
    record.replay(pen)
    pen._closePath()
    return [polygon for polygon in pen.polygons if len(polygon) > 2]


def filled(polygons, y):
    """The intervals of a scanline that are ink, by nonzero winding, left to right.

    Overlapping contours can split one run of ink into two that touch; they come back
    as two intervals, and `runs` is where they are joined.
    """
    crossings = []
    for polygon in polygons:
        points = polygon + [polygon[0]]
        for (x0, y0), (x1, y1) in zip(points, points[1:]):
            if (y0 <= y < y1) or (y1 <= y < y0):
                crossings.append((x0 + (x1 - x0) * (y - y0) / (y1 - y0), 1 if y1 > y0 else -1))
    crossings.sort()
    winding, out = 0, []
    for (start, direction), (end, _) in zip(crossings, crossings[1:]):
        winding += direction
        if winding:
            out.append((start, end))
    return out


def _fill(columns, spans, pixel):
    for start, end in spans:
        columns[max(int(start / pixel), 0) : max(int(end / pixel), 0)] += 1


def runs(font, glyph_name, ys):
    """The ink intervals at each scanline, by nonzero winding: [[(start, end), ...], ...].

    What is between the extremes matters as much as where they are — a wire-thin serif
    and a slab put their edge in the same place — so the interior crossings are kept.
    """
    polygons, out = outline(font, glyph_name), []
    for y in ys:
        spans = []
        for start, end in filled(polygons, y):
            if end <= start:
                continue
            if spans and start - spans[-1][1] < 0.5:  # overlapping contours split a run in two
                spans[-1] = (spans[-1][0], end)
            else:
                spans.append((start, end))
        out.append(spans)
    return out


def scan(font, glyph_name, ys):
    """Rightmost and leftmost ink at each y, nan where the glyph has none."""
    right, left = np.full(len(ys), np.nan), np.full(len(ys), np.nan)
    for i, spans in enumerate(runs(font, glyph_name, ys)):
        if spans:
            right[i], left[i] = spans[-1][1], spans[0][0]
    return right, left


def sector_columns(font, glyph_name, sectors, band=BAND, pixel=PIXEL):
    """Ink per column, kept separately for each horizontal band of the glyph.

    Collapsing a glyph's whole height into one profile lets a capital's shoulders
    fill the gap beside a lowercase letter; keeping the bands apart does not.
    """
    polygons = outline(font, glyph_name)
    edges = np.linspace(band[0], band[1], sectors + 1)
    out = np.zeros((sectors, int(font["hmtx"][glyph_name][0] / pixel) + 4))
    for index in range(sectors):
        for y in np.arange(edges[index], edges[index + 1], pixel):
            _fill(out[index], filled(polygons, y), pixel)
    return out


def gaussian(sigma, pixel=PIXEL):
    x = np.arange(-int(3 * sigma / pixel), int(3 * sigma / pixel) + 1) * pixel
    kernel = np.exp(-0.5 * (x / sigma) ** 2)
    return kernel / kernel.sum()


def kerner(data):
    """Returns the kerning a shaper already applies to a pair, in font units."""
    import uharfbuzz as hb  # only shaping needs it; the geometry here does not

    font = hb.Font(hb.Face(data))

    def kern(a, b):
        def total(on):
            buf = hb.Buffer()
            buf.add_str(a + b)
            buf.guess_segment_properties()
            hb.shape(font, buf, {"kern": on})
            return sum(g.x_advance for g in buf.glyph_positions)

        return total(True) - total(False)

    return kern


def add_kern_lookup(font, pairs):
    """Append a kern lookup; its values add to whatever the font already applies."""
    if not pairs:
        return 0
    gpos = font["GPOS"].table
    gid = {name: i for i, name in enumerate(font.getGlyphOrder())}
    seconds = {}
    for (a, b), value in pairs.items():
        seconds.setdefault(a, []).append((b, value))

    pair_pos = ot.PairPos()
    pair_pos.Format, pair_pos.ValueFormat1, pair_pos.ValueFormat2 = 1, 0x0004, 0
    pair_pos.Coverage = ot.Coverage()
    pair_pos.Coverage.glyphs = sorted(seconds, key=gid.get)
    pair_pos.PairSet = []
    for first in pair_pos.Coverage.glyphs:
        pair_set = ot.PairSet()
        pair_set.PairValueRecord = []
        for second, value in sorted(seconds[first], key=lambda pair: gid[pair[0]]):
            record = ot.PairValueRecord()
            record.SecondGlyph, record.Value2 = second, None
            record.Value1 = ot.ValueRecord()
            record.Value1.XAdvance = value
            pair_set.PairValueRecord.append(record)
        pair_set.PairValueCount = len(pair_set.PairValueRecord)
        pair_pos.PairSet.append(pair_set)
    pair_pos.PairSetCount = len(pair_pos.PairSet)

    extension = ot.ExtensionPos()
    extension.Format, extension.ExtensionLookupType, extension.ExtSubTable = 1, 2, pair_pos
    lookup = ot.Lookup()
    lookup.LookupType, lookup.LookupFlag = 9, 0
    lookup.SubTable, lookup.SubTableCount = [extension], 1
    gpos.LookupList.Lookup.append(lookup)
    index = len(gpos.LookupList.Lookup) - 1
    gpos.LookupList.LookupCount = index + 1

    for record in gpos.FeatureList.FeatureRecord:
        if record.FeatureTag == "kern":
            record.Feature.LookupListIndex.append(index)
            record.Feature.LookupCount = len(record.Feature.LookupListIndex)
    return len(pairs)
