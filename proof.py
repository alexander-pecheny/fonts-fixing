# /// script
# dependencies = ["fonttools"]
# ///
"""Render a stress-mark proof sheet so accent placement can be compared by eye.

Each argument is either an installed family name or a path to a .ttf; files are
copied to a temp dir under a unique family name so several versions of the same
font can sit side by side in one image.

    uv run proof.py "Roboto Flex Fix" old/RobotoFlexFix-Regular.ttf
    uv run proof.py --size 120 --words "доро́ги изжи́ли" "Roboto Flex Fix"
"""

import argparse
import os
import shutil
import subprocess
import tempfile

from fontTools.ttLib import TTFont

UPPER_ROW = "А́Я́О́У́Ю́Ы́И́Э́Е́Ё́"
LOWER_ROW = "а́я́о́у́ю́ы́и́э́е́ё́"
WORDS = "доро́ги изжи́ли Пу́шка усыпи́ть"


def stage(path, label, fontdir):
    font = TTFont(path)
    name = font["name"]
    for nid, value in ((1, label), (4, label), (6, label.replace(" ", "")), (16, label)):
        name.setName(value, nid, 3, 1, 0x409)
        name.setName(value, nid, 1, 0, 0)
    font.save(os.path.join(fontdir, f"{label.replace(' ', '')}.ttf"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("fonts", nargs="+", help="installed family names and/or .ttf paths")
    ap.add_argument("--out", default="proof.png")
    ap.add_argument("--size", type=int, default=60)
    ap.add_argument("--words", default=WORDS)
    ap.add_argument("--ppi", type=int, default=120)
    args = ap.parse_args()

    tmp = tempfile.mkdtemp(prefix="proof-fonts-")
    rows = []
    for i, spec in enumerate(args.fonts):
        if os.path.isfile(spec):
            label = f"Proof {i}"
            stage(spec, label, tmp)
            rows.append((label, os.path.basename(spec)))
        else:
            rows.append((spec, spec))

    lines = [
        f"#set page(width: auto, height: auto, margin: 24pt)",
        f'#set text(size: 11pt, lang: "ru")',
    ]
    for family, caption in rows:
        lines += [
            f"{caption}\\",
            # bounds edges keep tall stacked accents from colliding with the row above
            f'#text(font: "{family}", size: {args.size}pt, top-edge: "bounds", bottom-edge: "bounds")'
            f"[{UPPER_ROW} \\ {LOWER_ROW} \\ {args.words}]",
            "#v(18pt)",
        ]
    src = os.path.join(tmp, "proof.typ")
    with open(src, "w") as fh:
        fh.write("\n".join(lines) + "\n")

    out = os.path.abspath(args.out)
    subprocess.run(
        ["typst", "compile", "--font-path", tmp, src, out, "--ppi", str(args.ppi)],
        check=True,
    )
    shutil.rmtree(tmp)
    print(out)


if __name__ == "__main__":
    main()
