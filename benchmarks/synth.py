"""Synthetic Nepali name-variant benchmark.

WHY SYNTHETIC
-------------
There is no public, licensed corpus of labelled Nepali name variants, and
scraping patient or beneficiary records is not acceptable. This module therefore
builds a reproducible benchmark from a hand-written seed list of common names
plus a documented set of *orthographic ambiguity operations* that mirror how
Nepali names actually get rewritten: dropped aspiration, retroflex/dental
confusion, vowel-length variation, schwa insertion, romanisation choices and
one-edit typos.

WHAT THIS CAN AND CANNOT SHOW
-----------------------------
It measures robustness to the transformations encoded here. It does not
estimate field accuracy on real registries, because real error distributions
are richer and correlated. Family ``dev`` operations are used for training;
family ``hard`` operations are held out entirely to test generalisation to
transformations the model never saw.

Every pair is generated deterministically from ``seed`` and the seed list, so
results are reproducible without committing large data files.
"""

from __future__ import annotations

import csv
import hashlib
import random
from dataclasses import dataclass, field
from pathlib import Path

from milaun.normalize import has_devanagari

DATA_DIR = Path(__file__).resolve().parent / "data"
SEED_FILE = DATA_DIR / "seed_names.csv"
DEFAULT_SEED = 20261022


@dataclass(frozen=True)
class Identity:
    id: str
    given_ne: str
    family_ne: str
    given_lat: str
    family_lat: str

    @property
    def name_ne(self) -> str:
        return f"{self.given_ne} {self.family_ne}"

    @property
    def name_lat(self) -> str:
        return f"{self.given_lat} {self.family_lat}"

    @property
    def tokens_ne(self) -> list[str]:
        return self.name_ne.split()

    @property
    def tokens_lat(self) -> list[str]:
        return self.name_lat.split()


def load_identities(path: Path | None = None) -> list[Identity]:
    """Read the seed name list."""
    source = path or SEED_FILE
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return [
            Identity(
                id=row["id"],
                given_ne=row["given_ne"].strip(),
                family_ne=row["family_ne"].strip(),
                given_lat=row["given_lat"].strip(),
                family_lat=row["family_lat"].strip(),
            )
            for row in reader
        ]


# --------------------------------------------------------------------------
# Orthographic operations. Each returns (new_text, label) and must be a no-op
# returning (text, "") when there is nothing to change.
# --------------------------------------------------------------------------

_NE_ASPIRATION = [
    ("क", "ख"), ("ग", "घ"), ("ज", "झ"), ("ट", "ठ"), ("ड", "ढ"),
    ("त", "थ"), ("द", "ध"), ("प", "फ"), ("ब", "भ"), ("च", "छ"),
]
_NE_RETROFLEX = [("ट", "त"), ("ठ", "थ"), ("ड", "द"), ("ढ", "ध"), ("ण", "न")]
_NE_VOWEL_LENGTH = [("ि", "ी"), ("ु", "ू"), ("े", "ै"), ("ो", "ौ")]
_NE_NASAL = [("ं", "ँ")]
_NE_NUKTA = [("ज", "ज़"), ("ड", "ड़"), ("फ", "फ़")]
_NE_SIBILANT = [("श", "ष"), ("ष", "स")]

_NE_CONSONANTS = set("कखगघङचछजझञटठडढणतथदधनपफबभमयरलवशषसह")
_NE_FINAL_MATRAS = set("ा ि ी ु ू ृ े ै ो ौ".split())


def _substitute(text: str, pairs: list[tuple[str, str]], rng: random.Random) -> str:
    """Replace one occurrence of one side of a confusion pair."""
    for char, other in pairs:
        if char in text and rng.random() < 0.5:
            return text.replace(char, other, 1)
    for char, other in pairs:
        if other in text:
            return text.replace(other, char, 1)
    return text


def op_aspiration_ne(text: str, rng: random.Random) -> tuple[str, str]:
    new = _substitute(text, _NE_ASPIRATION, rng)
    return (new, "aspiration_ne") if new != text else (text, "")


def op_retroflex_ne(text: str, rng: random.Random) -> tuple[str, str]:
    new = _substitute(text, _NE_RETROFLEX, rng)
    return (new, "retroflex_ne") if new != text else (text, "")


