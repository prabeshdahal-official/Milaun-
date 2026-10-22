"""Probability calibration.

A raw logistic score is a ranking signal, not a probability: the fraction of
true matches among pairs scored 0.80 depends on the training distribution. For
identity work the number has operational meaning ("auto-merge above 0.95"), so
scores are mapped through a fitted curve and the result is reported with
expected calibration error.

Two methods are provided:

``platt``
    Two-parameter sigmoid on the logit of the raw score. Smooth, needs few
    calibration points, and is the packaged default.

``isotonic``
    Pool-adjacent-violators. More flexible but prone to step artefacts when the
    calibration split is small, which is why it is not the default.
"""

from __future__ import annotations

import json
import math
from bisect import bisect_right
from pathlib import Path


def _sigmoid(z: float) -> float:
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    exp_z = math.exp(z)
    return exp_z / (1.0 + exp_z)


def _logit(value: float) -> float:
    clipped = min(max(value, 1e-6), 1.0 - 1e-6)
    return math.log(clipped / (1.0 - clipped))


# --------------------------------------------------------------------- Platt
def fit_platt(
    scores: list[float],
    labels: list[int],
    epochs: int = 3000,
    learning_rate: float = 0.1,
    l2: float = 1e-3,
) -> dict[str, float]:
    """Fit ``sigmoid(a * logit(score) + b)`` by gradient descent."""
    if len(scores) != len(labels):
        raise ValueError("scores and labels must have the same length")
    if not scores:
        raise ValueError("cannot calibrate on an empty dataset")

    zs = [_logit(value) for value in scores]
    a, b = 1.0, 0.0
    n = len(zs)
    for _ in range(epochs):
        grad_a = grad_b = 0.0
        for z, label in zip(zs, labels, strict=False):
            error = _sigmoid(a * z + b) - label
            grad_a += error * z
            grad_b += error
        a -= learning_rate * (grad_a / n + l2 * a)
        b -= learning_rate * grad_b / n
    return {"a": float(a), "b": float(b)}


def apply_platt(params: dict[str, float], value: float) -> float:
    return _sigmoid(float(params.get("a", 1.0)) * _logit(value) + float(params.get("b", 0.0)))


# ------------------------------------------------------------------ isotonic
def fit_isotonic(scores: list[float], labels: list[int]) -> dict[str, list[float]]:
    """Fit a monotone, piecewise-linear map with pool-adjacent-violators."""
    if len(scores) != len(labels):
        raise ValueError("scores and labels must have the same length")
    if not scores:
        raise ValueError("cannot calibrate on an empty dataset")

    order = sorted(range(len(scores)), key=lambda i: scores[i])
    # Each block: [weight, sum_labels, first_x, last_x]
    blocks: list[list[float]] = []
    for index in order:
        x = float(scores[index])
        blocks.append([1.0, float(labels[index]), x, x])
        while len(blocks) > 1:
            left, right = blocks[-2], blocks[-1]
            if left[1] / left[0] <= right[1] / right[0]:
                break
            blocks[-2] = [left[0] + right[0], left[1] + right[1], left[2], right[3]]
            blocks.pop()

    xs = [block[2] for block in blocks]
    ys = [block[1] / block[0] for block in blocks]
    if xs[0] > 0.0:
        xs.insert(0, 0.0)
        ys.insert(0, ys[0])
    if xs[-1] < 1.0:
        xs.append(1.0)
        ys.append(ys[-1])
    return {"x": xs, "y": ys}


def apply_isotonic(knots: dict[str, list[float]] | None, value: float) -> float:
    """Map a raw score through the fitted curve, interpolating between knots."""
    if not knots:
        return min(max(value, 0.0), 1.0)
    xs = knots["x"]
    ys = knots["y"]
    if value <= xs[0]:
        return float(ys[0])
    if value >= xs[-1]:
        return float(ys[-1])
    position = bisect_right(xs, value) - 1
    left_x, right_x = xs[position], xs[position + 1]
    left_y, right_y = ys[position], ys[position + 1]
    if right_x == left_x:
        return float(right_y)
    share = (value - left_x) / (right_x - left_x)
    return float(left_y + share * (right_y - left_y))


def apply_calibration(calibration: dict | None, value: float) -> float:
    """Apply a calibration payload of either method."""
    if not calibration:
        return min(max(value, 0.0), 1.0)
    method = calibration.get("method", "platt")
    params = calibration.get("params", {})
    if method == "isotonic":
        return apply_isotonic(params, value)
    return apply_platt(params, value)


# -------------------------------------------------------------------- metrics
def brier(scores: list[float], labels: list[int]) -> float:
    """Brier score: mean squared error of probabilistic predictions."""
    if not scores:
        return 0.0
    return sum((s - y) ** 2 for s, y in zip(scores, labels, strict=False)) / len(scores)


def expected_calibration_error(scores: list[float], labels: list[int], bins: int = 10) -> float:
    """Weighted gap between predicted and observed frequency, equal-width bins."""
    if not scores:
        return 0.0
    total = len(scores)
    error = 0.0
    for bucket in range(bins):
        low = bucket / bins
        high = (bucket + 1) / bins
        members = [
            (s, y)
            for s, y in zip(scores, labels, strict=False)
            if (low <= s < high) or (bucket == bins - 1 and s == 1.0)
        ]
        if not members:
            continue
        mean_score = sum(s for s, _ in members) / len(members)
        mean_label = sum(y for _, y in members) / len(members)
        error += abs(mean_score - mean_label) * len(members) / total
    return error


def reliability_table(
    scores: list[float], labels: list[int], bins: int = 10
) -> list[dict[str, float | int]]:
    """Per-bin counts and means, for the evaluation report."""
    rows: list[dict[str, float | int]] = []
    for bucket in range(bins):
        low = bucket / bins
        high = (bucket + 1) / bins
        members = [
            (s, y)
            for s, y in zip(scores, labels, strict=False)
            if (low <= s < high) or (bucket == bins - 1 and s == 1.0)
        ]
        if not members:
            continue
        rows.append(
            {
                "bin": f"{low:.1f}-{high:.1f}",
                "count": len(members),
                "mean_score": round(sum(s for s, _ in members) / len(members), 4),
                "observed_rate": round(sum(y for _, y in members) / len(members), 4),
            }
        )
    return rows


# ----------------------------------------------------------------------- I/O
def save_calibration(path: str | Path, method: str, params: dict, metadata: dict) -> None:
    payload = {"method": method, "params": params, "metadata": metadata}
    Path(path).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def load_calibration(path: str | Path) -> tuple[dict, dict]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    calibration = {"method": payload.get("method", "platt"), "params": payload.get("params", {})}
    return calibration, payload.get("metadata", {})
