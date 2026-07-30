"""Swap the single-storey `a` family with its .ss01 double-storey counterparts."""
from copy import deepcopy
from fontTools.ttLib.tables.TupleVariation import TupleVariation

BASES = ['a','aacute','abreve','uni01CE','acircumflex','adieresis','uni1EA1',
         'agrave','amacron','aogonek','aring','uni2C65','atilde']
# Cyrillic glyphs that are composites of Latin `a` and must follow it.
CYR_MIRROR = {'uni0430':'a', 'uni04D1':'abreve', 'uni04D3':'adieresis'}

def _subtables(lookup):
    for st in lookup.SubTable:
        yield st.ExtSubTable if lookup.LookupType == 9 else st

def swap_a(font):
    glyf = font['glyf']; hmtx = font['hmtx']
    order = set(font.getGlyphOrder())
    pairs = [(b, b+'.ss01') for b in BASES if b in order and b+'.ss01' in order]
    partner = {}
    for x, y in pairs:
        partner[x] = y; partner[y] = x

    for x, y in pairs:
        glyf[x], glyf[y] = glyf[y], glyf[x]
        hmtx[x], hmtx[y] = hmtx[y], hmtx[x]
    for name in partner:
        g = glyf[name]
        if g.isComposite():
            for c in g.components:
                c.glyphName = partner.get(c.glyphName, c.glyphName)

    gvar = font.get('gvar')
    if gvar:
        for x, y in pairs:
            vx, vy = gvar.variations.get(x), gvar.variations.get(y)
            if vx is not None: gvar.variations[y] = vx
            if vy is not None: gvar.variations[x] = vy
    hvar = font.get('HVAR')
    awm = hvar.table.AdvWidthMap.mapping if hvar and hvar.table.AdvWidthMap else None
    if awm:
        for x, y in pairs:
            if x in awm and y in awm:
                awm[x], awm[y] = awm[y], awm[x]

    for lk in font['GPOS'].table.LookupList.Lookup:
        for st in _subtables(lk):
            if st.__class__.__name__ != 'MarkBasePos':
                continue
            gl = st.BaseCoverage.glyphs; recs = st.BaseArray.BaseRecord
            for x, y in pairs:
                if x in gl and y in gl:
                    i, j = gl.index(x), gl.index(y)
                    recs[i], recs[j] = recs[j], recs[i]

    _mirror_cyrillic(font, glyf, hmtx, gvar, awm, pairs)
    return len(pairs)

def _mirror_cyrillic(font, glyf, hmtx, gvar, awm, pairs):
    """Cyrillic а/ӑ/ӓ are composites of `a`; realign their metrics to the new base."""
    order = set(font.getGlyphOrder())
    # how far the designer nudged marks when moving to the narrower ss01 base
    dx = 0
    if 'adieresis' in order and len(glyf['adieresis'].components) > 1:
        dx = glyf['adieresis'].components[1].x - 127  # post-swap value minus original
    for cyr, src in CYR_MIRROR.items():
        if cyr not in order or src not in order:
            continue
        hmtx[cyr] = hmtx[src]
        g = glyf[cyr]
        if g.isComposite() and len(g.components) > 1:
            for c in g.components[1:]:
                c.x += dx
        if gvar and src in gvar.variations:
            n = len(g.components) if g.isComposite() else 0
            out = []
            for tv in gvar.variations[src]:
                coords = list(tv.coordinates)
                phantom = coords[-4:]
                out.append(TupleVariation(dict(tv.axes), [(0, 0)] * n + phantom))
            gvar.variations[cyr] = out
        if awm is not None and src in awm:
            awm[cyr] = awm[src]

    for lk in font['GPOS'].table.LookupList.Lookup:
        for st in _subtables(lk):
            if st.__class__.__name__ != 'MarkBasePos':
                continue
            gl = st.BaseCoverage.glyphs; recs = st.BaseArray.BaseRecord
            for cyr, src in CYR_MIRROR.items():
                if cyr in gl and src in gl:
                    recs[gl.index(cyr)] = deepcopy(recs[gl.index(src)])
