# /// script
# dependencies = ["fonttools", "numpy", "scikit-learn", "joblib", "uharfbuzz"]
# ///
"""Train the sidebearing model on the fonts macOS ships, and report what it is worth.

The system fonts are the training set on purpose. They are not fonts anyone here wants
to modify — most are proprietary — so nothing that gets patched later has been learned
from itself, and the score is always a score on a face the model has not seen. What is
kept is the model, which holds no outlines: only how spacing follows from shape.

Families are held out whole. A family's weights share their designer's habits, so
testing on a sibling of a font in the training set would flatter the model.

Google Fonts can be cloned into `scratchpad/gfonts` and read as well, and it was: 1,821
families against 112, and the held-out error rose from 9.6 units to 10.6. A corpus that
is mostly unreviewed work teaches the unreviewed consensus, and filtering it by `care()`
only made it worse by cutting the data further. `--system` is the default worth using.

    uv run train_spacing.py --system
    uv run train_spacing.py --system --check ~/Library/Fonts/Literata/static/Literata-Regular.ttf
"""

import argparse
import concurrent.futures
import glob
import os

import joblib
import numpy as np
from fontTools.ttLib import TTCollection
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import GroupKFold

from spacing_model import CYRILLIC, OWN, SAMPLES, care, centred, extract

HERE = os.path.dirname(os.path.abspath(__file__))
ROOTS = ("/System/Library/Fonts", "/System/Library/Fonts/Supplemental")
CORPUS = os.path.join(HERE, "scratchpad", "gfonts")
MODEL = os.path.join(HERE, "spacing-model.joblib")
CACHE = os.path.join(HERE, "scratchpad", "system-sides.npz")
KERNS = 0.02  # kerning coverage below which a script's spacing was not reviewed

# The corpus contains the very fonts this repository patches, and a model that has read
# Jost's own Cyrillic will propose Jost's own Cyrillic. Nothing gets learned from itself.
EXCLUDE = ("jost", "literata", "spectral", "inter", "geist", "ibm plex", "roboto flex",
           "sofia sans", "stix", "pliant")

# Faces whose spacing is not a function of shape: a monospace advance is fixed before
# any glyph is drawn, and a script face is spaced so its strokes join up.
NOT_TEXT = ("mono", "courier", "zapfino", "chancery", "bradley", "trattatello", "luminari",
            "comic", "papyrus", "marker", "brush", "script", "hand", "typewriter", "stencil",
            "impact", "phosphate", "chalkduster", "herculanum", "ayuthaya", "silom", "krungthep")


def faces(corpus=True):
    """Every text face on the machine, and every one in the Google Fonts corpus."""
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
    if corpus and os.path.isdir(CORPUS):
        for licence in ("ofl", "apache", "ufl"):
            for path in sorted(glob.glob(f"{CORPUS}/{licence}/*/*.ttf")):
                yield path, 0


def one(job):
    """Everything one face teaches: its Latin sides, and its Cyrillic where it has any."""
    path, index = job
    if any(word in os.path.basename(path).lower() for word in NOT_TEXT):
        return []
    try:
        found = extract(path, index)
    except Exception:
        return []
    if len(found) < 40:  # a face missing most of the alphabet teaches little
        return []
    family = found[0]["family"].lower()
    if any(word in family for word in NOT_TEXT):
        return []
    if any(family.startswith(word) for word in EXCLUDE):
        return []
    try:
        attention = care(path, index)
    except Exception:
        return []
    for row in found:
        row["script"] = 0

    # A Cyrillic ж or Ч is a shape Latin never makes, and the model cannot guess what a
    # designer does with an arm that overhangs unless it has been shown one. Only faces
    # whose Cyrillic kerning says somebody reviewed that script are worth learning from.
    if (attention["cyrillic kerning"] or 0) > KERNS:
        try:
            for row in extract(path, index, letters=CYRILLIC):
                row["script"] = 1
                found.append(row)
        except Exception:
            pass

    targets, _ = centred(found)
    for row, target in zip(found, targets):
        row["centred"] = target
        row["kerned"] = attention["latin kerning"]
        row["rounded"] = attention["round numbers"]
        row["system"] = float(path.startswith(ROOTS))
    return found


def harvest(corpus=True):
    jobs = list(faces(corpus))
    print(f"reading {len(jobs)} faces")
    rows = []
    with concurrent.futures.ProcessPoolExecutor() as pool:
        for done, found in enumerate(pool.map(one, jobs, chunksize=8), 1):
            rows += found
            if done % 500 == 0:
                print(f"  {done}/{len(jobs)}, {len(rows)} sides")
    return rows


