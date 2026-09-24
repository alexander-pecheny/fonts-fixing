# /// script
# dependencies = ["fonttools", "numpy"]
# ///
"""Build 'SF Pro Fix' — the macOS system font with the stress mark set over Cyrillic vowels.

SF Pro has no `mark` feature at all. Latin á works only because Unicode composes
a + U+0301 into a precomposed glyph, drawn in the font as a composite of a and
acutecmb. Cyrillic has no precomposed stressed vowels, so о + U+0301 falls
through to the bare zero-width acutecmb, which hangs after the letter.

This does for Cyrillic what the font does for Latin: a composite per vowel, and
a `ccmp` ligature that swaps it in. Each composite takes the acute glyph, its
height and its offset from the letter's centre from a Latin donor (о from ó,
и from ú), so it sits where the font's own á does. The offset is measured at
1,500 points of the design space and fitted by least squares onto the font's own
gvar regions, so it tracks weight, width and optical size to within 3 units of
2,048. Fitting to the masters alone left errors of 109 units between them.

The copy loses the `appl` and `bild` entries of its `meta` table, Apple's
signature: CoreText hides a font that fails it from the family list, so no app
could ask for it by name.

SF Pro may not be redistributed, so the output goes to scratchpad/, not fonts/.
The system copy is under SIP; point Firefox at this one instead (README.md).

    uv run build_sf_fix.py
"""

import os
from copy import deepcopy

from fontTools.otlLib import builder as ob
from fontTools.pens.boundsPen import BoundsPen
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables._g_l_y_f import GlyphCoordinates
from fontTools.ttLib.tables.TupleVariation import TupleVariation
from fontTools.varLib.models import supportScalar
import numpy as np

from acutefix import ACUTE, bowl_center

HERE = os.path.dirname(os.path.abspath(__file__))
DST = os.path.join(HERE, "scratchpad", "sf")
SOURCES = {
    "Regular": "/System/Library/Fonts/SFNS.ttf",
    "Italic": "/System/Library/Fonts/SFNSItalic.ttf",
}
FAMILY = "SF Pro Fix"

# Cyrillic vowel -> Latin precomposed donor of the acute's glyph, height and offset from centre.
DONORS = {
    "а": "á", "е": "é", "о": "ó", "у": "ý", "и": "ú", "ы": "ú", "э": "ó", "ю": "ó", "я": "ú",
    "А": "Á", "Е": "É", "О": "Ó", "У": "Ú", "И": "Ú", "Ы": "Ú", "Э": "Ó", "Ю": "Ó", "Я": "Ú",
}
BOWL = {"ю", "Ю"}


def coords_at(font, name, loc):
    """A glyph's points (for a composite, its component offsets) plus phantoms at `loc`."""
    glyf, gvar = font["glyf"], font["gvar"].variations
    coords, _ = glyf._getCoordinatesAndControls(name, font["hmtx"].metrics, None)
    for var in gvar.get(name, []):
        s = supportScalar(loc, var.axes)
        if s:
            if None in var.coordinates:
                raise SystemExit(f"{name}: sparse deltas on a composite")
            coords += GlyphCoordinates(var.coordinates) * s
    return coords


def center(gs, name, bowl):
    if bowl:
        return bowl_center(gs, name)
    pen = BoundsPen(gs)
    gs[name].draw(pen)
    return (pen.bounds[0] + pen.bounds[2]) / 2


def regions(font, names):
    """Every region of the design space the involved glyphs vary over."""
    seen, glyf = set(), font["glyf"]
    todo = list(names)
    while todo:
        n = todo.pop()
        if n not in seen:
            seen.add(n)
            todo += [c.glyphName for c in glyf[n].components] if glyf[n].isComposite() else []
    out = set()
    for n in seen:
        for var in font["gvar"].variations.get(n, []):
            out.add(tuple(sorted((a, t) for a, t in var.axes.items() if t[1])))
    return [dict(r) for r in sorted(out)]


def samples(font, supports, n=1500):
    """The default, every peak and corner of a region, and random fill between."""
    rng = np.random.default_rng(0)
    axes = [a.axisTag for a in font["fvar"].axes]
    locs = [{}] + [{a: t[1] for a, t in r.items()} for r in supports]
    locs += [{a: t[k] for a, t in r.items()} for r in supports for k in (0, 2)]
    locs += [dict(zip(axes, rng.uniform(-1, 1, len(axes)))) for _ in range(n)]
    return locs


