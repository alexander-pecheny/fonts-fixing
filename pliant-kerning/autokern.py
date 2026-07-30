"""Fill in kern pairs that sit looser than the font's own per-glyph rhythm."""
import numpy as np, uharfbuzz as hb
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables import otTables as ot
from profiles import profile

LATIN = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
CYR   = 'абвгдеёжзийклмнопрстуфхцчшщъыьэюяАБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ'
DIGIT = '0123456789'
PUNCT = '.,;:!?«»()[]"\'-–—/'
ALPHABET = LATIN + CYR + DIGIT + PUNCT
CAP, THRESHOLD = 280.0, -60

def _hb_kerns(data, chars, cmap):
    face = hb.Face(data); hbf = hb.Font(face)
    out = {}
    for a in chars:
        for b in chars:
            s = a + b
            def adv(on):
                buf = hb.Buffer(); buf.add_str(s); buf.guess_segment_properties()
                hb.shape(hbf, buf, {'kern': on})
                return sum(p.x_advance for p in buf.glyph_positions)
            out[(a, b)] = adv(True) - adv(False)
    return out

def propose(font, data):
    cmap = font.getBestCmap()
    chars = [c for c in ALPHABET if ord(c) in cmap]
    ys = np.arange(-220, 760, 20)
    hmtx = font['hmtx']
    prof = {c: profile(font, cmap[ord(c)], ys) for c in chars}
    existing = _hb_kerns(data, chars, cmap)

    def metric(a, b, extra=0.0):
        Ra = hmtx[cmap[ord(a)]][0] - prof[a][0]
        Lb = prof[b][1]
        sel = ~np.isnan(Ra) | ~np.isnan(Lb)
        if not sel.any(): return np.nan
        gap = Ra + Lb + extra
        gap = np.where(np.isnan(gap), CAP, np.minimum(gap, CAP))[sel]
        return float(np.mean(np.maximum(gap, 20.0)))

    pairs = {}
    for a in chars:
        vals = [metric(a, b, existing[(a, b)]) for b in chars]
        target = np.nanmedian(vals)
        for b in chars:
            if existing[(a, b)]: continue
            k = target - metric(a, b)
            if k <= THRESHOLD:
                pairs[(cmap[ord(a)], cmap[ord(b)])] = int(round(k / 10) * 10)
    return pairs

def add_lookup(font, pairs):
    if not pairs: return 0
    gpos = font['GPOS'].table
    order = font.getGlyphOrder(); gid = {g: i for i, g in enumerate(order)}
    first = {}
    for (a, b), v in pairs.items():
        first.setdefault(a, []).append((b, v))

    pp = ot.PairPos(); pp.Format = 1
    pp.ValueFormat1, pp.ValueFormat2 = 0x0004, 0
    cov_glyphs = sorted(first, key=lambda g: gid[g])
    pp.Coverage = ot.Coverage(); pp.Coverage.glyphs = cov_glyphs
    pp.PairSet = []
    for a in cov_glyphs:
        ps = ot.PairSet(); ps.PairValueRecord = []
        for b, v in sorted(first[a], key=lambda t: gid[t[0]]):
            r = ot.PairValueRecord(); r.SecondGlyph = b
            r.Value1 = ot.ValueRecord(); r.Value1.XAdvance = v
            r.Value2 = None
            ps.PairValueRecord.append(r)
        ps.PairValueCount = len(ps.PairValueRecord)
        pp.PairSet.append(ps)
    pp.PairSetCount = len(pp.PairSet)

    ext = ot.ExtensionPos(); ext.Format = 1
    ext.ExtensionLookupType = 2; ext.ExtSubTable = pp
    lk = ot.Lookup(); lk.LookupType = 9; lk.LookupFlag = 0
    lk.SubTable = [ext]; lk.SubTableCount = 1
    gpos.LookupList.Lookup.append(lk)
    idx = len(gpos.LookupList.Lookup) - 1
    gpos.LookupList.LookupCount = idx + 1

    for fr in gpos.FeatureList.FeatureRecord:
        if fr.FeatureTag == 'kern':
            fr.Feature.LookupListIndex.append(idx)
            fr.Feature.LookupCount = len(fr.Feature.LookupListIndex)
    return len(pairs)
