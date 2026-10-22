import pytest

from milaun import Matcher


@pytest.fixture(scope="module")
def matcher():
    return Matcher()


def test_identical_names_score_high(matcher):
    result = matcher.compare("Prabesh Dahal", "Prabesh Dahal")
    assert result.probability > 0.9
    assert result.band == "match"


def test_cross_script_match(matcher):
    result = matcher.compare("प्रवेश दाहाल", "Prabesh Dahal")
    assert result.probability > 0.9


def test_different_people_score_low(matcher):
    result = matcher.compare("सीता शर्मा", "Sita Karki")
    assert result.probability < 0.5
    assert result.band == "distinct"


def test_result_payload_is_json_ready(matcher):
    payload = matcher.compare("Ram Thapa", "Ram Bahadur Thapa").as_dict()
    assert set(payload) == {"probability", "raw_score", "band", "features", "keys_a", "keys_b",
                            "reasons"}
    assert payload["reasons"]
    assert isinstance(payload["features"], dict)


def test_reasons_are_produced_for_close_names(matcher):
    result = matcher.compare("Bhattarai", "Bhattarai")
    assert any("Phonetic keys are identical" in reason for reason in result.reasons)


def test_threshold_validation():
    with pytest.raises(ValueError):
        Matcher(auto_threshold=0.4, review_threshold=0.9)
    with pytest.raises(ValueError):
        Matcher(auto_threshold=1.5, review_threshold=0.5)


def test_bands_follow_thresholds():
    matcher = Matcher(auto_threshold=0.8, review_threshold=0.3, use_packaged=False)
    assert matcher.decide(0.95) == "match"
    assert matcher.decide(0.5) == "review"
    assert matcher.decide(0.1) == "distinct"


def test_cost_sensitive_triage():
    matcher = Matcher(use_packaged=False)
    # Missing a duplicate is 10x worse than a false merge.
    assert matcher.triage_by_cost(0.2) == "match"
    assert matcher.triage_by_cost(0.05) == "distinct"
    with pytest.raises(ValueError):
        matcher.triage_by_cost(0.5, cost_false_match=0, cost_missed_match=1)


def test_dedupe_clusters_variants(matcher):
    records = [
        {"id": "1", "name": "प्रवेश दाहाल"},
        {"id": "2", "name": "Prabesh Dahal"},
        {"id": "3", "name": "Sita Sharma"},
        {"id": "4", "name": "Ramesh Karki"},
    ]
    result = matcher.dedupe(records)
    assert len(result["clusters"]) == 1
    cluster = result["clusters"][0]
    assert sorted(cluster["members"]) == ["1", "2"]
    assert cluster["size"] == 2
    assert result["stats"]["n_records"] == 4
    assert result["stats"]["clusters"] == 1


def test_dedupe_requires_name_field(matcher):
    with pytest.raises(KeyError):
        matcher.dedupe([{"id": "1"}], name_field="name")


def test_dedupe_empty(matcher):
    assert matcher.dedupe([])["clusters"] == []


def test_link_finds_cross_list_pairs(matcher):
    left = [{"id": "a1", "name": "Sita Sharma"}, {"id": "a2", "name": "Ram Thapa"}]
    right = [{"id": "b1", "name": "सीता शर्मा"}, {"id": "b2", "name": "Krishna Acharya"}]
    result = matcher.link(left, right)
    assert len(result["matches"]) == 1
    assert result["matches"][0]["left"] == "a1"
    assert result["matches"][0]["right"] == "b1"


def test_link_empty_side(matcher):
    assert matcher.link([], [{"id": "1", "name": "Ram"}])["matches"] == []


def test_describe_reports_configuration(matcher):
    info = matcher.describe()
    assert info["thresholds"] == {"auto": 0.9, "review": 0.55}
    assert "key_sim" in info["weights"]
    assert info["features"]
