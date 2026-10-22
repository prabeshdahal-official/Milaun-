"""String similarity primitives and pair feature extraction.

Everything here is pure Python and deterministic. Names are short, so the
quadratic Levenshtein implementation is not a bottleneck; the benchmark in
``benchmarks/evaluate.py`` measures it rather than assuming it.

The feature set is deliberately small and continuous. Binary "keys are equal"
flags look attractive but fail on exactly the cases the encoder exists for: a
single-token name written ``सापकोटा`` and ``Sapkota`` has different keys and
identical meaning, so equality flags read 0 on a true match. Token-level
similarities carry the same information without that failure mode.
"""

from __future__ import annotations

from milaun.phonetic import NameKeys

FEATURES: tuple[str, ...] = (
    "key_sim",
    "skeleton_sim",
    "key_dice",
    "skeleton_dice",
    "token_min_sim",
    "first_token_sim",
    "last_token_sim",
    "latin_sim",
)


def levenshtein(a: str, b: str) -> int:
    """Edit distance with two rolling rows."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        current = [i]
        for j, cb in enumerate(b, start=1):
            cost = 0 if ca == cb else 1
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + cost))
        previous = current
    return previous[-1]


def ratio(a: str, b: str) -> float:
    """Normalised similarity in ``[0, 1]`` derived from edit distance."""
    if not a and not b:
        return 1.0
    longest = max(len(a), len(b))
    if longest == 0:
        return 1.0
    return 1.0 - levenshtein(a, b) / longest


def jaro(a: str, b: str) -> float:
    """Jaro similarity."""
    if a == b:
        return 1.0
    if not a or not b:
        return 0.0
    window = max(max(len(a), len(b)) // 2 - 1, 0)
    a_matched = [False] * len(a)
    b_matched = [False] * len(b)
    matches = 0
    for i, ca in enumerate(a):
        start = max(0, i - window)
        end = min(i + window + 1, len(b))
        for j in range(start, end):
            if not b_matched[j] and b[j] == ca:
                a_matched[i] = True
                b_matched[j] = True
                matches += 1
                break
    if matches == 0:
        return 0.0
    transpositions = 0
    k = 0
    for i, ca in enumerate(a):
        if not a_matched[i]:
            continue
        while not b_matched[k]:
            k += 1
        if ca != b[k]:
            transpositions += 1
        k += 1
    transpositions //= 2
    return (matches / len(a) + matches / len(b) + (matches - transpositions) / matches) / 3.0


def jaro_winkler(a: str, b: str, prefix_weight: float = 0.1, max_prefix: int = 4) -> float:
    """Jaro-Winkler similarity, which rewards a shared prefix."""
    base = jaro(a, b)
    if base <= 0.7:
        return base
    prefix = 0
    for ca, cb in zip(a, b, strict=False):
        if ca != cb or prefix == max_prefix:
            break
        prefix += 1
    return min(1.0, base + prefix * prefix_weight * (1.0 - base))


def dice(a: str, b: str) -> float:
    """Sørensen-Dice coefficient over character bigrams.

    Edit distance punishes a deleted character twice (one deletion shifts every
    following character), which is harsh on short phonetic keys. Bigram overlap
    is more forgiving of single-character noise and complements the edit ratio.
    """
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if len(a) < 2 or len(b) < 2:
        return ratio(a, b)
    bigrams_a = [a[i:i + 2] for i in range(len(a) - 1)]
    bigrams_b = [b[i:i + 2] for i in range(len(b) - 1)]
    pool = list(bigrams_b)
    shared = 0
    for gram in bigrams_a:
        if gram in pool:
            pool.remove(gram)
            shared += 1
    return 2 * shared / (len(bigrams_a) + len(bigrams_b))


def token_best_match(a_tokens: tuple[str, ...], b_tokens: tuple[str, ...]) -> float:
    """Order-invariant token similarity.

    Each token is matched to its best counterpart in the other name, then the
    two directional averages are averaged. This tolerates reordered names,
    dropped middle names and initials without inventing matches.
    """
    if not a_tokens or not b_tokens:
        return 0.0

    def directed(left: tuple[str, ...], right: tuple[str, ...]) -> float:
        total = 0.0
        for token in left:
            total += max(ratio(token, other) for other in right)
        return total / len(left)

    return (directed(a_tokens, b_tokens) + directed(b_tokens, a_tokens)) / 2.0


def _token_sim(
    a_key: str, a_skeleton: str, b_key: str, b_skeleton: str
) -> float:
    """Similarity of one token pair.

    Take the better of the vowel-sensitive and vowel-free comparisons. A token
    that differs only by an epenthetic schwa (सापकोटा / Sapkota) matches on its
    skeleton; a token that differs in a real consonant does not.
    """
    return max(ratio(a_key, b_key), ratio(a_skeleton, b_skeleton))


def _informative_pairs(
    keys: tuple[str, ...], skeletons: tuple[str, ...]
) -> list[tuple[str, str]]:
    """Drop single-symbol tokens (middle initials) when better tokens exist.

    "Ram B. Thapa" must not be penalised for the "B": an initial carries almost
    no evidence, and treating it as a full token drove a true match to zero in
    the error analysis. Keys and skeletons are filtered together so the two
    tuples stay aligned.
    """
    pairs = [
        (key, skeleton)
        for key, skeleton in zip(keys, skeletons, strict=True)
        if len(key) > 1
    ]
    if pairs:
        return pairs
    return list(zip(keys, skeletons, strict=True))


def token_min_sim(a: NameKeys, b: NameKeys) -> float:
    """Worst best-match among the tokens of the shorter name.

    This is what separates "Prabesh Dahal" from "Prabin Dahal": every token
    finds *some* counterpart, but one of them is a poor match. An average alone
    hides that; the minimum does not.
    """
    if not a.keys or not b.keys:
        return 0.0
    left = _informative_pairs(a.keys, a.skeletons)
    right = _informative_pairs(b.keys, b.skeletons)
    short, long = (left, right) if len(left) <= len(right) else (right, left)

    worst = 1.0
    for key, skeleton in short:
        best = max(
            _token_sim(key, skeleton, other_key, other_skeleton)
            for other_key, other_skeleton in long
        )
        worst = min(worst, best)
    return worst


def _key_pair_sim(a_sorted: str, a_ordered: str, b_sorted: str, b_ordered: str) -> float:
    """Best of order-invariant and in-order comparison.

    Sorting token keys makes "Dahal Prabesh" match "Prabesh Dahal". It also
    makes a single-token spelling ("Madhugiri") fail to match the same name
    written with a space ("Madhu Giri"), because the sorted key reorders the
    surname to the front. Comparing both concatenations fixes that case without
    giving up order invariance.
    """
    return max(ratio(a_sorted, b_sorted), ratio(a_ordered, b_ordered))


def pair_features(a: NameKeys, b: NameKeys) -> dict[str, float]:
    """Extract the model features for one pair of names."""
    ordered_key_a, ordered_key_b = "".join(a.keys), "".join(b.keys)
    ordered_skeleton_a, ordered_skeleton_b = "".join(a.skeletons), "".join(b.skeletons)

    first = (
        _token_sim(a.keys[0], a.skeletons[0], b.keys[0], b.skeletons[0])
        if a.keys and b.keys
        else 0.0
    )
    last = (
        _token_sim(a.keys[-1], a.skeletons[-1], b.keys[-1], b.skeletons[-1])
        if a.keys and b.keys
        else 0.0
    )
    return {
        "key_sim": _key_pair_sim(a.key, ordered_key_a, b.key, ordered_key_b),
        "skeleton_sim": _key_pair_sim(
            a.skeleton, ordered_skeleton_a, b.skeleton, ordered_skeleton_b
        ),
        "key_dice": max(dice(a.key, b.key), dice(ordered_key_a, ordered_key_b)),
        "skeleton_dice": max(
            dice(a.skeleton, b.skeleton),
            dice(ordered_skeleton_a, ordered_skeleton_b),
        ),
        "token_min_sim": token_min_sim(a, b),
        "first_token_sim": first,
        "last_token_sim": last,
        "latin_sim": jaro_winkler(a.latin, b.latin),
    }
