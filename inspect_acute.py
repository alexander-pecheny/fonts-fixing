# /// script
# dependencies = ["fonttools"]
# ///
"""Report which Cyrillic vowels a font anchors U+0301 over, and how the acute is drawn.

    uv run inspect_acute.py path/to/font.ttf
"""

import sys

from fontTools.ttLib import TTFont

from acutefix import ACUTE, LOWER, UPPER, contours, find_mark_bases, langsyses, pointing_tip


def mark_scripts(font):
    """Which GPOS scripts run the `mark` feature, and which list it nowhere."""
    t = font["GPOS"].table
    feats = t.FeatureList.FeatureRecord
    on, off = [], []
    for sr in t.ScriptList.ScriptRecord:
        tags = {feats[i].FeatureTag for ls in langsyses(sr) for i in ls.FeatureIndex}
        (on if "mark" in tags else off).append(sr.ScriptTag)
    return on, off


def report(path):
    font = TTFont(path, fontNumber=0) if path.endswith(".ttc") else TTFont(path)
    cmap = font.getBestCmap()
    print(f"=== {path}")
    print("family:", font["name"].getDebugName(1), "|", font["name"].getDebugName(2))
    if "fvar" in font:
        print("variable, axes:", " ".join(a.axisTag for a in font["fvar"].axes))
    mark = cmap.get(ACUTE)
    if not mark:
        print("no U+0301 in cmap")
        return
    subtables = find_mark_bases(font, mark)
    if not subtables:
        print(f"{mark} is in cmap but no mark-to-base lookup covers it")
        return
    st = subtables[0]
    anchored = {g for sub in subtables for g in sub.BaseCoverage.glyphs}
    on, off = mark_scripts(font)
    print(f"mark feature: on for {' '.join(on)}" + (f", MISSING from {' '.join(off)}" if off else ""))
    print(
        f"mark-to-base: {len(subtables)} subtable(s), "
        f"{len(st.MarkCoverage.glyphs)} marks, {len(anchored)} bases"
    )
    for row, cps in (("upper", UPPER), ("lower", LOWER)):
        state = " ".join(
            f"{chr(cp)}{'+' if cmap.get(cp) in anchored else '-'}" for cp in cps
        )
        print(f"  {row}: {state}")
    gs = font.getGlyphSet()
    pts = [p for c in contours(gs, mark) for p in c]
    xs = [x for x, _ in pts]
    rec = st.MarkArray.MarkRecord[st.MarkCoverage.glyphs.index(mark)]
    print(
        f"  acute: {len(pts)} points, x=[{min(xs):.0f},{max(xs):.0f}], "
        f"mark anchor x={rec.MarkAnchor.XCoordinate}, pointing tip x={pointing_tip(gs, mark)}"
    )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    for p in sys.argv[1:]:
        report(p)
