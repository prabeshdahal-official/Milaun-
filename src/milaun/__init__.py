"""Milaun - offline record linkage for Nepali names.

Milaun (मिलाउनु, "to match") compares personal names written in Devanagari and
in Latin script and returns a calibrated probability that two records describe
the same person. It is designed for offline use on modest hardware: the core
package has no third-party dependencies and makes no network calls.
"""

from milaun.matcher import Matcher, MatchResult
from milaun.phonetic import NameKeys, name_keys, phonetic_key, skeleton_key

__all__ = [
    "Matcher",
    "MatchResult",
    "NameKeys",
    "name_keys",
    "phonetic_key",
    "skeleton_key",
    "__version__",
]

__version__ = "0.1.0"
