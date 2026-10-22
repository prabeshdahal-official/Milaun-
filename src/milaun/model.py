"""A tiny, dependency-free logistic scorer.

Six features do not justify a machine-learning framework, and a model that
cannot be inspected line by line is a poor fit for a tool used on identity
records. This module is therefore Newton-Raphson (IRLS) on a small design
matrix, with weights stored as plain JSON.

Two details matter for reproducibility and interpretation:

* Ridge regularisation is applied to the feature weights (not the intercept).
  On separable data the unregularised maximum-likelihood solution diverges, so
  the ridge term is what keeps the numbers finite and stable across retraining.
* All six features are similarities, so a higher value must never mean *less*
  likely. An active-set step clamps negative weights to zero and re-solves.
  Without it, collinear features let the optimiser drive one weight negative to
  compensate for another, which predicts just as well but makes the per-pair
  explanation misleading.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from milaun.similarity import FEATURES, pair_features  # noqa: F401  (re-exported)

DEFAULT_WEIGHTS: dict[str, float] = {
    "bias": -7.0,
    "key_sim": 1.5,
    "skeleton_sim": 2.0,
    "key_dice": 1.0,
    "skeleton_dice": 1.5,
    "token_min_sim": 3.5,
    "first_token_sim": 3.0,
    "last_token_sim": 2.5,
    "latin_sim": 0.5,
}


def sigmoid(z: float) -> float:
    """Numerically stable logistic function."""
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    exp_z = math.exp(z)
    return exp_z / (1.0 + exp_z)


def score(weights: dict[str, float], features: dict[str, float]) -> float:
    """Return the raw (uncalibrated) match probability."""
    z = float(weights.get("bias", 0.0))
    for name in FEATURES:
        z += float(weights.get(name, 0.0)) * float(features.get(name, 0.0))
    return sigmoid(z)


def _row(features: dict[str, float]) -> list[float]:
    return [float(features.get(name, 0.0)) for name in FEATURES]


def _solve(matrix: list[list[float]], vector: list[float]) -> list[float]:
    """Solve a small linear system by Gaussian elimination with pivoting."""
    size = len(vector)
    a = [list(row) + [vector[i]] for i, row in enumerate(matrix)]
    for column in range(size):
        pivot = max(range(column, size), key=lambda r: abs(a[r][column]))
        if abs(a[pivot][column]) < 1e-12:
            continue
        a[column], a[pivot] = a[pivot], a[column]
        for row in range(size):
            if row == column:
                continue
            factor = a[row][column] / a[column][column]
            if factor == 0.0:
                continue
            for k in range(column, size + 1):
                a[row][k] -= factor * a[column][k]
    return [
        a[i][size] / a[i][i] if abs(a[i][i]) > 1e-12 else 0.0
        for i in range(size)
    ]


def _loss(design: list[list[float]], labels: list[int], weights: list[float], l2: float) -> float:
    total = 0.0
    for row, label in zip(design, labels, strict=False):
        z = sum(w * x for w, x in zip(weights, row, strict=False))
        p = min(max(sigmoid(z), 1e-12), 1.0 - 1e-12)
        total -= label * math.log(p) + (1 - label) * math.log(1.0 - p)
    penalty = 0.5 * l2 * sum(w * w for w in weights[1:])
    return total / len(design) + penalty


def train(
    rows: list[dict[str, float]],
    labels: list[int],
    max_iter: int = 40,
    l2: float = 1e-3,
    non_negative: bool = True,
) -> dict[str, float]:
    """Fit logistic weights by IRLS with an optional non-negativity constraint."""
    if len(rows) != len(labels):
        raise ValueError("rows and labels must have the same length")
    if not rows:
        raise ValueError("cannot train on an empty dataset")

    design = [[1.0] + _row(row) for row in rows]
    size = len(design[0])
    n = len(design)
    weights = [0.0] * size
    current_loss = _loss(design, labels, weights, l2)

    for _ in range(max_iter):
        probabilities = [
            sigmoid(sum(w * x for w, x in zip(weights, row, strict=False)))
            for row in design
        ]
        gradient = [
            sum((probabilities[i] - labels[i]) * design[i][j] for i in range(n)) / n
            + (l2 * weights[j] if j > 0 else 0.0)
            for j in range(size)
        ]
        hessian = [
            [
                sum(
                    probabilities[i] * (1 - probabilities[i]) * design[i][a] * design[i][b]
                    for i in range(n)
                )
                / n
                + (l2 if a == b and a > 0 else 0.0)
                + (1e-10 if a == b else 0.0)
                for b in range(size)
            ]
            for a in range(size)
        ]
        step = _solve(hessian, [-value for value in gradient])

        scale = 1.0
        improved = False
        for _attempt in range(12):
            candidate = [w + scale * s for w, s in zip(weights, step, strict=False)]
            if non_negative:
                candidate = [candidate[0]] + [max(0.0, value) for value in candidate[1:]]
            candidate_loss = _loss(design, labels, candidate, l2)
            if candidate_loss <= current_loss + 1e-12:
                weights, current_loss = candidate, candidate_loss
                improved = True
                break
            scale /= 2.0
        if not improved:
            break
        if max(abs(scale * s) for s in step) < 1e-9:
            break

    fitted = {"bias": weights[0]}
    for name, value in zip(FEATURES, weights[1:], strict=False):
        fitted[name] = value
    return fitted


def save_model(path: str | Path, weights: dict[str, float], metadata: dict) -> None:
    """Write weights plus provenance metadata to JSON."""
    payload = {
        "weights": {k: round(float(v), 8) for k, v in weights.items()},
        "metadata": metadata,
    }
    Path(path).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def load_model(path: str | Path) -> tuple[dict[str, float], dict]:
    """Load weights and metadata, ignoring unknown feature names."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    weights = dict(DEFAULT_WEIGHTS)
    for name, value in payload.get("weights", {}).items():
        if name != "bias" and name not in FEATURES:
            continue
        weights[name] = float(value)
    return weights, payload.get("metadata", {})
