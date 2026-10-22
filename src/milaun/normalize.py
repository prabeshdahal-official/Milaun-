"""Text normalisation for names in Devanagari and Latin script."""

from __future__ import annotations

import unicodedata

from milaun.charset import DEVANAGARI_DIGITS, IGNORABLE

_DEVANAGARI_RANGE = (0x0900, 0x097F)


def strip_marks(text: str) -> str:
    """Remove zero-width and other phonetically empty marks."""
    return "".join(ch for ch in text if ch not in IGNORABLE)


def unify_digits(text: str) -> str:
    """Map Devanagari digits to ASCII so record ids compare consistently."""
    return "".join(DEVANAGARI_DIGITS.get(ch, ch) for ch in text)


def is_devanagari_char(ch: str) -> bool:
    return _DEVANAGARI_RANGE[0] <= ord(ch) <= _DEVANAGARI_RANGE[1]


def _is_name_char(ch: str) -> bool:
    """Keep ASCII alphanumerics and the whole Devanagari block.

    The Devanagari block must be kept wholesale: matras, the virama and the
    anusvara are combining marks (Unicode category Mn), so a ``\\w`` based
    filter would silently delete them and corrupt every name.
    """
    if ch == "_":
        return False
    if ch.isascii():
        return ch.isalnum()
    return is_devanagari_char(ch) and not ch.isspace()


def normalize_text(text: str) -> str:
    """Normalise a name for comparison.

    Steps: NFC, drop invisible marks, ASCII digits, replace punctuation with
    spaces, lowercase Latin, collapse whitespace. Devanagari is left intact
    (it is a case-less script, so lowercasing has no effect on it).
    """
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)
    text = unicodedata.normalize("NFC", text)
    text = strip_marks(text)
    text = unify_digits(text)
    cleaned = "".join(ch if _is_name_char(ch) else " " for ch in text)
    cleaned = cleaned.lower()
    return " ".join(cleaned.split())


def script_of(token: str) -> str:
    """Return ``devanagari``, ``latin``, ``mixed`` or ``unknown`` for a token."""
    dev = sum(1 for ch in token if is_devanagari_char(ch) and ch.isalpha())
    lat = sum(1 for ch in token if ch.isascii() and ch.isalpha())
    if dev and lat:
        return "mixed"
    if dev:
        return "devanagari"
    if lat:
        return "latin"
    return "unknown"


def dominant_script(text: str) -> str:
    """Return the dominant script of a whole string."""
    dev = sum(1 for ch in text if is_devanagari_char(ch) and ch.isalpha())
    lat = sum(1 for ch in text if ch.isascii() and ch.isalpha())
    if dev and lat:
        return "mixed"
    if dev:
        return "devanagari"
    if lat:
        return "latin"
    return "unknown"


def tokenize(text: str) -> list[str]:
    """Split a normalised name into non-empty tokens."""
    return [tok for tok in normalize_text(text).split(" ") if tok]


def has_devanagari(text: str) -> bool:
    return any(is_devanagari_char(ch) for ch in text)
