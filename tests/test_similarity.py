import pytest

from milaun.phonetic import name_keys
from milaun.similarity import (
    FEATURES,
    dice,
    jaro,
    jaro_winkler,
    levenshtein,
    pair_features,
    ratio,
    token_best_match,
    token_min_sim,
)


def test_levenshtein_basics():
    assert levenshtein("", "") == 0
    assert levenshtein("abc", "") == 3
    assert levenshtein("kitten", "sitting") == 3
    assert levenshtein("abc", "abc") == 0


def test_ratio_bounds():
    assert ratio("abc", "abc") == 1.0
    assert ratio("", "") == 1.0
    assert ratio("abc", "xyz") == 0.0
    assert 0.0 <= ratio("prabesh", "pravesh") <= 1.0


def test_jaro_identical_and_empty():
    assert jaro("same", "same") == 1.0
    assert jaro("", "x") == 0.0
    assert jaro("martha", "marhta") > 0.9


def test_jaro_winkler_rewards_prefix():
    assert jaro_winkler("prabesh", "prabin") >= jaro("prabesh", "prabin")
    assert jaro_winkler("dahal", "dahal") == 1.0


def test_dice_handles_short_and_empty():
    assert dice("", "abc") == 0.0
    assert dice("a", "a") == 1.0
    assert dice("abcde", "abcdf") == 0.75


def test_token_best_match_is_order_invariant():
    left = name_keys("Prabesh Dahal").keys
    right = name_keys("Dahal Prabesh").keys
    assert token_best_match(left, right) == pytest.approx(1.0)


def test_token_min_penalises_one_weak_token():
    a = name_keys("Prabesh Dahal")
    b = name_keys("Prabin Dahal")
    c = name_keys("Prabesh Dahal")
    assert token_min_sim(a, b) < token_min_sim(a, c)


def test_features_are_symmetric_and_complete():
    a = name_keys("Sita Sharma")
    b = name_keys("सीता शर्मा")
    forward = pair_features(a, b)
    backward = pair_features(b, a)
    assert set(forward) == set(FEATURES)
    for name in FEATURES:
        assert forward[name] == pytest.approx(backward[name])
        assert 0.0 <= forward[name] <= 1.0


def test_features_on_empty_names_are_zero():
    empty = name_keys("")
    features = pair_features(empty, name_keys("Ram Thapa"))
    assert all(value == 0.0 for value in features.values())