def op_vowel_length_ne(text: str, rng: random.Random) -> tuple[str, str]:
    new = _substitute(text, _NE_VOWEL_LENGTH, rng)
    return (new, "vowel_length_ne") if new != text else (text, "")


def op_nasal_ne(text: str, rng: random.Random) -> tuple[str, str]:
    new = _substitute(text, _NE_NASAL, rng)
    if new == text and "ं" not in text:
        # Insert an anusvara before the final consonant: कुवर -> कुंवर.
        for index in range(len(text) - 1, 0, -1):
            if text[index] in _NE_CONSONANTS:
                new = text[:index] + "ं" + text[index:]
                return new, "nasal_ne"
    return (new, "nasal_ne") if new != text else (text, "")


def op_schwa_final_ne(text: str, rng: random.Random) -> tuple[str, str]:
    """Add a final ा, the Devanagari side of Ramesh/Ramesha variation."""
    if not text or text[-1] in _NE_FINAL_MATRAS or text[-1] == "्":
        return text, ""
    return text + "ा", "schwa_final_ne"


def op_halant_ne(text: str, rng: random.Random) -> tuple[str, str]:
    """Drop a virama, turning a cluster into an extra syllable."""
    if "्" not in text:
        return text, ""
    index = text.rfind("्")
    return text[:index] + text[index + 1:], "halant_ne"


def op_nukta_ne(text: str, rng: random.Random) -> tuple[str, str]:
    new = _substitute(text, _NE_NUKTA, rng)
    return (new, "nukta_ne") if new != text else (text, "")


def op_sibilant_ne(text: str, rng: random.Random) -> tuple[str, str]:
    new = _substitute(text, _NE_SIBILANT, rng)
    return (new, "sibilant_ne") if new != text else (text, "")


def op_typo_ne(text: str, rng: random.Random) -> tuple[str, str]:
    if len(text) < 4:
        return text, ""
    index = rng.randrange(len(text))
    return text[:index] + text[index + 1:], "typo_ne"


def _add_h(text: str, rng: random.Random) -> str:
    letters = "ktpbdgj"
    positions = [i for i, ch in enumerate(text) if ch in letters and
                 (i + 1 >= len(text) or text[i + 1] != "h")]
    if not positions:
        return text
    index = rng.choice(positions)
    return text[: index + 1] + "h" + text[index + 1:]


def _drop_h(text: str, rng: random.Random) -> str:
    positions = [i for i, ch in enumerate(text) if ch == "h" and i > 0
                 and text[i - 1] in "ktpbdgjc"]
    if not positions:
        return text
    index = rng.choice(positions)
    return text[:index] + text[index + 1:]


def op_aspiration_lat(text: str, rng: random.Random) -> tuple[str, str]:
    new = _add_h(text, rng) if rng.random() < 0.5 else _drop_h(text, rng)
    return (new, "aspiration_lat") if new != text else (text, "")


_LAT_VOWEL_DIGRAPHS = [("i", "ee"), ("u", "oo"), ("o", "ou")]


def op_vowel_digraph_lat(text: str, rng: random.Random) -> tuple[str, str]:
    for short, long in _LAT_VOWEL_DIGRAPHS:
        if short in text:
            index = text.find(short)
            if rng.random() < 0.5:
                new = text[:index] + long + text[index + 1:]
                return new, "vowel_digraph_lat"
    for short, long in _LAT_VOWEL_DIGRAPHS:
        if long in text:
            return text.replace(long, short, 1), "vowel_digraph_lat"
    return text, ""


def op_wbv_lat(text: str, rng: random.Random) -> tuple[str, str]:
    return _substitute(text, [("b", "v"), ("v", "b"), ("w", "v")], rng), "wbv_lat"


def op_sh_s_lat(text: str, rng: random.Random) -> tuple[str, str]:
    if "sh" in text:
        return text.replace("sh", "s", 1), "sh_s_lat"
    return text, ""


def op_double_lat(text: str, rng: random.Random) -> tuple[str, str]:
    candidates = [i for i, ch in enumerate(text) if ch in "nmltsr" and i < len(text) - 2
                  and text[i + 1] not in "h"]
    if not candidates:
        return text, ""
    index = rng.choice(candidates)
    return text[: index + 1] + text[index] + text[index + 1:], "double_lat"


