from milaun.blocking import BlockingIndex, blocking_keys, pair_completeness
from milaun.phonetic import name_keys


def test_blocking_keys_are_produced():
    keys = blocking_keys(name_keys("Prabesh Dahal"))
    assert keys
    assert all(key.startswith(("t:", "s:")) for key in keys)


def test_empty_name_has_no_keys():
    assert blocking_keys(name_keys("")) == ()


def test_variants_share_a_blocking_key():
    a = blocking_keys(name_keys("प्रवेश दाहाल"))
    b = blocking_keys(name_keys("Prabesh Dahal"))
    assert set(a) & set(b)


def test_candidate_pairs_find_variants():
    records = [
        name_keys("Prabesh Dahal"),
        name_keys("Prabesh Dahall"),
        name_keys("Sita Sharma"),
    ]
    index = BlockingIndex().build(records)
    pairs = index.candidate_pairs()
    assert (0, 1) in pairs
    assert (0, 2) not in pairs


def test_stats_reduction_and_completeness():
    records = [name_keys(name) for name in ["Ram Thapa", "Ram Thapa", "Sita Rai"]]
    index = BlockingIndex().build(records)
    stats = index.stats()
    assert stats.n_records == 3
    assert stats.total_possible_pairs == 3
    assert 0.0 <= stats.reduction_ratio <= 1.0
    assert pair_completeness({(0, 1)}, {(0, 1)}) == 1.0
    assert pair_completeness(set(), {(0, 1)}) == 0.0
    assert pair_completeness({(0, 1)}, set()) == 1.0


def test_empty_index():
    stats = BlockingIndex().stats()
    assert stats.n_records == 0
    assert stats.n_candidate_pairs == 0
    assert stats.reduction_ratio == 0.0
