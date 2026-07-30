# /// script
# dependencies = ["fonttools"]
# ///
"""Build 'Sofia Sans Ru' — Russian letterforms by default, Bulgarian moved to ss01,
plus acute anchors for the Cyrillic vowels Sofia Sans left unanchored.

Kept as it was run on 2026-07-21, so it carries its own copy of the anchor logic
rather than importing acutefix.py: this font is installed and correct, and the
Russian-default transform is what makes the file worth keeping.

    uv run build_sofia_sans_ru.py
"""

import glob
import os

from fontTools.otlLib import builder as ob
from fontTools.pens.boundsPen import BoundsPen
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables.otTables import FeatureParamsStylisticSet

SRC = os.path.expanduser("~/Downloads/sofia_sans_extracted")
DST = os.path.expanduser("~/Library/Fonts/SofiaSans-Ru")

VOWELS = [0x0410, 0x042F, 0x041E, 0x0423, 0x042E, 0x042B, 0x0418, 0x042D, 0x0415,
          0x0430, 0x044F, 0x043E, 0x0443, 0x044E, 0x044B, 0x0438, 0x044D, 0x0435]
UPPER = set(range(0x0410, 0x0430))
YERU = {0x042B, 0x044B}                       # Ы ы -> recenter off right leg
ACUTE_MARKS = ("acutecomb", "acutecomb.case")


# ---------- Russian-default transform ----------
def is_loclrus(lk):
    if lk.LookupType != 1:
        return False
    for st in lk.SubTable:
        m = getattr(st, "mapping", None)
        if not m or not all(v.endswith(".loclRUS") for v in m.values()):
            return False
    return True


def make_russian_default(f):
    gsub = f["GSUB"].table
    lookups = gsub.LookupList.Lookup
    ss01, locl = set(), set()
    for fr in gsub.FeatureList.FeatureRecord:
        if fr.FeatureTag == "ss01":
            ss01.update(fr.Feature.LookupListIndex)
        elif fr.FeatureTag == "locl":
            locl.update(fr.Feature.LookupListIndex)
    names = set(f.getGlyphOrder())
    for tbl in f["cmap"].tables:
        if tbl.isUnicode():
            for cp, g in list(tbl.cmap.items()):
                if g + ".loclRUS" in names:
                    tbl.cmap[cp] = g + ".loclRUS"
    for idx in ss01 | locl:
        if is_loclrus(lookups[idx]):
            for st in lookups[idx].SubTable:
                st.mapping = {v: k for k, v in st.mapping.items()}
    for sr in gsub.ScriptList.ScriptRecord:
        if sr.ScriptTag == "cyrl":
            for lr in sr.Script.LangSysRecord:
                if lr.LangSysTag == "RUS ":
                    lr.LangSysTag = "BGR "
    ui = f["name"].addName("Bulgarian")
    for fr in gsub.FeatureList.FeatureRecord:
        if fr.FeatureTag == "ss01":
            p = FeatureParamsStylisticSet()
            p.Version = 0
            p.UINameID = ui
            fr.Feature.FeatureParams = p
    for r in f["name"].names:
        s = r.toUnicode()
        if r.nameID in (1, 4, 16) and "Sofia Sans" in s and "Sofia Sans Ru" not in s:
            r.string = s.replace("Sofia Sans", "Sofia Sans Ru")
        elif r.nameID in (3, 6, 25) and "SofiaSans" in s and "SofiaSansRu" not in s:
            r.string = s.replace("SofiaSans", "SofiaSansRu")


# ---------- acute over АЯОУЮЫИЭЕ (both cases) ----------
def mbsub(lk):
    return lk.SubTable[0].ExtSubTable if lk.LookupType == 9 else lk.SubTable[0]


BOWL = {0x042E, 0x044E}   # Ю ю -> accent over the round bowl on the right