def op_schwa_final_lat(text: str, rng: random.Random) -> tuple[str, str]:
    if not text or text[-1] in "aeiou":
        return text, ""
    return text + "a", "schwa_final_lat"


def op_final_y_lat(text: str, rng: random.Random) -> tuple[str, str]:
    if text.endswith("y"):
        return text[:-1] + "i", "final_y_lat"
    if text.endswith("i"):
        return text[:-1] + "y", "final_y_lat"
    return text, ""


def op_typo_lat(text: str, rng: random.Random) -> tuple[str, str]:
    if len(text) < 4:
        return text, ""
    index = rng.randrange(len(text))
    choice = rng.random()
    if choice < 0.4:
        return text[:index] + text[index + 1:], "typo_lat"
    if choice < 0.7:
        return text[:index] + rng.choice("aeiou") + text[index + 1:], "typo_lat"
    return text[:index] + rng.choice("abcdefghijklmnoprstuvy") + text[index:], "typo_lat"


def op_nukta_lat(text: str, rng: random.Random) -> tuple[str, str]:
    return _substitute(text, [("j", "z"), ("z", "j")], rng), "nukta_lat"


# Structural operations apply to both scripts.
def op_swap_tokens(text: str, rng: random.Random) -> tuple[str, str]:
    tokens = text.split()
    if len(tokens) < 2:
        return text, ""
    tokens[0], tokens[-1] = tokens[-1], tokens[0]
    return " ".join(tokens), "swap_tokens"


def op_drop_middle(text: str, rng: random.Random) -> tuple[str, str]:
    tokens = text.split()
    if len(tokens) < 3:
        return text, ""
    return " ".join(tokens[:1] + tokens[2:]), "drop_middle"


def op_initial_middle(text: str, rng: random.Random) -> tuple[str, str]:
    tokens = text.split()
    if len(tokens) < 3:
        return text, ""
    middle = tokens[1]
    tokens[1] = middle[0] + "."
    return " ".join(tokens), "initial_middle"


DEV_NE_OPS = [op_aspiration_ne, op_retroflex_ne, op_vowel_length_ne, op_nasal_ne,
              op_schwa_final_ne]
DEV_LAT_OPS = [op_aspiration_lat, op_vowel_digraph_lat, op_wbv_lat, op_sh_s_lat,
               op_double_lat, op_schwa_final_lat, op_final_y_lat]
HARD_NE_OPS = [op_nukta_ne, op_halant_ne, op_sibilant_ne, op_typo_ne]
HARD_LAT_OPS = [op_typo_lat, op_nukta_lat]
STRUCTURAL_OPS = [op_swap_tokens, op_drop_middle, op_initial_middle]

# Minimal pairs: a different person whose given name differs by one sound.
# These are the dangerous false positives in a real registry ("Prabesh" vs
# "Prabin" with the same surname), so they are generated explicitly instead of
# hoping random sampling produces them.
# A single vowel change ("Prabesh"/"Pribesh") is far more likely to be a typo
# of the same person than a different person, so different-person negatives are
# built from *consonant* changes only. Labelling vowel edits as different people
# would punish the model for being right.
# Substitutions must cross a phonetic class. Swapping b/p or d/t would produce
# a *different spelling of the same sound*, which the encoder merges by design;
# labelling that as a different person would inject contradictory examples.
_CONFUSABLE_LATIN = [("n", "m"), ("r", "l"), ("s", "n"), ("t", "k"),
                     ("d", "g"), ("p", "m"), ("b", "g"), ("j", "d")]

_NE_CROSS_CLASS = [("\u0915", "\u091f"), ("\u0924", "\u092a"), ("\u0926", "\u0917"),
                   ("\u0928", "\u092e"), ("\u0930", "\u0932"), ("\u0938", "\u0928"),
                   ("\u092c", "\u0926"), ("\u091c", "\u0917")]


def _latin_substitute(word: str, rng: random.Random) -> tuple[str, str]:
    for _ in range(12):
        index = rng.randrange(len(word))
        char = word[index]
        for left, right in _CONFUSABLE_LATIN:
            if char == left:
                return word[:index] + right + word[index + 1:], "near_miss"
            if char == right:
                return word[:index] + left + word[index + 1:], "near_miss"
    return word, ""


