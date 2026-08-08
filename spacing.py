"""How wide the white channel between two glyphs reads, and how to kern it shut.

Sidebearings say very little about that in a serif face: a stem sits far back from
the advance and only its serifs reach out, so two flat-sided letters keep a channel
two or three times wider than their sidebearings suggest. What the eye judges is
closer to the narrowest part of the channel, so pairs are measured with a soft
minimum over the scanlines where both letters have ink.
"""

import numpy as np
import uharfbuzz as hb
from fontTools.pens.basePen import BasePen
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.ttLib.tables import otTables as ot

STEP = 20  # units between scanlines
FLOOR = 20.0  # a channel never reads tighter than this, whatever the outlines do
SOFTNESS = -2  # power-mean exponent: the more negative, the more the narrowest part counts
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


def scan(font, glyph_name, ys):
    """Rightmost and leftmost ink at each y, nan where the glyph has none."""
    glyphs = font.getGlyphSet()
    record = DecomposingRecordingPen(glyphs)
    glyphs[glyph_name].draw(record)
    pen = FlattenPen(glyphs)
    record.replay(pen)
    pen._closePath()

    right, left = np.full(len(ys), np.nan), np.full(len(ys), np.nan)
    for i, y in enumerate(ys):
        crossings = []
        for polygon in (p for p in pen.polygons if len(p) > 2):
            points = polygon + [polygon[0]]
            for (x0, y0), (x1, y1) in zip(points, points[1:]):
                if (y0 <= y < y1) or (y1 <= y < y0):
                    crossings.append(x0 + (x1 - x0) * (y - y0) / (y1 - y0))
        if crossings:
            right[i], left[i] = max(crossings), min(crossings)
    return right, left


def ink_columns(font, glyph_name, band=BAND, pixel=PIXEL):
    """Ink area per column of the glyph, laid out from its origin."""
    glyphs = font.getGlyphSet()
    record = DecomposingRecordingPen(glyphs)
    glyphs[glyph_name].draw(record)
    pen = FlattenPen(glyphs)
    record.replay(pen)
    pen._closePath()

    advance = font["hmtx"][glyph_name][0]
    columns = np.zeros(int(advance / pixel) + 4)
    for y in np.arange(*band, pixel):
        crossings = []
        for polygon in (p for p in pen.polygons if len(p) > 2):
            points = polygon + [polygon[0]]
            for (x0, y0), (x1, y1) in zip(points, points[1:]):
                if (y0 <= y < y1) or (y1 <= y < y0):
                    crossings.append((x0 + (x1 - x0) * (y - y0) / (y1 - y0), 1 if y1 > y0 else -1))
        crossings.sort()
        winding = 0
        for (start, direction), (end, _) in zip(crossings, crossings[1:]):
            winding += direction  # nonzero winding, so overlapping contours still fill
            if winding:
                columns[max(int(start / pixel), 0) : max(int(end / pixel), 0)] += 1
    return columns, advance


def gaussian(sigma, pixel=PIXEL):
    x = np.arange(-int(3 * sigma / pixel), int(3 * sigma / pixel) + 1) * pixel
    kernel = np.exp(-0.5 * (x / sigma) ** 2)
    return kernel / kernel.sum()


def trough(left, right, kern, kernel, pixel=PIXEL):
    """How much ink the lightest column between two letters is seen to carry.

    Blurring an image and adding up its columns is the same as adding up the columns
    and blurring that, so a glyph never needs rasterising in two dimensions.
    """
    (columns_a, advance, first_a, last_a), (columns_b, _, first_b, last_b) = left, right
    offset = int(round((advance + kern) / pixel))
    both = np.zeros(max(len(columns_a), offset + len(columns_b)) + len(kernel))
    both[: len(columns_a)] += columns_a
    both[offset : offset + len(columns_b)] += columns_b
    seen = np.convolve(both, kernel, mode="same")

    lo, hi = sorted((last_a, offset + first_b))
    return seen[lo : hi + 1].min()


def kerner(data):
    """Returns the kerning a shaper already applies to a pair, in font units."""
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


def channels(font, data, chars, top=760):
    """Soft-minimum channel width for every ordered pair of `chars`, kerning included."""
    cmap, hmtx = font.getBestCmap(), font["hmtx"]
    scale = font["head"].unitsPerEm / 1000
    ys = np.arange(-40 * scale, top * scale, STEP * scale)
    sides = {c: scan(font, cmap[ord(c)], ys) for c in chars}
    kern = kerner(data)

    out = {}
    for a in chars:
        right = hmtx[cmap[ord(a)]][0] - sides[a][0]
        for b in chars:
            gap = (right + sides[b][1] + kern(a, b)) / scale
            both = gap[~np.isnan(gap)]
            if len(both):
                out[(a, b)] = float(np.mean(np.maximum(both, FLOOR) ** SOFTNESS) ** (1 / SOFTNESS))
    return out


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
