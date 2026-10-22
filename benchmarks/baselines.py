"""Baselines for the evaluation.

Each baseline gets the same inputs the model gets, and Devanagari names are
transliterated first so that Latin-only algorithms are not failed for a reason
that has nothing to do with their similarity logic. That is generous to the
baselines, which is the point: the comparison should be hard to win.

* ``exact``            normalised string equality
* ``levenshtein``      normalised edit similarity on the Latin form
* ``jaro_winkler``     Jaro-Winkler on the Latin form
* ``soundex``          classic American Soundex on Latin tokens
* ``latin_metaphone``  the Latin-side phonetic encoder only (no Devanagari rules)
"""

from __future__ import annotations

from milaun import latin
from milaun.phonetic import name_keys
from milaun.similarity import jaro_winkler, ratio

_SOUNDEX_CODES = {
    "b": "1", "f": "1", "p": "1", "v": "1",
    "c": "2", "g": "2", "j": "2", "k": "2", "q": "2", "s": "2", "x": "2", "z": "2",
    "d": "3", "t": "3",
    "l": "4",
    "m": "5", "n": "5",
    "r": "6",
}


def soundex(word: str) -> str:
    """Classic Soundex: first letter plus three consonant codes."""
    letters = [ch for ch in word.lower() if ch.isalpha()]
    if not letters:
        return "0000"
    first = letters[0]
    encoded = first.upper()
    previous = _SOUNDEX_CODES.get(first, "")
    for char in letters[1:]:
        code = _SOUNDEX_CODES.get(char, "")
        if code and code != previous:
            encoded += code
        if char not in "hw":
            previous = code
    return (encoded + "000")[:4]


def _latin_pair(left: str, right: str) -> tuple[str, str]:
    return name_keys(left).latin, name_keys(right).latin


def exact(left: str, right: str) -> float:
    a, b = _latin_pair(left, right)
    return 1.0 if a == b else 0.0


def levenshtein(left: str, right: str) -> float:
    a, b = _latin_pair(left, right)
    return ratio(a, b)


def jaro_winkler_baseline(left: str, right: str) -> float:
    a, b = _latin_pair(left, right)
    return jaro_winkler(a, b)


def soundex_baseline(left: str, right: str) -> float:
    a, b = _latin_pair(left, right)
    key_a = "|".join(sorted(soundex(token) for token in a.split()))
    key_b = "|".join(sorted(soundex(token) for token in b.split()))
    return 1.0 if key_a == key_b else 0.0


def latin_metaphone(left: str, right: str) -> float:
    a, b = _latin_pair(left, right)
    return ratio(latin.to_phonetic_stream(a), latin.to_phonetic_stream(b))


BASELINES = {
    "exact": exact,
    "levenshtein": levenshtein,
    "jaro_winkler": jaro_winkler_baseline,
    "soundex": soundex_baseline,
    "latin_metaphone": latin_metaphone,
}