def op_near_miss(name: str, rng: random.Random) -> tuple[str, str]:
    """Change only the given name by one confusable sound."""
    tokens = name.split()
    if len(tokens) < 2:
        return name, ""
    given = tokens[0]
    if has_devanagari(given):
        changed, label = given, ""
        for left, right in _NE_CROSS_CLASS:
            if left in given:
                changed, label = given.replace(left, right, 1), "near_miss"
                break
            if right in given:
                changed, label = given.replace(right, left, 1), "near_miss"
                break
    else:
        changed, label = _latin_substitute(given, rng)
    if not label:
        return name, ""
    return " ".join([changed] + tokens[1:]), "near_miss"




def mutate(
    name: str, family: str = "dev", rng: random.Random | None = None
) -> tuple[str, list[str]]:
    """Apply one or two ambiguity operations to a name."""
    rng = rng or random.Random(DEFAULT_SEED)
    devanagari = has_devanagari(name)
    if family == "dev":
        pool = DEV_NE_OPS if devanagari else DEV_LAT_OPS
    else:
        pool = HARD_NE_OPS if devanagari else HARD_LAT_OPS
    pool = list(pool) + STRUCTURAL_OPS

    applied: list[str] = []
    rounds = rng.choice([1, 1, 1, 2])
    for _ in range(rounds):
        for _attempt in range(8):
            op = rng.choice(pool)
            new_name, label = op(name, rng)
            if label:
                name = new_name
                applied.append(label)
                break
    return name, applied


@dataclass
class Pair:
    left_id: str
    right_id: str
    left_name: str
    right_name: str
    label: int
    split: str
    identity_left: str
    identity_right: str
    ops: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "left_id": self.left_id,
            "right_id": self.right_id,
            "left_name": self.left_name,
            "right_name": self.right_name,
            "label": self.label,
            "split": self.split,
            "identity_left": self.identity_left,
            "identity_right": self.identity_right,
            "ops": "|".join(self.ops),
        }


def _split_for(identity_id: str, family: str) -> str:
    """Assign a whole identity to one split so no person leaks across splits."""
    if family == "hard":
        return "hard_test"
    bucket = hashlib.md5(identity_id.encode("utf-8")).digest()[0] % 100
    if bucket < 60:
        return "train"
    if bucket < 80:
        return "calib"
    return "test"