def build(src, style):
    font = TTFont(src)
    cmap = font.getBestCmap()
    glyf, hmtx = font["glyf"], font["hmtx"]
    hvar = font["HVAR"].table.AdvWidthMap.mapping

    plan = []
    for ch, donor_ch in DONORS.items():
        base, donor = cmap[ord(ch)], cmap[ord(donor_ch)]
        dbase, dacute = glyf[donor].components
        plan.append((ch, base, donor, dbase.glyphName, dacute.glyphName))
    supports = regions(font, [n for p in plan for n in p[1:]])
    locs = samples(font, supports)
    basis = np.array([[supportScalar(l, r) for r in supports] for l in locs])
    glyphsets = [font.getGlyphSet(location=l, normalized=True) for l in locs]

    ligatures = {}
    for ch, base, donor, dbase, acute in plan:
        values = []  # per master: acute x, acute y, then the four phantom points' x
        for loc, gs in zip(locs, glyphsets):
            d = coords_at(font, donor, loc)
            off = d[1][0] - d[0][0] - center(gs, dbase, False) + center(gs, base, ch in BOWL)
            phantom = coords_at(font, base, loc)[-4:]
            values.append([off, d[1][1]] + [p[0] for p in phantom])
        values = np.array(values)
        default = [round(v) for v in values[0]]
        deltas = np.linalg.lstsq(basis, values - values[0], rcond=None)[0].round().astype(int)

        g = deepcopy(glyf[donor])
        g.components[0].glyphName, g.components[0].x, g.components[0].y = base, 0, 0
        g.components[1].glyphName, g.components[1].x, g.components[1].y = acute, *default[:2]
        name = f"{base}.acute"
        font.setGlyphOrder(font.getGlyphOrder() + [name])
        glyf[name] = g
        hmtx[name] = hmtx[base]
        hvar[name] = hvar[base]
        tvs = []
        for support, (dx, dy, *ph) in zip(supports, deltas.tolist()):
            if any((dx, dy, *ph)):
                pts = [(0, 0), (dx, dy)] + [(p, 0) for p in ph]
                tvs.append(TupleVariation(support, pts))
        font["gvar"].variations[name] = tvs
        g.recalcBounds(glyf)
        ligatures[(base, cmap[ACUTE])] = name

    lookup = ob.buildLookup([ob.buildLigatureSubstSubtable(ligatures)], table="GSUB")
    gsub = font["GSUB"].table
    gsub.LookupList.Lookup.append(lookup)
    gsub.LookupList.LookupCount += 1
    for fr in gsub.FeatureList.FeatureRecord:
        if fr.FeatureTag == "ccmp":
            fr.Feature.LookupListIndex.append(len(gsub.LookupList.Lookup) - 1)
            fr.Feature.LookupCount += 1

    del font["MERG"]  # an AAT glyph-merging table indexed by glyph; stale once glyphs are added
    for tag in ("appl", "bild"):  # Apple's signature: a copy that fails it is hidden from the font list
        font["meta"].data.pop(tag, None)
    ps = f"SFProFix-{style}"
    name = font["name"]
    strings = {1: FAMILY, 2: style, 3: f"{ps};acute", 4: f"{FAMILY} {style}", 6: ps, 16: FAMILY, 17: style}
    # The localised "System Font" and the .SFNS instance names would pass for the real system font.
    for nid in (1, 2, 4, 16, 17, 21, 22, 25):
        name.removeNames(nameID=nid)
    for rec in name.names:
        if rec.toUnicode().startswith(".SFNS-"):
            rec.string = rec.toUnicode().replace(".SFNS-", "SFProFix-", 1)
    for nid, value in strings.items():
        name.setName(value, nid, 3, 1, 0x409)
        name.setName(value, nid, 1, 0, 0)
    os.makedirs(DST, exist_ok=True)
    out = os.path.join(DST, f"{ps}.ttf")
    font.save(out)
    print(f"{out}: {len(ligatures)} stressed vowels over {len(supports)} regions")


if __name__ == "__main__":
    for style, src in SOURCES.items():
        build(src, style)