# Faces whose spacing no one doubts, kept out of every fit so the regimes can be compared
TRUSTED = ("palatino", "baskerville", "hoefler", "charter", "optima", "georgia", "times")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", nargs="*", default=[], help="fonts to score after training")
    parser.add_argument("--ablate", action="store_true", help="score cut-down feature sets too")
    parser.add_argument("--regimes", action="store_true", help="re-run the which-fonts-to-learn-from comparison")
    parser.add_argument("--system", action="store_true", help="learn from the macOS fonts alone")
    parser.add_argument("--reharvest", action="store_true", help="re-read the fonts rather than the cache")
    args = parser.parse_args()

    if os.path.exists(CACHE) and not args.reharvest:
        held = np.load(CACHE, allow_pickle=True)
        X, y, groups, scales = held["X"], held["y"], held["groups"], held["scales"]
        kerned, rounded = held["kerned"], held["rounded"]
        system, script = held["system"], held["script"]
    else:
        rows = harvest(not args.system)
        X = np.array([row["features"] for row in rows])
        y = np.array([row["centred"] for row in rows])
        groups = np.array([row["family"] for row in rows])
        scales = np.array([row["xheight"] for row in rows])
        kerned = np.array([row["kerned"] for row in rows])
        rounded = np.array([row["rounded"] for row in rows])
        system = np.array([row["system"] for row in rows])
        script = np.array([row["script"] for row in rows])
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        np.savez_compressed(CACHE, X=X, y=y, groups=groups, scales=scales,
                            kerned=kerned, rounded=rounded, system=system, script=script)
    print(f"{len(y)} sides, {len(set(groups))} families, {X.shape[1]} features")
    print(f"null error {np.abs(y * scales).mean():.1f} units at 1000 upem")

    build = lambda: HistGradientBoostingRegressor(
        max_iter=1200, learning_rate=0.05, max_leaf_nodes=63, min_samples_leaf=40)

    folds = list(GroupKFold(n_splits=5).split(X, y, groups))

    def score(columns, label, split=False):
        errors, where = [], []
        for train, test in folds:
            predicted = build().fit(X[train][:, columns], y[train]).predict(X[test][:, columns])
            errors.append(np.abs((y[test] - predicted) * scales[test]))
            where.append(test)
        errors, where = np.concatenate(errors), np.concatenate(where)
        print(f"  {label:34s} {errors.mean():5.1f} units")
        if not split:
            return
        # The corpus is mostly amateur work, so the average is a harder test than the
        # fonts anyone here would set text in. These are the subsets worth reading.
        for mask, name in ((system[where] > 0, "on the fonts macOS ships"),
                           (script[where] == 0, "on Latin"),
                           (script[where] > 0, "on Cyrillic"),
                           ((system[where] > 0) & (script[where] == 0), "on macOS Latin")):
            print(f"    {name:32s} {errors[mask].mean():5.1f} units, {int(mask.sum()):7d} sides")

    # Which fonts to learn from: a face that kerns nothing and rounds every sidebearing
    # to ten has not been spaced so much as defaulted, and teaching on it teaches that.
    trusted = np.array([any(word in str(f).lower() for word in TRUSTED) for f in groups])

    def regime(mask, label, rounds=1, match=None):
        keep = mask & ~trusted
        if match is not None:  # a fair comparison needs the same amount of data, not just
            spare = np.flatnonzero(keep)  # the same fonts minus the ones we distrust
            drop = np.random.default_rng(0).choice(spare, max(len(spare) - match, 0), replace=False)
            keep = keep.copy()
            keep[drop] = False
        weights = np.ones(keep.sum())
        for _ in range(rounds):
            model = build().fit(X[keep], y[keep], sample_weight=weights)
            if rounds > 1:  # let the consensus vote the odd font out
                residual = np.abs(y[keep] - model.predict(X[keep]))
                for family in set(groups[keep]):
                    rows = groups[keep] == family
                    weights[rows] = 1.0 / (1.0 + (residual[rows].mean() / np.median(residual)) ** 2)
        error = np.abs((y[trusted] - model.predict(X[trusted])) * scales[trusted]).mean()
        print(f"  {label:38s} {error:5.1f} units on the trusted faces, {keep.sum():6d} sides")

    everything = np.arange(X.shape[1])
    print("held out families, never seen in training:")
    score(everything, "everything", split=True)
    if args.regimes:
        print(f"\nheld out for judging: {len(set(groups[trusted]))} trusted families")
        print("what to train on, judged on faces no one doubts:")
        regime(np.ones(len(y), bool), "every font")
        regime(rounded < 0.35, "dropping the ones that round to ten")
        regime(kerned > 0.02, "dropping the ones that barely kern")
        regime((rounded < 0.35) & (kerned > 0.02), "dropping both")
        regime(np.ones(len(y), bool), "every font, consensus reweighted", rounds=3)
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
