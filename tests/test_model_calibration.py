import json
import math

import pytest

from milaun import model
from milaun.calibration import (
    apply_calibration,
    apply_isotonic,
    brier,
    expected_calibration_error,
    fit_isotonic,
    fit_platt,
    load_calibration,
    reliability_table,
    save_calibration,
)
from milaun.similarity import FEATURES


def test_sigmoid_is_stable_at_extremes():
    assert model.sigmoid(0) == pytest.approx(0.5)
    assert model.sigmoid(1000) == pytest.approx(1.0)
    assert model.sigmoid(-1000) == pytest.approx(0.0)
    assert 0.0 < model.sigmoid(-40) < 1e-10


def test_score_uses_all_features():
    weights = {name: 1.0 for name in FEATURES}
    weights["bias"] = -3.0
    features = {name: 1.0 for name in FEATURES}
    expected = model.sigmoid(-3.0 + len(FEATURES))
    assert model.score(weights, features) == pytest.approx(expected)


def test_training_produces_non_negative_weights():
    rows = []
    labels = []
    for index in range(40):
        rows.append({name: 1.0 for name in FEATURES} if index % 2 == 0 else
                    {name: 0.0 for name in FEATURES})
        labels.append(index % 2 == 0)
    weights = model.train(rows, [int(label) for label in labels], l2=1e-2)
    assert all(weights[name] >= 0.0 for name in FEATURES)
    assert weights["bias"] < 0.0


def test_training_validates_input():
    with pytest.raises(ValueError):
        model.train([], [])
    with pytest.raises(ValueError):
        model.train([{name: 1.0 for name in FEATURES}], [])


def test_model_roundtrip(tmp_path):
    path = tmp_path / "model.json"
    weights = {name: 0.5 for name in FEATURES}
    weights["bias"] = -1.0
    model.save_model(path, weights, {"note": "test"})
    loaded, metadata = model.load_model(path)
    assert loaded["bias"] == pytest.approx(-1.0)
    assert metadata["note"] == "test"


def test_platt_improves_monotonicity():
    scores = [0.1, 0.2, 0.7, 0.8, 0.9, 0.95]
    labels = [0, 0, 1, 1, 1, 1]
    params = fit_platt(scores, labels)
    calibration = {"method": "platt", "params": params}
    calibrated = [apply_calibration(calibration, value) for value in scores]
    assert calibrated == sorted(calibrated)
    assert 0.0 <= calibrated[0] <= calibrated[-1] <= 1.0


def test_isotonic_is_monotone():
    scores = [0.9, 0.1, 0.8, 0.2, 0.7, 0.3]
    labels = [1, 0, 1, 0, 1, 0]
    knots = fit_isotonic(scores, labels)
    ys = knots["y"]
    assert all(ys[i] <= ys[i + 1] + 1e-12 for i in range(len(ys) - 1))
    assert apply_isotonic(knots, 0.0) <= apply_isotonic(knots, 1.0)


def test_apply_without_calibration_is_identity():
    assert apply_calibration(None, 0.42) == pytest.approx(0.42)
    assert apply_calibration(None, -1.0) == 0.0
    assert apply_calibration(None, 2.0) == 1.0


def test_metrics():
    scores = [0.9, 0.8, 0.2, 0.1]
    labels = [1, 1, 0, 0]
    assert brier(scores, labels) == pytest.approx((0.01 + 0.04 + 0.04 + 0.01) / 4)
    assert expected_calibration_error(scores, labels) < 0.2
    table = reliability_table(scores, labels, bins=2)
    assert sum(row["count"] for row in table) == 4


def test_calibration_roundtrip(tmp_path):
    path = tmp_path / "calibration.json"
    save_calibration(path, "platt", {"a": 1.5, "b": -0.2}, {"note": "x"})
    calibration, metadata = load_calibration(path)
    assert calibration["method"] == "platt"
    assert calibration["params"]["a"] == pytest.approx(1.5)
    assert metadata["note"] == "x"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert "params" in payload


def test_invalid_inputs_raise():
    with pytest.raises(ValueError):
        fit_platt([], [])
    with pytest.raises(ValueError):
        fit_isotonic([0.5], [1, 0])


def test_logit_handles_zero_and_one():
    # Through apply_platt the logit is clipped, so exact 0/1 must not raise.
    value = apply_calibration({"method": "platt", "params": {"a": 1.0, "b": 0.0}}, 1.0)
    assert math.isfinite(value)
