"""Unicode tables for Devanagari and the canonical phonetic alphabet.

The canonical alphabet is deliberately small. Each symbol is a *class* of
sounds that Nepali typists and clerks routinely confuse when writing names in
Latin script, so the mapping is lossy on purpose:

    K  velar stop (क, ख)              merge aspiration
    G  voiced velar (ग, घ)            merge aspiration
    C  palatal affricate (च, छ)
    J  palatal affricate (ज, झ, ज़)
    T  coronal stop (ट, ठ, त, थ)      merge retroflex/dental + aspiration
    D  voiced coronal (ड, ढ, द, ध)    merge retroflex/dental + aspiration
    N  nasal (ङ, ञ, ण, न, ं, ँ)
    P  labial stop (प, फ, फ़)
    B  labial (ब, भ, व, w, v)         Nepali व is realised [w]/[b]
    M  labial nasal (म)
    Y  approximant (य)
    R  rhotic (र, ड़, ढ़)
    L  lateral (ल)
    S  sibilant (श, ष, स)
    H  glottal (ह)
    A I U E O  vowel classes (length neutral; e/ai and o/au merged)

The consonant skeleton drops vowels entirely and is used as a second, more
permissive comparison key. It absorbs epenthetic schwa in clusters, which is
the single largest source of Devanagari/Latin mismatch in Nepali names
(प्रवेश -> "Pravesh", not "Prvesh").
"""

from __future__ import annotations

# Devanagari consonants -> canonical symbol.
CONSONANTS: dict[str, str] = {
    "\u0915": "K",  # क
    "\u0916": "K",  # ख
    "\u0917": "G",  # ग
    "\u0918": "G",  # घ
    "\u0919": "N",  # ङ
    "\u091a": "C",  # च
    "\u091b": "C",  # छ
    "\u091c": "J",  # ज
    "\u091d": "J",  # झ
    "\u091e": "N",  # ञ
    "\u091f": "T",  # ट
    "\u0920": "T",  # ठ
    "\u0921": "D",  # ड
    "\u0922": "D",  # ढ
    "\u0923": "N",  # ण
    "\u0924": "T",  # त
    "\u0925": "T",  # थ
    "\u0926": "D",  # द
    "\u0927": "D",  # ध
    "\u0928": "N",  # न
    "\u092a": "P",  # प
    "\u092b": "P",  # फ
    "\u092c": "B",  # ब
    "\u092d": "B",  # भ
    "\u092e": "M",  # म
    "\u092f": "Y",  # य
    "\u0930": "R",  # र
    "\u0932": "L",  # ल
    "\u0935": "B",  # व
    "\u0936": "S",  # श
    "\u0937": "S",  # ष
    "\u0938": "S",  # स
    "\u0939": "H",  # ह
}

# Independent vowels.
INDEPENDENT_VOWELS: dict[str, str] = {
    "\u0905": "A",  # अ
    "\u0906": "A",  # आ
    "\u0907": "I",  # इ
    "\u0908": "I",  # ई
    "\u0909": "U",  # उ
    "\u090a": "U",  # ऊ
    "\u090b": "RI",  # ऋ
    "\u090f": "E",  # ए
    "\u0910": "E",  # ऐ
    "\u0913": "O",  # ओ
    "\u0914": "O",  # औ
}

# Dependent vowel signs (matras).
MATRAS: dict[str, str] = {
    "\u093e": "A",  # ा
    "\u093f": "I",  # ि
    "\u0940": "I",  # ी
    "\u0941": "U",  # ु
    "\u0942": "U",  # ू
    "\u0943": "RI",  # ृ
    "\u0947": "E",  # े
    "\u0948": "E",  # ै
    "\u094b": "O",  # ो
    "\u094c": "O",  # ौ
}

VIRAMA = "\u094d"  # ्
NUKTA = "\u093c"  # ़
ANUSVARA = "\u0902"  # ं
CHANDRABINDU = "\u0901"  # ँ
VISARGA = "\u0903"  # ः

NASAL_MARKS = frozenset({ANUSVARA, CHANDRABINDU})
NASAL_SYMBOL = "N"

# Marks that carry no phonetic weight but appear in real names.
IGNORABLE = frozenset(
    {
        "\u200b",  # zero width space
        "\u200c",  # ZWNJ
        "\u200d",  # ZWJ
        "\ufeff",  # BOM
        "\u00ad",  # soft hyphen
        "\u093d",  # avagraha ऽ
        "\u0951",  # stress marks
        "\u0952",
        "\u0900",
    }
)

DEVANAGARI_DIGITS = {chr(0x0966 + i): str(i) for i in range(10)}

# Latin digraphs, applied longest-first by the transcriber.
LATIN_DIGRAPHS: tuple[tuple[str, str], ...] = (
    ("chh", "C"),
    ("ksh", "KS"),
    ("gy", "GY"),
    ("ch", "C"),
    ("kh", "K"),
    ("gh", "G"),
    ("jh", "J"),
    ("th", "T"),
    ("dh", "D"),
    ("ph", "P"),
    ("bh", "B"),
    ("sh", "S"),
    ("zh", "J"),
    ("ss", "S"),
    ("ee", "I"),
    ("ea", "I"),
    ("oo", "U"),
    ("ou", "O"),
    ("au", "O"),
    ("aw", "O"),
    ("ai", "E"),
    ("ay", "E"),
    ("ey", "E"),
    ("eu", "O"),
    ("oi", "O"),
    ("ng", "N"),
)

LATIN_SINGLES: dict[str, str] = {
    "a": "A",
    "b": "B",
    "c": "K",
    "d": "D",
    "e": "E",
    "f": "P",
    "g": "G",
    "h": "H",
    "i": "I",
    "j": "J",
    "k": "K",
    "l": "L",
    "m": "M",
    "n": "N",
    "o": "O",
    "p": "P",
    "q": "K",
    "r": "R",
    "s": "S",
    "t": "T",
    "u": "U",
    "v": "B",
    "w": "B",
    "x": "KS",
    "y": "Y",
    "z": "J",
}

# Latin display order for a canonical key (used by the explanation UI only).
SYMBOL_NAMES: dict[str, str] = {
    "K": "k/kh",
    "G": "g/gh",
    "C": "ch",
    "J": "j/jh/z",
    "T": "t/th/tt",
    "D": "d/dh/dd",
    "N": "n/ng/nn",
    "P": "p/ph/f",
    "B": "b/bh/v/w",
    "M": "m",
    "Y": "y",
    "R": "r/rh",
    "L": "l",
    "S": "s/sh",
    "H": "h",
    "A": "a",
    "I": "i/ee",
    "U": "u/oo",
    "E": "e/ai",
    "O": "o/au",
}
