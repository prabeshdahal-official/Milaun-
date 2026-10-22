"""Fit the packaged model and calibration curve.

Run from the repository root::

    python benchmarks/train.py

Writes ``src/milaun/data/model.json``, ``calibration.json`` and
``thresholds.json``. Training uses only the ``train`` split of the ``dev``
operation family; calibration uses ``calib``. The ``hard`` family is never
touched here, so it remains an honest held-out test.

Decision thresholds are a *policy*, not a fitted parameter: 0.90 for automatic
merging and 0.55 for human review are chosen to be conservative on identity
data, and this script reports what they cost on the calibration split rather
than tuning them to look good.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

BENCH_DIR = Path(__file__).resolve().parent
ROOT = BENCH_DIR.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(BENCH_DIR))

import synth  # noqa: E402

from milaun import model  # noqa: E402
from milaun.calibration import (  # noqa: E402
    apply_calibration,
    expected_calibration_error,
    fit_platt,
    save_calibration,
)
from milaun.phonetic import name_keys  # noqa: E402
from milaun.similarity import pair_features  # noqa: E402

DATA_DIR = ROOT / "src" / "milaun" / "data"
AUTO_THRESHOLD = 0.90
REVIEW_THRESHOLD = 0.55


def featurise(pairs: list[synth.Pair]) -> tuple[list[dict[str, float]], list[int]]:
    cache: dict[str, object] = {}

    def keys(name: str):
        if name not in cache:
            cache[name] = name_keys(name)
        return cache[name]

    rows = [pair_features(keys(pair.left_name), keys(pair.right_name)) for pair in pairs]
    labels = [pair.label for pair in pairs]
    return rows, labels


def raw_probabilities(pairs: list[synth.Pair], weights: dict[str, float]) -> list[float]:
    rows, _ = featurise(pairs)
    return [model.score(weights, row) for row in rows]


def operating_point(scores: list[float], labels: list[int], threshold: float) -> dict:
    tp = fp = fn = tn = 0
    for score, label in zip(scores, labels, strict=False):
        predicted = score >= threshold
        if predicted and label:
            tp += 1
        elif predicted and not label:
            fp += 1
        elif not predicted and label:
            fn += 1
        else:
            tn += 1
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "threshold": threshold,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "false_positive_rate": round(fp / (fp + tn), 4) if fp + tn else 0.0,
    }


def main() -> int:
    identities = synth.load_identities()
    pairs = synth.build_pairs(identities, family="dev")
    train_pairs = [pair for pair in pairs if pair.split == "train"]
    calib_pairs = [pair for pair in pairs if pair.split == "calib"]
    test_pairs = [pair for pair in pairs if pair.split == "test"]

    print(
        f"identities={len(identities)} train={len(train_pairs)} "
        f"calib={len(calib_pairs)} test={len(test_pairs)}"
    )

    train_rows, train_labels = featurise(train_pairs)
    weights = model.train(train_rows, train_labels, l2=5e-3)
    print("fitted weights:")
    for name, value in weights.items():
        print(f"  {name:>14}: {value:+.4f}")

    calib_raw = raw_probabilities(calib_pairs, weights)
    calib_labels = [pair.label for pair in calib_pairs]
    platt = fit_platt(calib_raw, calib_labels)
    calibration = {"method": "platt", "params": platt}
    calib_scores = [apply_calibration(calibration, value) for value in calib_raw]

    ece = expected_calibration_error(calib_scores, calib_labels)
    auto_point = operating_point(calib_scores, calib_labels, AUTO_THRESHOLD)
    print(f"calibration ECE (in-sample) = {ece:.4f}")
    print(f"at auto={AUTO_THRESHOLD}: precision={auto_point['precision']} "
          f"recall={auto_point['recall']} fpr={auto_point['false_positive_rate']}")
    if auto_point["precision"] < 0.98:
        print(
            "WARNING: the fixed auto threshold does not reach 0.98 precision "
            "on calibration data."
        )

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    model.save_model(
        DATA_DIR / "model.json",
        weights,
        {
            "trained_on": "benchmarks/synth.py dev/train split",
            "n_train": len(train_pairs),
            "seed": synth.DEFAULT_SEED,
            "features": list(model.FEATURES),
            "note": "synthetic benchmark; refit on your own labelled pairs before production use",
        },
    )
    save_calibration(
        DATA_DIR / "calibration.json",
        "platt",
        platt,
        {
            "fitted_on": "benchmarks/synth.py dev/calib split",
            "n_calib": len(calib_pairs),
            "ece_in_sample": round(ece, 6),
        },
    )
    (DATA_DIR / "thresholds.json").write_text(
        json.dumps(
            {
                "thresholds": {"auto": AUTO_THRESHOLD, "review": REVIEW_THRESHOLD},
                "policy": "fixed conservative defaults, not fitted",
                "calibration_check": auto_point,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"wrote artifacts to {DATA_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


