"""Add missing combining-acute (U+0301) anchors for Cyrillic vowels.

Fonts routinely anchor only Latin bases in their GPOS mark-to-base lookup, so a
Russian stress mark lands after the letter instead of over it. This adds the
missing anchors, reusing the font's own Latin anchor heights so the result
matches its precomposed Á/á exactly.
"""

from fontTools.otlLib import builder as ob
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.recordingPen import DecomposingRecordingPen

ACUTE = 0x0301
UPPER = [0x0410, 0x0415, 0x0401, 0x0418, 0x041E, 0x0423, 0x042B, 0x042D, 0x042E, 0x042F]
LOWER = [c + (0x50 if c == 0x0401 else 0x20) for c in UPPER]
BOWL = {0x042E, 0x044E}  # Ю ю: over the round bowl on the right, not the whole bbox
REF_UPPER = (0x041E, 0x004F)  # О, O — anchor height donors for uppercase
REF_LOWER = (0x043E, 0x006F)  # о, o


def contours(glyphset, name):
    pen = DecomposingRecordingPen(glyphset)
    glyphset[name].draw(pen)
    out, cur = [], None
    for op, args in pen.value:
        pts = [a for a in args if isinstance(a, tuple) and len(a) == 2]
        if op == "moveTo":
            if cur:
                out.append(cur)
            cur = list(pts)
        elif cur is not None:
            cur.extend(pts)
    if cur:
        out.append(cur)
    return out


def bbox_center(glyphset, name):
    pen = BoundsPen(glyphset)
    glyphset[name].draw(pen)
    return None if not pen.bounds else round((pen.bounds[0] + pen.bounds[2]) / 2)


def bowl_center(glyphset, name):
    """Center of the rightmost contour — Ю's bowl rather than its whole width."""
    cs = contours(glyphset, name)
    if not cs:
        return bbox_center(glyphset, name)
    right = max(cs, key=lambda c: max(x for x, _ in c))
    xs = [x for x, _ in right]
    return round((min(xs) + max(xs)) / 2)


def pointing_tip(glyphset, name):
    """X of the acute's lower edge — the end it visually points with.

    A steeply slanted acute centered by its bounding box reads as pointing at
    the left half of the letter; centering this instead fixes that.
    """
    pts = [p for c in contours(glyphset, name) for p in c]
    low = sorted(pts, key=lambda p: p[1])[:2]
    return round(sum(x for x, _ in low) / 2)


def find_mark_bases(font, mark_glyph):
    """Every mark-to-base subtable that positions mark_glyph, in feature order."""
    gpos = font["GPOS"].table
    found = []
    for fr in gpos.FeatureList.FeatureRecord:
        if fr.FeatureTag != "mark":
            continue
        for i in fr.Feature.LookupListIndex:
            lk = gpos.LookupList.Lookup[i]
            st = lk.SubTable[0].ExtSubTable if lk.LookupType == 9 else lk.SubTable[0]
            if st.__class__.__name__ != "MarkBasePos":
                continue  # the mark feature also carries mark-to-ligature subtables
            if mark_glyph in st.MarkCoverage.glyphs:
                found.append(st)
    return found


def add_acute_anchors(font, point_at_center=True, uppercase=UPPER, lowercase=LOWER):
    """Anchor U+0301 over the Cyrillic vowels the font left out. Returns added glyph names."""
    cmap = font.getBestCmap()
    gs = font.getGlyphSet()
    mark = cmap[ACUTE]
    subtables = find_mark_bases(font, mark)
    if not subtables:
        raise SystemExit("font has no mark-to-base lookup covering U+0301")

    st = subtables[0]
    rec = st.MarkArray.MarkRecord[st.MarkCoverage.glyphs.index(mark)]
    cls = rec.Class
    anchored = {g for sub in subtables for g in sub.BaseCoverage.glyphs}

    def donor_y(codepoints):
        for cp in codepoints:
            g = cmap.get(cp)
            for sub in subtables:
                if g in sub.BaseCoverage.glyphs:
                    a = sub.BaseArray.BaseRecord[sub.BaseCoverage.glyphs.index(g)].BaseAnchor[cls]
                    if a:
                        return a.YCoordinate
        raise SystemExit(f"no anchored donor glyph among {[hex(c) for c in codepoints]}")

    bases = {}
    for cps, y in ((uppercase, donor_y(REF_UPPER)), (lowercase, donor_y(REF_LOWER))):
        for cp in cps:
            g = cmap.get(cp)
            if not g or g in anchored or g in bases:
                continue
            x = bowl_center(gs, g) if cp in BOWL else bbox_center(gs, g)
            if x is not None:
                bases[g] = {cls: ob.buildAnchor(x, y)}
    if not bases:
        return []

    mx = pointing_tip(gs, mark) if point_at_center else rec.MarkAnchor.XCoordinate
    marks = {mark: (cls, ob.buildAnchor(mx, rec.MarkAnchor.YCoordinate))}
    lookup = ob.buildLookup(
        [ob.buildMarkBasePosSubtable(marks, bases, font.getReverseGlyphMap())],
        flags=0,
        table="GPOS",
    )
    gpos = font["GPOS"].table
    idx = len(gpos.LookupList.Lookup)
    gpos.LookupList.Lookup.append(lookup)
    gpos.LookupList.LookupCount += 1
    for fr in gpos.FeatureList.FeatureRecord:
        if fr.FeatureTag == "mark":
            fr.Feature.LookupListIndex.append(idx)
    classdefs = font["GDEF"].table.GlyphClassDef.classDefs
    for g in bases:
        classdefs[g] = 1
    return sorted(bases)
