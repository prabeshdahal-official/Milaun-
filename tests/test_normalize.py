from milaun.normalize import (
    dominant_script,
    has_devanagari,
    normalize_text,
    script_of,
    tokenize,
)


def test_preserves_devanagari_matra():
    # Regression: a regex based on \w deletes combining marks and silently
    # corrupts every Devanagari name.
    assert normalize_text("सीता") == "सीता"
    assert "\u0940" in normalize_text("सीता")


def test_collapses_whitespace_and_punctuation():
    assert normalize_text("  Prabesh   Dahal. ") == "prabesh dahal"
    assert normalize_text("Dahal, Prabesh") == "dahal prabesh"


def test_devanagari_digits_become_ascii():
    assert normalize_text("क्रम १२३") == "क्रम 123"


def test_strips_zero_width_and_nukta_preserved():
    assert normalize_text("प्र\u200dवेश") == "प्रवेश"


def test_none_and_non_string():
    assert normalize_text(None) == ""
    assert normalize_text(1234) == "1234"


def test_script_detection():
    assert script_of("प्रवेश") == "devanagari"
    assert script_of("prabesh") == "latin"
    assert script_of("prabeshप्रवेश") == "mixed"
    assert script_of("123") == "unknown"
    assert dominant_script("प्रवेश दाहाल") == "devanagari"
    assert dominant_script("Prabesh Dahal") == "latin"


def test_tokenize():
    assert tokenize(" Ram  Bahadur Thapa ") == ["ram", "bahadur", "thapa"]
    assert tokenize("") == []


def test_has_devanagari():
    assert has_devanagari("राम")
    assert not has_devanagari("ram")
