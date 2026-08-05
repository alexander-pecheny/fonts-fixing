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
CASE = dict(zip(UPPER, LOWER)) | dict(zip(LOWER, UPPER))
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


def bbox(glyphset, name):
    pen = BoundsPen(glyphset)
    glyphset[name].draw(pen)
    return pen.bounds


def bbox_center(glyphset, name):
    b = bbox(glyphset, name)
    return None if not b else round((b[0] + b[2]) / 2)


def mirrored_x(glyphset, donor, target, x):
    """Where x sits in donor, proportionally, inside target.

    Cyrillic vowels keep their shape across cases, so a font that anchors only
    one of the pair still says where it wants the mark on the other.
    """
    d, t = bbox(glyphset, donor), bbox(glyphset, target)
    if not d or not t or d[2] == d[0]:
        return None
    return round(t[0] + (x - d[0]) / (d[2] - d[0]) * (t[2] - t[0]))


def bowl_center(glyphset, name):
    """Center of the rightmost counter — Ю's bowl rather than its whole width.

    The crossbar usually joins Ю's stem and bowl into one contour, so the bowl
    is only findable as the hole inside it. Where a font does anchor ю itself,
    this reproduces its anchor to within a unit.
    """
    boxes = [
        (min(x for x, _ in c), min(y for _, y in c), max(x for x, _ in c), max(y for _, y in c))
        for c in contours(glyphset, name)
    ]
    holes = [
        b
        for b in boxes
        if any(o[0] < b[0] and o[1] < b[1] and o[2] > b[2] and o[3] > b[3] for o in boxes)
    ]
    if not holes:
        return bbox_center(glyphset, name)
    b = max(holes, key=lambda b: b[2])
    return round((b[0] + b[2]) / 2)


def pointing_tip(glyphset, name):
    """X of the acute's lower edge — the end it visually points with.

    A steeply slanted acute centered by its bounding box reads as pointing at
    the left half of the letter; centering this instead fixes that.
    """
    pts = [p for c in contours(glyphset, name) for p in c]
    low = sorted(pts, key=lambda p: p[1])[:2]
    return round(sum(x for x, _ in low) / 2)


def langsyses(script_record):
    for ls in [script_record.Script.DefaultLangSys] + [
        r.LangSys for r in script_record.Script.LangSysRecord
    ]:
        if ls is not None:
            yield ls


def enable_features(font, script, tags=("mark", "mkmk"), table="GPOS"):
    """Register `tags` under `script`, copying the feature indices from DFLT.

    A shaper that finds the script tag stops looking, so a script listed with an
    incomplete feature set gets no DFLT fallback: the lookups are in the font but
    never run. Returns the tags added.
    """
    t = font[table].table
    feats = t.FeatureList.FeatureRecord
    scripts = {r.ScriptTag: r for r in t.ScriptList.ScriptRecord}
    target = scripts.get(script)
    if target is None:
        return []  # a missing script falls back to DFLT, which already has them
    donor = scripts.get("DFLT") or scripts["latn"]
    wanted = [i for i in donor.Script.DefaultLangSys.FeatureIndex if feats[i].FeatureTag in tags]
    added = set()
    for ls in langsyses(target):
        for i in wanted:
            if i not in ls.FeatureIndex:
                ls.FeatureIndex.append(i)
                ls.FeatureIndex.sort()
                ls.FeatureCount = len(ls.FeatureIndex)
                added.add(feats[i].FeatureTag)
    return sorted(added)


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


def recenter_acute(font, codepoints):
    """Move the font's own acute anchors onto the glyph's bounding-box center.

    Geist hangs the mark over ы's right stroke; Russian sets it over the letter.
    """
    cmap = font.getBestCmap()
    gs = font.getGlyphSet()
    subtables = find_mark_bases(font, cmap[ACUTE])
    st = subtables[0]
    cls = st.MarkArray.MarkRecord[st.MarkCoverage.glyphs.index(cmap[ACUTE])].Class
    moved = []
    for cp in codepoints:
        g = cmap.get(cp)
        x = bbox_center(gs, g) if g else None
        for sub in subtables if x is not None else []:
            if g not in sub.BaseCoverage.glyphs:
                continue
            rec = sub.BaseArray.BaseRecord[sub.BaseCoverage.glyphs.index(g)]
            a = rec.BaseAnchor[cls]
            if a and a.XCoordinate != x:
                moved.append((g, a.XCoordinate, x))
                rec.BaseAnchor[cls] = ob.buildAnchor(x, a.YCoordinate)
    return moved


def add_acute_anchors(font, point_at_center=True, uppercase=UPPER, lowercase=LOWER, bowl=BOWL):
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

    def anchor_of(cp):
        g = cmap.get(cp)
        for sub in subtables:
            if g in sub.BaseCoverage.glyphs:
                a = sub.BaseArray.BaseRecord[sub.BaseCoverage.glyphs.index(g)].BaseAnchor[cls]
                if a:
                    return g, a
        return None

    def donor_y(codepoints):
        for cp in codepoints:
            hit = anchor_of(cp)
            if hit:
                return hit[1].YCoordinate
        raise SystemExit(f"no anchored donor glyph among {[hex(c) for c in codepoints]}")

    def anchor_x(cp, g):
        twin = anchor_of(CASE.get(cp))
        x = twin and mirrored_x(gs, twin[0], g, twin[1].XCoordinate)
        if x is not None:
            return x
        return bowl_center(gs, g) if cp in bowl else bbox_center(gs, g)

    bases = {}
    for cps, y in ((uppercase, donor_y(REF_UPPER)), (lowercase, donor_y(REF_LOWER))):
        for cp in cps:
            g = cmap.get(cp)
            if not g or g in anchored or g in bases:
                continue
            x = anchor_x(cp, g)
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
