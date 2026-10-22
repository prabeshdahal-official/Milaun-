import pytest

from milaun.devanagari import to_latin, to_phonetic_stream
from milaun.phonetic import name_keys, phonetic_key, skeleton_key


@pytest.mark.parametrize(
    "devanagari, latin",
    [
        ("प्रवेश दाहाल", "Prabesh Dahal"),
        ("सीता शर्मा", "Sita Sharma"),
        ("भट्टराई", "Bhattarai"),
        ("न्यौपाने", "Neupane"),
        ("पौडेल", "Poudel"),
        ("कुँवर", "Kunwar"),
        ("तामाङ", "Tamang"),
        ("आचार्य", "Acharya"),
        ("चौधरी", "Chaudhary"),
        ("पाण्डे", "Pandey"),
        ("खड्का", "Khadka"),
        ("श्रेष्ठ", "Shrestha"),
        ("गुरुङ", "Gurung"),
        ("अधिकारी", "Adhikari"),
        ("सुवेदी", "Subedi"),
        ("राई", "Rai"),
        ("थापा", "Thapa"),
        ("महर्जन", "Maharjan"),
        ("तिमिल्सिना", "Timilsina"),
        ("रेग्मी", "Regmi"),
        ("चौधरी", "Chaudhari"),
    ],
)
def test_cross_script_keys_agree(devanagari, latin):
    assert phonetic_key(devanagari) == phonetic_key(latin)


def test_epenthetic_schwa_is_absorbed_by_skeleton():
    # सापकोटा is written with an extra vowel that Latin transliterations drop.
    assert phonetic_key("सापकोटा") != phonetic_key("Sapkota")
    assert skeleton_key("सापकोटा") == skeleton_key("Sapkota")


def test_token_order_does_not_change_the_key():
    assert phonetic_key("Prabesh Dahal") == phonetic_key("Dahal Prabesh")


def test_distinct_names_keep_distinct_keys():
    assert phonetic_key("Prabesh Dahal") != phonetic_key("Ramesh Karki")


def test_final_schwa_is_deleted():
    assert phonetic_key("Rama") == phonetic_key("Ram")
    assert phonetic_key("रामा") == phonetic_key("राम")


def test_aspiration_is_merged_but_skeleton_survives():
    assert phonetic_key("Khadka") == phonetic_key("Kadka")


def test_palatalised_nasal():
    # न्य is pronounced "n", so न्यौपाने must line up with "Neupane".
    assert phonetic_key("न्यौपाने") == phonetic_key("Neupane")


def test_halant_cluster():
    assert phonetic_key("कृष्ण") == phonetic_key("Krishna")


def test_empty_name():
    keys = name_keys("")
    assert keys.key == ""
    assert keys.skeleton == ""
    assert keys.tokens == ()


@pytest.mark.parametrize("name", ["Prabesh Dahal", "प्रवेश दाहाल", "  RAM  ", "sita"])
def test_normalisation_is_idempotent(name):
    once = name_keys(name)
    twice = name_keys(once.normalized)
    assert once.key == twice.key


def test_latin_rendering_is_readable():
    assert to_latin("प्रवेश दाहाल") == "pravesh dahal"
    assert to_phonetic_stream("सीता") == "SITA"


def test_name_keys_as_dict_roundtrip():
    payload = name_keys("Prabesh Dahal").as_dict()
    assert payload["key"] == phonetic_key("Prabesh Dahal")
    assert payload["tokens"] == ["prabesh", "dahal"]