def build_pairs(
    identities: list[Identity],
    family: str = "dev",
    positives_per_identity: int = 6,
    negatives_per_identity: int = 8,
    seed: int = DEFAULT_SEED,
) -> list[Pair]:
    """Generate labelled pairs for one operation family."""
    rng = random.Random(seed)
    pairs: list[Pair] = []

    for identity in identities:
        for variant_index in range(positives_per_identity):
            mode = rng.choice(["ne", "lat", "cross", "cross", "exact"])
            ops: list[str] = []
            if mode == "exact":
                left_name, right_name = identity.name_lat, identity.name_lat
            elif mode == "ne":
                left_name = identity.name_ne
                right_name, ops = mutate(identity.name_ne, family, rng)
            elif mode == "lat":
                left_name = identity.name_lat
                right_name, ops = mutate(identity.name_lat, family, rng)
            else:
                left_name = identity.name_ne
                right_name, ops = mutate(identity.name_lat, family, rng)
            pairs.append(
                Pair(
                    left_id=f"{identity.id}-a{variant_index}",
                    right_id=f"{identity.id}-b{variant_index}",
                    left_name=left_name,
                    right_name=right_name,
                    label=1,
                    split=_split_for(identity.id, family),
                    identity_left=identity.id,
                    identity_right=identity.id,
                    ops=ops,
                )
            )

    by_family: dict[str, list[Identity]] = {}
    by_given: dict[str, list[Identity]] = {}
    for identity in identities:
        by_family.setdefault(identity.family_lat, []).append(identity)
        by_given.setdefault(identity.given_lat, []).append(identity)

    shared_family = [group for group in by_family.values() if len(group) > 1]
    shared_given = [group for group in by_given.values() if len(group) > 1]

    for identity in identities:
        for negative_index in range(negatives_per_identity):
            roll = rng.random()
            if roll < 0.45 and shared_family:
                group = rng.choice(shared_family)
                other = rng.choice([item for item in group if item.id != identity.id])
            elif roll < 0.7 and shared_given:
                group = rng.choice(shared_given)
                other = rng.choice([item for item in group if item.id != identity.id])
            else:
                other = rng.choice([item for item in identities if item.id != identity.id])

            # Match the script mix of the positive pairs. Otherwise a model can
            # learn "one side is Devanagari" as a shortcut, which would not hold
            # on a real single-script registry.
            mode = rng.choice(["ne", "lat", "cross", "cross", "lat"])
            if mode == "ne":
                left_name, right_name = identity.name_ne, other.name_ne
            elif mode == "lat":
                left_name, right_name = identity.name_lat, other.name_lat
            else:
                left_name, right_name = identity.name_ne, other.name_lat
            if rng.random() < 0.35:
                left_name, _ = mutate(left_name, family, rng)
            if rng.random() < 0.35:
                right_name, _ = mutate(right_name, family, rng)

            pairs.append(
                Pair(
                    left_id=f"{identity.id}-na{negative_index}",
                    right_id=f"{other.id}-nb{negative_index}",
                    left_name=left_name,
                    right_name=right_name,
                    label=0,
                    split=_split_for(identity.id, family),
                    identity_left=identity.id,
                    identity_right=other.id,
                )
            )
    # Two negatives per identity that keep the given name and swap the family
    # name. Without these, "first token matches" looks like proof of identity,
    # which is exactly the mistake that joins Sita Sharma to Sita Karki.
    for identity in identities:
        for variant_index in range(2):
            candidates = [
                item
                for item in identities
                if item.id != identity.id and item.family_lat != identity.family_lat
            ]
            if not candidates:
                continue
            other = rng.choice(candidates)
            if rng.random() < 0.5:
                left_name = identity.name_ne
                right_name = f"{identity.given_ne} {other.family_ne}"
            else:
                left_name = identity.name_lat
                right_name = f"{identity.given_lat} {other.family_lat}"
            if left_name == right_name:
                continue
            pairs.append(
                Pair(
                    left_id=f"{identity.id}-ga{variant_index}",
                    right_id=f"{identity.id}-gb{variant_index}",
                    left_name=left_name,
                    right_name=right_name,
                    label=0,
                    split=_split_for(identity.id, family),
                    identity_left=identity.id,
                    identity_right=f"{other.id}-surnameonly",
                )
            )

    # Two minimal pairs per identity: same surname, one-sound difference in the
    # given name, different person.
    for identity in identities:
        for variant_index in range(2):
            base = identity.name_lat if rng.random() < 0.5 else identity.name_ne
            variant, ops = op_near_miss(base, rng)
            if variant.split() == base.split():
                continue
            pairs.append(
                Pair(
                    left_id=f"{identity.id}-ma{variant_index}",
                    right_id=f"{identity.id}-mb{variant_index}",
                    left_name=base,
                    right_name=variant,
                    label=0,
                    split=_split_for(identity.id, family),
                    identity_left=identity.id,
                    identity_right=f"{identity.id}-twin",
                    ops=ops,
                )
            )

    return pairs


def build_registry(
    identities: list[Identity], copies: int = 3, seed: int = DEFAULT_SEED
) -> list[dict]:
    """Build a small registry with known duplicates, for cluster-level scoring."""
    rng = random.Random(seed + 7)
    records: list[dict] = []
    for identity in identities:
        records.append({"id": f"{identity.id}-r0", "name": identity.name_lat,
                        "true_identity": identity.id})
        for copy_index in range(1, copies):
            if copy_index % 2 == 0:
                name, _ = mutate(identity.name_ne, "dev", rng)
            else:
                name, _ = mutate(identity.name_lat, "dev", rng)
            records.append({"id": f"{identity.id}-r{copy_index}", "name": name,
                            "true_identity": identity.id})
    rng.shuffle(records)
    return records


def write_pairs(path: Path, pairs: list[Pair]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(pairs[0].as_dict().keys()) if pairs else []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for pair in pairs:
            writer.writerow(pair.as_dict())


if __name__ == "__main__":  # pragma: no cover - manual inspection helper
    identities = load_identities()
    for family in ("dev", "hard"):
        pairs = build_pairs(identities, family=family)
        print(f"{family}: {len(pairs)} pairs, "
              f"{sum(pair.label for pair in pairs)} positives")
        for pair in pairs[:3]:
            print(" ", pair.as_dict())
