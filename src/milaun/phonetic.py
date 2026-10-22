"""Name-level phonetic keys.

A name is projected into two comparison keys:

``key``
    Canonical phonetics with vowels, tokens sorted so that word order does not
    matter. Roughly a Nepali-specific Metaphone.

``skeleton``
    The same stream with every vowel removed. It absorbs epenthetic schwa,
    which is the largest single source of Devanagari/Latin mismatch in Nepali
    names (प्रवेश -> "Pravesh", which a naive encoder renders "Prvesh").
"""

from __future__ import annotations

from dataclasses import dataclass

from milaun import devanagari, latin
from milaun.normalize import dominant_script, has_devanagari, normalize_text, tokenize

VOWELS = frozenset("AIUEO")

# Two adjacent vowel symbols denote one diphthong in South Asian romanisation.
# Folding them keeps आई ("-ai") aligned with Latin "ai" and औ ("au") with
# Latin "au"/"ou"/"o".
_VOWEL_PAIRS: dict[str, str] = {
    "AI": "E",
    "EI": "E",
    "IE": "E",
    "IA": "E",
    "AE": "E",
    "EA": "E",
    "AU": "O",
    "OU": "O",
    "OA": "O",
    "AO": "O",
    "UA": "O",
    "EU": "O",
    "EO": "O",
    "OE": "O",
    "UE": "O",
    "IO": "O",
    "OI": "O",
    "UI": "I",
    "IU": "I",
}


def _collapse_vowel_runs(stream: str) -> str:
    """Fold adjacent vowels into one symbol, repeatedly, left to right."""
    out: list[str] = []
    for symbol in stream:
        if symbol in VOWELS and out and out[-1] in VOWELS:
            pair = out[-1] + symbol
            out[-1] = _VOWEL_PAIRS.get(pair, out[-1])
        else:
            out.append(symbol)
    return "".join(out)


def _collapse_doubles(stream: str) -> str:
    out: list[str] = []
    for symbol in stream:
        if out and out[-1] == symbol:
            continue
        out.append(symbol)
    return "".join(out)


def _reduce_token(stream: str) -> tuple[str, str]:
    """Reduce one token's stream to ``(key, skeleton)``."""
    stream = _collapse_vowel_runs(stream)
    stream = _collapse_doubles(stream)
    # Word-final schwa deletion: राम -> "ram", Ramesha -> "Rames".
    if len(stream) > 1 and stream.endswith("A"):
        stream = stream[:-1]
    skeleton = "".join(symbol for symbol in stream if symbol not in VOWELS)
    return stream, skeleton


def stream_for_token(token: str) -> str:
    """Return the canonical phonetic stream for a single token."""
    if has_devanagari(token):
        return devanagari.to_phonetic_stream(token)
    return latin.to_phonetic_stream(token)


def latin_for_token(token: str) -> str:
    """Return a readable Latin form for a single token."""
    if has_devanagari(token):
        return devanagari.to_latin(token)
    return latin.to_latin(token)


@dataclass(frozen=True)
class NameKeys:
    """All derived representations of one name."""

    normalized: str
    latin: str
    script: str
    tokens: tuple[str, ...]
    keys: tuple[str, ...]
    skeletons: tuple[str, ...]
    key: str
    skeleton: str

    def as_dict(self) -> dict[str, object]:
        return {
            "normalized": self.normalized,
            "latin": self.latin,
            "script": self.script,
            "tokens": list(self.tokens),
            "keys": list(self.keys),
            "skeletons": list(self.skeletons),
            "key": self.key,
            "skeleton": self.skeleton,
        }


def name_keys(name: str) -> NameKeys:
    """Compute :class:`NameKeys` for a full name in either script."""
    normalized = normalize_text(name)
    tokens = tokenize(normalized)
    keys: list[str] = []
    skeletons: list[str] = []
    latin_words: list[str] = []
    for token in tokens:
        key, skeleton = _reduce_token(stream_for_token(token))
        if not key:
            continue
        keys.append(key)
        skeletons.append(skeleton)
        latin_words.append(latin_for_token(token))
    # Sorting makes the full-name key order-invariant so that "Dahal Prabesh"
    # and "Prabesh Dahal" share a key.
    return NameKeys(
        normalized=normalized,
        latin=" ".join(latin_words),
        script=dominant_script(normalized),
        tokens=tuple(tokens),
        keys=tuple(keys),
        skeletons=tuple(skeletons),
        key="".join(sorted(keys)),
        skeleton="".join(sorted(skeletons)),
    )


def phonetic_key(name: str) -> str:
    """Return only the phonetic key of a name."""
    return name_keys(name).key


def skeleton_key(name: str) -> str:
    """Return only the consonant skeleton of a name."""
    return name_keys(name).skeleton
