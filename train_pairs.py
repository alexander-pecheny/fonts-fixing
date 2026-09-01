# /// script
# dependencies = ["fonttools", "uharfbuzz", "numpy", "scikit-learn", "joblib"]
# ///
"""Train the pair model on the fonts macOS ships, and report what it is worth.

Same corpus and same discipline as `train_spacing.py`: system faces only, families held
out whole, and the fonts this repository patches excluded so nothing is learned from
itself. Each face's own tracking is removed before fitting, since how loose a font is
set is a choice made once for the whole face and not a fact about any pair.

    uv run train_pairs.py
    uv run train_pairs.py --check fonts/GeistFix/GeistFix-Regular.ttf
"""

import argparse
import concurrent.futures
import os

import joblib
import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import GroupKFold

import pair_model
from spacing_model import CYRILLIC, LETTERS, care
from train_spacing import EXCLUDE, KERNS, NOT_TEXT, ROOTS, TRUSTED, faces

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = os.path.join(HERE, "pair-model.joblib")
CACHE = os.path.join(HERE, "scratchpad", "system-pairs.npz")
KEEP = 1400  # pairs sampled per script per face, so no one face dominates


def one(job):
    path, index = job
    if any(word in os.path.basename(path).lower() for word in NOT_TEXT):
        return []
    try:
        attention = care(path, index)
        read = pair_model.sides(path, index, letters=LETTERS + CYRILLIC)
    except Exception:
        return []
    if not read or len(read["letters"]) < 40:
        return []

    from spacing import kerner
    from fontTools.ttLib import TTFont
    with open(path, "rb") as handle:
        kern = kerner(handle.read())
    family = (TTFont(path, fontNumber=index, lazy=True)["name"].getDebugName(16) or path).lower()
    if any(word in family for word in NOT_TEXT) or any(family.startswith(w) for w in EXCLUDE):
        return []

    rng = np.random.default_rng(abs(hash(path)) % 2**32)
    rows = []
    for script, alphabet in ((0, LETTERS), (1, CYRILLIC)):
        if script and (attention["cyrillic kerning"] or 0) <= KERNS:
            continue
        have = [c for c in alphabet if c in read["letters"]]
        if len(have) < 20:
            continue
        both = [(a, b) for a in have for b in have]
        pick = rng.choice(len(both), min(KEEP, len(both)), replace=False)
        found = pair_model.extract(path, index, letters=alphabet, kern=kern,
                                   pairs=[both[i] for i in pick])
        for row in found:
            row["script"] = script
        rows += found
    if not rows:
        return []
    mean = np.mean([row["target"] for row in rows if not row["script"]] or
                   [row["target"] for row in rows])
    for row in rows:
        row["centred"] = row["target"] - mean  # the face's own tracking is not a pair fact
        row["kerned"] = attention["latin kerning"]
    return rows


def harvest():
    jobs = [job for job in faces(corpus=False)]
    print(f"reading {len(jobs)} faces")
    rows = []
    with concurrent.futures.ProcessPoolExecutor() as pool:
        for done, found in enumerate(pool.map(one, jobs, chunksize=2), 1):
            rows += found
            if done % 40 == 0:
                print(f"  {done}/{len(jobs)}, {len(rows)} pairs")
    return rows


def build():
    return HistGradientBoostingRegressor(max_iter=600, learning_rate=0.08,
                                         max_leaf_nodes=63, min_samples_leaf=40)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", nargs="*", default=[])
    parser.add_argument("--reharvest", action="store_true")
    args = parser.parse_args()

    if os.path.exists(CACHE) and not args.reharvest:
        held = np.load(CACHE, allow_pickle=True)
        X, y, groups, scales, script = (held[k] for k in ("X", "y", "groups", "scales", "script"))
    else:
        rows = harvest()
        X = np.array([row["features"] for row in rows], dtype=np.float32)
        y = np.array([row["centred"] for row in rows])
        groups = np.array([row["family"] for row in rows])
        scales = np.array([row["xheight"] for row in rows])
        script = np.array([row["script"] for row in rows])
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        np.savez_compressed(CACHE, X=X, y=y, groups=groups, scales=scales, script=script)
    print(f"{len(y)} pairs, {len(set(groups))} families, {X.shape[1]} features")
    print(f"null error {np.abs(y * scales).mean():.1f} units at 1000 upem")

    errors, apart, where = [], [], []
    for train, test in GroupKFold(n_splits=3).split(X, y, groups):
        predicted = build().fit(X[train], y[train]).predict(X[test])
        errors.append(np.abs((y[test] - predicted) * scales[test]))
        apart.append(np.abs(y[test] - predicted))
        where.append(test)
    errors, apart, where = (np.concatenate(part) for part in (errors, apart, where))
    print(f"held out {errors.mean():5.1f} units, {apart.mean():.4f} x-heights")
    for mask, name in ((script[where] == 0, "Latin"), (script[where] > 0, "Cyrillic")):
        if mask.any():
            print(f"  {name:10s} {errors[mask].mean():5.1f} units, {int(mask.sum()):7d} pairs")
    trusted = np.array([any(w in str(f).lower() for w in TRUSTED) for f in groups])
    print(f"  {'trusted':10s} {errors[trusted[where]].mean():5.1f} units")

    # The error travels with the model. `fit` shrinks every move by it, and what the
    # model gets wrong on a face it has never seen is the honest figure for that — how
    # far a particular font disagrees is partly the font being wrong, which is the point.
    joblib.dump({"model": build().fit(X, y), "error": float(apart.mean())}, MODEL)
    print(f"wrote {MODEL}")


if __name__ == "__main__":
    main()
