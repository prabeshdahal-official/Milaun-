"""Blocking: cheap candidate generation before pairwise comparison.

Comparing every pair is quadratic. Blocking indexes short prefixes of the
phonetic keys and only compares records that share at least one key. Recall
lost here is unrecoverable, so the index is deliberately generous (three
characters per token key, three per skeleton) and
:func:`pair_completeness` exists to measure what it costs.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from milaun.phonetic import NameKeys


@dataclass(frozen=True)
class BlockingStats:
    n_records: int
    n_keys: int
    n_candidate_pairs: int
    total_possible_pairs: int

    @property
    def reduction_ratio(self) -> float:
        if self.total_possible_pairs == 0:
            return 0.0
        return 1.0 - self.n_candidate_pairs / self.total_possible_pairs

    def as_dict(self) -> dict[str, float | int]:
        return {
            "n_records": self.n_records,
            "n_keys": self.n_keys,
            "n_candidate_pairs": self.n_candidate_pairs,
            "total_possible_pairs": self.total_possible_pairs,
            "reduction_ratio": round(self.reduction_ratio, 6),
        }


def blocking_keys(keys: NameKeys) -> tuple[str, ...]:
    """Return the blocking keys for one record."""
    out: set[str] = set()
    for token_key in keys.keys:
        if len(token_key) >= 2:
            out.add("t:" + token_key[:3])
    for skeleton in keys.skeletons:
        if len(skeleton) >= 2:
            out.add("s:" + skeleton[:3])
    return tuple(sorted(out))


class BlockingIndex:
    """Inverted index from blocking key to record positions."""

    def __init__(self) -> None:
        self._index: dict[str, list[int]] = defaultdict(list)
        self._n_records = 0

    def add(self, position: int, keys: tuple[str, ...]) -> None:
        for key in keys:
            self._index[key].append(position)
        self._n_records = max(self._n_records, position + 1)

    def build(self, records: list[NameKeys]) -> BlockingIndex:
        for position, keys in enumerate(records):
            self.add(position, blocking_keys(keys))
        return self

    def candidate_pairs(self) -> set[tuple[int, int]]:
        """Return unordered pairs that share at least one blocking key."""
        pairs: set[tuple[int, int]] = set()
        for positions in self._index.values():
            if len(positions) < 2:
                continue
            for i in range(len(positions)):
                for j in range(i + 1, len(positions)):
                    left, right = positions[i], positions[j]
                    if left > right:
                        left, right = right, left
                    pairs.add((left, right))
        return pairs

    def stats(self) -> BlockingStats:
        n = self._n_records
        return BlockingStats(
            n_records=n,
            n_keys=len(self._index),
            n_candidate_pairs=len(self.candidate_pairs()),
            total_possible_pairs=n * (n - 1) // 2,
        )


def pair_completeness(
    candidate_pairs: set[tuple[int, int]], true_pairs: set[tuple[int, int]]
) -> float:
    """Share of known duplicate pairs that survive blocking."""
    if not true_pairs:
        return 1.0
    return len(candidate_pairs & true_pairs) / len(true_pairs)