def fix_acute(f):
    gpos = f["GPOS"].table
    cmap = f.getBestCmap()
    names = set(f.getGlyphOrder())
    gs = f.getGlyphSet()
    glyf = f["glyf"]

    def center(g):
        p = BoundsPen(gs)
        gs[g].draw(p)
        return None if not p.bounds else round((p.bounds[0] + p.bounds[2]) / 2)

    def bowl_center(g):                       # center of the rightmost (bowl) contour
        gl = glyf[g]
        if gl.isComposite() or gl.numberOfContours < 1:
            return center(g)
        best, start = None, 0
        for e in gl.endPtsOfContours:
            xs = [p[0] for p in gl.coordinates[start:e + 1]]
            if best is None or max(xs) > best[1]:
                best = (min(xs), max(xs))
            start = e + 1
        return round((best[0] + best[1]) / 2)

    mark_lkidx, st = set(), None
    for fr in gpos.FeatureList.FeatureRecord:
        if fr.FeatureTag == "mark":
            mark_lkidx.update(fr.Feature.LookupListIndex)
    for i in mark_lkidx:
        s = mbsub(gpos.LookupList.Lookup[i])
        if getattr(s, "Format", None) == 1 and hasattr(s, "BaseCoverage") \
           and "acutecomb" in s.MarkCoverage.glyphs:
            st = s
            break

    marks = st.MarkCoverage.glyphs
    acute_marks = {nm: st.MarkArray.MarkRecord[marks.index(nm)] for nm in ACUTE_MARKS if nm in marks}
    acls = next(iter(acute_marks.values())).Class

    def base_anchor(g):
        gi = st.BaseCoverage.glyphs
        return st.BaseArray.BaseRecord[gi.index(g)].BaseAnchor[acls] if g in gi else None

    upY = base_anchor(cmap[0x041E]).YCoordinate   # О
    loY = base_anchor(cmap[0x043E]).YCoordinate   # о
    anchored = {g for g in st.BaseCoverage.glyphs if base_anchor(g)}

    # recenter Ы / ы
    for cp in YERU:
        for g in {cmap.get(cp), (cmap.get(cp) or "").replace(".loclRUS", ""), (cmap.get(cp) or "") + ".loclRUS"}:
            a = base_anchor(g) if g in names else None
            if a:
                a.XCoordinate = center(g)

    # add anchors for the vowels that still lack them
    bases = {}
    for cp in VOWELS:
        base = cmap.get(cp)
        if not base:
            continue
        for g in {base, base.replace(".loclRUS", ""), base + ".loclRUS"}:
            if g in names and g not in anchored and g not in bases and center(g) is not None:
                Y = upY if cp in UPPER else loY
                X = bowl_center(g) if cp in BOWL else center(g)
                bases[g] = {acls: ob.buildAnchor(X, Y)}
    if bases:
        mk = {nm: (r.Class, ob.buildAnchor(r.MarkAnchor.XCoordinate, r.MarkAnchor.YCoordinate))
              for nm, r in acute_marks.items()}
        lk = ob.buildLookup([ob.buildMarkBasePosSubtable(mk, bases, f.getReverseGlyphMap())],
                            flags=0, table="GPOS")
        idx = len(gpos.LookupList.Lookup)
        gpos.LookupList.Lookup.append(lk)
        gpos.LookupList.LookupCount += 1
        for fr in gpos.FeatureList.FeatureRecord:
            if fr.FeatureTag == "mark":
                fr.Feature.LookupListIndex.append(idx)
        cd = f["GDEF"].table.GlyphClassDef.classDefs
        for g in bases:
            if cd.get(g, 0) != 1:
                cd[g] = 1
    return len(bases)


for src in glob.glob(SRC + "/**/*.ttf", recursive=True):
    f = TTFont(src)
    make_russian_default(f)
    n = fix_acute(f)
    rel = os.path.relpath(src, SRC).replace("SofiaSans", "SofiaSansRu")
    out = os.path.join(DST, rel)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    f.save(out)
    print(f"{os.path.basename(out):42s} acute+{n}")
print("done")
