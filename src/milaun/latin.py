"""Latin-script side of the phonetic projection.

Nepali has no standard romanisation. Clerks and applicants mix Hunterian,
IAST-style and ad-hoc English spellings, so the rules here are ordered
longest-first and deliberately collapse contrasts that Devanagari marks but
Latin typists routinely drop:

* aspiration (``k``/``kh``, ``t``/``th``, ``p``/``ph``) is merged;
* retroflex and dental stops are merged;
* ``v``/``w``/``b`` are merged (Nepali व is realised as [w] or [b]);
* vowel length is merged and diphthongs are folded (``ai`` -> E, ``au`` -> O).
"""

from __future__ import annotations

from milaun.charset import LATIN_DIGRAPHS, LATIN_SINGLES
from milaun.normalize import normalize_text

_VOWELS = frozenset("AIUEO")


def _fold_final_y(word: str) -> str:
    """Map a word-final ``y`` after a consonant onto ``I``.

    "-y" and "-i" are the same ending in Nepali romanisation
    (Chaudhary/Chaudhari, Pandey/Pande), but ``y`` is kept elsewhere because
    it is a real glide word-initially (Yadav).
    """
    if len(word) > 1 and word.endswith("Y") and word[-2] not in _VOWELS:
        return word[:-1] + "I"
    return word


def to_phonetic_stream(text: str) -> str:
    """Project Latin text onto canonical phonetic symbols."""
    text = normalize_text(text)
    words: list[str] = []
    current: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if not ch.isascii() or not ch.isalpha():
            if current:
                words.append(_fold_final_y("".join(current)))
                current = []
            i += 1
            continue
        matched = False
        for src, symbol in LATIN_DIGRAPHS:
            if text.startswith(src, i):
                current.append(symbol)
                i += len(src)
                matched = True
                break
        if matched:
            continue
        current.append(LATIN_SINGLES[ch])
        i += 1
    if current:
        words.append(_fold_final_y("".join(current)))
    return " ".join(words)


def to_latin(text: str) -> str:
    """Return a cleaned Latin form (identity for Latin input)."""
    return normalize_text(text)
