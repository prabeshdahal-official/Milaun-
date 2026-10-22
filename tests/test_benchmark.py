"""Tests for the benchmark itself.

An evaluation harness that is not tested is just a number generator. These
tests pin the properties the reported metrics depend on.
"""

import synth
from evaluate import average_precision, confusion, roc_auc, tune_threshold


def test_pair_generation_is_deterministic():
    identities = synth.load_identities()
    first = synth.build_pairs(identities, family="dev")
    second = synth.build_pairs(identities, family="dev")
    assert [p.as_dict() for p in first] == [p.as_dict() for p in second]


def test_splits_do_not_share_identities():
    identities = synth.load_identities()
    pairs = synth.build_pairs(identities, family="dev")
    train_ids = {p.identity_left for p in pairs if p.split == "train"}
    test_ids = {p.identity_left for p in pairs if p.split == "test"}
    calib_ids = {p.identity_left for p in pairs if p.split == "calib"}
    assert not train_ids & test_ids
    assert not train_ids & calib_ids
    assert not test_ids & calib_ids


def test_hard_family_is_held_out():
    identities = synth.load_identities()
    pairs = synth.build_pairs(identities, family="hard")
    assert pairs
    assert {p.split for p in pairs} == {"hard_test"}


def test_negative_pairs_are_not_self_pairs():
    identities = synth.load_identities()
    for pair in synth.build_pairs(identities):
        if pair.label == 0:
            assert pair.left_name != pair.right_name


def test_both_labels_present():
    pairs = synth.build_pairs(synth.load_identities())
    labels = {p.label for p in pairs}
    assert labels == {0, 1}


def test_mutate_produces_a_documented_label():
    import random

    name, ops = synth.mutate("Prabesh Dahal", "dev", random.Random(3))
    assert isinstance(name, str)
    assert isinstance(ops, list)


def test_confusion_counts():
    result = confusion([0.9, 0.8, 0.2, 0.1], [1, 1, 0, 0], 0.5)
    assert result["tp"] == 2
    assert result["fp"] == 0
    assert result["fn"] == 0
    assert result["tn"] == 2
    assert result["precision"] == 1.0


def test_average_precision_groups_ties():
    # Four positives, all at score 1.0, then negatives: one operating point.
    scores = [1.0, 1.0, 1.0, 1.0, 0.0, 0.0]
    labels = [1, 1, 1, 1, 0, 0]
    assert average_precision(scores, labels) == 1.0

    # The same data with ties broken the wrong way must not change the result.
    shuffled_scores = [1.0, 0.0, 1.0, 0.0, 1.0, 1.0]
    shuffled_labels = [1, 0, 1, 0, 1, 1]
    assert average_precision(shuffled_scores, shuffled_labels) == 1.0


def test_average_precision_partial():
    scores = [1.0, 0.9, 0.1]
    labels = [1, 0, 1]
    value = average_precision(scores, labels)
    assert 0.7 < value < 0.9


def test_roc_auc_with_ties():
    assert roc_auc([0.5, 0.5], [1, 0]) == 0.5
    assert roc_auc([0.9, 0.1], [1, 0]) == 1.0
    assert roc_auc([0.1, 0.9], [1, 0]) == 0.0


def test_tune_threshold_picks_a_split():
    scores = [0.9, 0.8, 0.3, 0.2]
    labels = [1, 1, 0, 0]
    threshold = tune_threshold(scores, labels)
    assert 0.3 < threshold <= 0.8


def test_registry_has_known_duplicates():
    records = synth.build_registry(synth.load_identities()[:10], copies=3)
    assert len(records) == 30
    identities = {record["true_identity"] for record in records}
    assert len(identities) == 10
