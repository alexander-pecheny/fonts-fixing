# /// script
# dependencies = ["fonttools", "numpy", "scikit-learn", "joblib"]
# ///
"""Train the sidebearing model on the fonts macOS ships, and report what it is worth.

The system fonts are the training set on purpose. They are not fonts anyone here wants
to modify — most are proprietary — so nothing that gets patched later has been learned
from itself, and the score is always a score on a face the model has not seen. What is
kept is the model, which holds no outlines: only how spacing follows from shape.

Families are held out whole. A family's weights share their designer's habits, so
testing on a sibling of a font in the training set would flatter the model.

    uv run train_spacing.py
    uv run train_spacing.py --check ~/Library/Fonts/Literata/static/Literata-Regular.ttf
"""

import argparse
import glob
import os

import joblib
import numpy as np
from fontTools.ttLib import TTCollection
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import GroupKFold

from spacing_model import OWN, SAMPLES, centred, extract

HERE = os.path.dirname(os.path.abspath(__file__))
ROOTS = ("/System/Library/Fonts", "/System/Library/Fonts/Supplemental")
MODEL = os.path.join(HERE, "spacing-model.joblib")
CACHE = os.path.join(HERE, "scratchpad", "system-sides.npz")

# Faces whose spacing is not a function of shape: a monospace advance is fixed before
# any glyph is drawn, and a script face is spaced so its strokes join up.
NOT_TEXT = ("mono", "courier", "zapfino", "chancery", "bradley", "trattatello", "luminari",
            "comic", "papyrus", "marker", "brush", "script", "hand", "typewriter", "stencil",
            "impact", "phosphate", "chalkduster", "herculanum", "ayuthaya", "silom", "krungthep")


def faces():
    for root in ROOTS:
        for path in sorted(glob.glob(f"{root}/*")):
            if path.lower().endswith((".ttf", ".otf")):
                yield path, 0
            elif path.lower().endswith((".ttc", ".otc")):
                try:
                    for index in range(len(TTCollection(path, lazy=True).fonts)):
                        yield path, index
                except Exception:
                    continue


def harvest():
    rows = []
    for path, index in faces():
        if any(word in os.path.basename(path).lower() for word in NOT_TEXT):
            continue
        try:
            found = extract(path, index)
        except Exception:
            continue
        if len(found) < 40:  # a face missing most of the alphabet teaches little
            continue
        if any(word in found[0]["family"].lower() for word in NOT_TEXT):
            continue
        targets, _ = centred(found)
        for row, target in zip(found, targets):
            row["centred"] = target
        rows += found
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", nargs="*", default=[], help="fonts to score after training")
    parser.add_argument("--ablate", action="store_true", help="score cut-down feature sets too")
    parser.add_argument("--reharvest", action="store_true", help="re-read the fonts rather than the cache")
    args = parser.parse_args()

    if os.path.exists(CACHE) and not args.reharvest:
        held = np.load(CACHE, allow_pickle=True)
        X, y, groups, scales = held["X"], held["y"], held["groups"], held["scales"]
    else:
        rows = harvest()
        X = np.array([row["features"] for row in rows])
        y = np.array([row["centred"] for row in rows])
        groups = np.array([row["family"] for row in rows])
        scales = np.array([row["xheight"] for row in rows])
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        np.savez_compressed(CACHE, X=X, y=y, groups=groups, scales=scales)
    print(f"{len(rows)} sides, {len(set(groups))} families, {X.shape[1]} features")
    print(f"null error {np.abs(y * scales).mean():.1f} units at 1000 upem")

    build = lambda: HistGradientBoostingRegressor(
        max_iter=1200, learning_rate=0.05, max_leaf_nodes=63, min_samples_leaf=40)

    folds = list(GroupKFold(n_splits=5).split(X, y, groups))

    def score(columns, label):
        errors = []
        for train, test in folds:
            predicted = build().fit(X[train][:, columns], y[train]).predict(X[test][:, columns])
            errors.append(np.abs((y[test] - predicted) * scales[test]))
        print(f"  {label:34s} {np.concatenate(errors).mean():5.1f} units")

    print("held out families, never seen in training:")
    everything = np.arange(X.shape[1])
    score(everything, "everything")
    if args.ablate:
        # the layout of a row, in the order spacing_model builds it
        band, own, slope = SAMPLES, SAMPLES + OWN, SAMPLES + OWN + OWN - 1
        score(everything[:band], "the band profile alone")
        score(everything[:own], "band and glyph profiles")
        score(everything[:-5], "everything but the face features")
        score(np.r_[everything[:slope], everything[slope + OWN - 1:]], "everything but the slopes")

    model = build().fit(X, y)
    joblib.dump(model, MODEL, compress=3)
    print(f"saved {os.path.basename(MODEL)}, {os.path.getsize(MODEL) / 1e6:.1f} MB")

    for path in args.check:
        found = extract(os.path.expanduser(path))
        targets, _ = centred(found)
        predicted = model.predict(np.array([row["features"] for row in found]))
        scale = found[0]["xheight"]
        print(f"  {os.path.basename(path):34s} {np.abs((targets - predicted) * scale).mean():5.1f} units "
              f"(null {np.abs(targets * scale).mean():5.1f})")


if __name__ == "__main__":
    main()
