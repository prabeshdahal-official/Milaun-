"""Devanagari -> canonical phonetic stream, and a readable Latin rendering.

Both projections are produced by one state machine (:func:`_walk`) that emits
script-agnostic events. The machine tracks a single piece of context: whether a
consonant is still waiting for its inherent vowel. A virama suppresses that
vowel, a matra replaces it, and any other character flushes it as ``A``.
"""

from __future__ import annotations

from milaun.charset import (
    CONSONANTS,
    INDEPENDENT_VOWELS,
    MATRAS,
    NASAL_MARKS,
    NUKTA,
    VIRAMA,
    VISARGA,
)
from milaun.normalize import normalize_text

_LATIN_CONSONANTS: dict[str, str] = {
    "\u0915": "k",
    "\u0916": "kh",
    "\u0917": "g",
    "\u0918": "gh",
    "\u0919": "ng",
    "\u091a": "ch",
    "\u091b": "chh",
    "\u091c": "j",
    "\u091d": "jh",
    "\u091e": "n",
    "\u091f": "t",
    "\u0920": "th",
    "\u0921": "d",
    "\u0922": "dh",
    "\u0923": "n",
    "\u0924": "t",
    "\u0925": "th",
    "\u0926": "d",
    "\u0927": "dh",
    "\u0928": "n",
    "\u092a": "p",
    "\u092b": "ph",
    "\u092c": "b",
    "\u092d": "bh",
    "\u092e": "m",
    "\u092f": "y",
    "\u0930": "r",
    "\u0932": "l",
    "\u0935": "v",
    "\u0936": "sh",
    "\u0937": "sh",
    "\u0938": "s",
    "\u0939": "h",
}

_LATIN_MATRAS: dict[str, str] = {
    "\u093e": "a",
    "\u093f": "i",
    "\u0940": "i",
    "\u0941": "u",
    "\u0942": "u",
    "\u0943": "ri",
    "\u0947": "e",
    "\u0948": "ai",
    "\u094b": "o",
    "\u094c": "au",
}

_LATIN_INDEPENDENT: dict[str, str] = {
    "\u0905": "a",
    "\u0906": "a",
    "\u0907": "i",
    "\u0908": "i",
    "\u0909": "u",
    "\u090a": "u",
    "\u090b": "ri",
    "\u090f": "e",
    "\u0910": "ai",
    "\u0913": "o",
    "\u0914": "au",
}

# Devanagari bases that become a retroflex flap when a nukta follows.
_FLAP_BASES = frozenset({"\u0921", "\u0922"})
_FLAP_REPLACEMENT = "\u0930"  # map ड़/ढ़ onto र so both projections yield R/r

# A nasal followed by virama + य is palatalised (न्य -> "n"), so the य is
# dropped. Restricting this to nasals matters: dropping every post-virama य
# would also erase the /j/ in र्य ("Acharya") and over-merge distinct names.
_NASAL_BASES = frozenset({"\u0919", "\u091e", "\u0923", "\u0928", "\u092e"})


def _walk(text: str) -> list[tuple[str, str]]:
    """Return the event stream for normalised Devanagari text.

    Event kinds: ``cons`` (payload: consonant char), ``vowel`` (payload: matra
    or independent-vowel char, or ``""`` for the inherent vowel), ``nasal``,
    ``visarga``, ``space``.
    """
    events: list[tuple[str, str]] = []
    pending = False
    previous_char = ""
    previous_was_virama = False
    last_consonant = ""

    for ch in text:
        if ch == NUKTA:
            if previous_char in _FLAP_BASES and events and events[-1][0] == "cons":
                events[-1] = ("cons", _FLAP_REPLACEMENT)
                last_consonant = _FLAP_REPLACEMENT
            continue

        if ch in CONSONANTS:
            if pending:
                events.append(("vowel", ""))
                pending = False
            if ch == "\u092f" and previous_was_virama and last_consonant in _NASAL_BASES:
                # Palatalised nasal: drop the glide but keep its vowel slot.
                pending = True
                previous_was_virama = False
                previous_char = ch
                continue
            events.append(("cons", ch))
            last_consonant = ch
            pending = True
            previous_was_virama = False
            previous_char = ch
            continue

        if ch == VIRAMA:
            pending = False
            previous_was_virama = True
            previous_char = ch
            continue

        if ch in MATRAS:
            pending = False
            events.append(("vowel", ch))
            previous_was_virama = False
            previous_char = ch
            continue

        if ch in INDEPENDENT_VOWELS:
            if pending:
                events.append(("vowel", ""))
                pending = False
            events.append(("vowel", ch))
            previous_was_virama = False
            previous_char = ch
            continue

        if ch in NASAL_MARKS:
            if pending:
                events.append(("vowel", ""))
                pending = False
            events.append(("nasal", ""))
            previous_was_virama = False
            previous_char = ch
            continue

        if ch == VISARGA:
            if pending:
                events.append(("vowel", ""))
                pending = False
            events.append(("visarga", ""))
            previous_was_virama = False
            previous_char = ch
            continue

        if pending:
            events.append(("vowel", ""))
            pending = False
        if not events or events[-1][0] != "space":
            events.append(("space", ""))
        previous_was_virama = False
        previous_char = ch

    if pending:
        events.append(("vowel", ""))
    return events


def to_phonetic_stream(text: str) -> str:
    """Project Devanagari text onto canonical phonetic symbols."""
    text = normalize_text(text)
    parts: list[str] = []
    for kind, payload in _walk(text):
        if kind == "space":
            parts.append(" ")
        elif kind == "cons":
            parts.append(CONSONANTS[payload])
        elif kind == "vowel":
            if not payload:
                parts.append("A")
            else:
                parts.append(MATRAS.get(payload) or INDEPENDENT_VOWELS[payload])
        elif kind == "nasal":
            parts.append("N")
        else:  # visarga
            parts.append("H")
    return "".join(parts).strip()


def to_latin(text: str) -> str:
    """Readable transliteration, e.g. ``प्रवेश दाहाल`` -> ``pravesh dahal``."""
    text = normalize_text(text)
    words: list[str] = []
    current: list[str] = []

    def flush_word() -> None:
        if not current:
            return
        # Nepali deletes word-final schwa, and romanisations follow the
        # pronunciation ("Lama", not "Lamaa"), so mirror that here.
        if len(current) > 2 and current[-1] == "a":
            current.pop()
        words.append("".join(current))
        current.clear()

    for kind, payload in _walk(text):
        if kind == "space":
            flush_word()
        elif kind == "cons":
            current.append(_LATIN_CONSONANTS[payload])
        elif kind == "vowel":
            if not payload:
                current.append("a")
            else:
                current.append(_LATIN_MATRAS.get(payload) or _LATIN_INDEPENDENT[payload])
        elif kind == "nasal":
            current.append("n")
        else:  # visarga
            current.append("h")
    flush_word()
    return " ".join(words)
