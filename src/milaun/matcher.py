"""The public matching API: compare, link and deduplicate names."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from milaun import model
from milaun.blocking import BlockingIndex, blocking_keys
from milaun.calibration import apply_calibration
from milaun.phonetic import NameKeys, name_keys
from milaun.similarity import FEATURES, pair_features

DATA_DIR = Path(__file__).resolve().parent / "data"

MATCH = "match"
REVIEW = "review"
DISTINCT = "distinct"


@dataclass
class MatchResult:
    """Outcome of comparing two names."""

    probability: float
    raw_score: float
    band: str
    features: dict[str, float]
    keys_a: dict[str, object]
    keys_b: dict[str, object]
    reasons: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "probability": round(self.probability, 6),
            "raw_score": round(self.raw_score, 6),
            "band": self.band,
            "features": {k: round(v, 6) for k, v in self.features.items()},
            "keys_a": self.keys_a,
            "keys_b": self.keys_b,
            "reasons": self.reasons,
        }


def _packaged(path: Path) -> dict:
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


class Matcher:
    """Calibrated name matcher.

    Parameters
    ----------
    weights:
        Logistic feature weights. Defaults to the packaged model, then to
        :data:`milaun.model.DEFAULT_WEIGHTS`.
    calibration:
        Calibration payload ``{"method": "platt"|"isotonic", "params": {...}}``.
        Defaults to the packaged curve; without one, the raw logistic score is
        used unchanged.
    auto_threshold / review_threshold:
        Probability bands. ``>= auto`` is an automatic match, ``>= review`` is
        an ambiguous pair that should go to a human, everything else is
        treated as distinct.
    """

    def __init__(
        self,
        weights: dict[str, float] | None = None,
        calibration: dict[str, list[float]] | None = None,
        auto_threshold: float = 0.90,
        review_threshold: float = 0.55,
        use_packaged: bool = True,
    ) -> None:
        self.metadata: dict = {}
        if weights is None and use_packaged:
            payload = _packaged(DATA_DIR / "model.json")
            weights = payload.get("weights")
            self.metadata = payload.get("metadata", {})
        self.weights = dict(weights) if weights else dict(model.DEFAULT_WEIGHTS)

        if calibration is None and use_packaged:
            payload = _packaged(DATA_DIR / "calibration.json")
            if payload:
                calibration = {
                    "method": payload.get("method", "platt"),
                    "params": payload.get("params", {}),
                }
                self.metadata.setdefault("calibration", payload.get("metadata", {}))
        self.calibration = calibration

        if not 0.0 <= review_threshold <= auto_threshold <= 1.0:
            raise ValueError("thresholds must satisfy 0 <= review <= auto <= 1")
        self.auto_threshold = auto_threshold
        self.review_threshold = review_threshold

    # ------------------------------------------------------------------ core
    def score(self, left: str, right: str) -> float:
        """Return the calibrated probability that two names are the same person."""
        keys_left = name_keys(left)
        keys_right = name_keys(right)
        return self._score_keys(keys_left, keys_right)[0]

    def decide(self, probability: float) -> str:
        """Map a probability to a decision band."""
        if probability >= self.auto_threshold:
            return MATCH
        if probability >= self.review_threshold:
            return REVIEW
        return DISTINCT

    def triage_by_cost(self, probability: float, cost_false_match: float = 1.0,
                       cost_missed_match: float = 10.0) -> str:
        """Bayes decision for asymmetric error costs.

        A false merge (two people treated as one) usually costs far less than a
        missed duplicate in welfare or clinical registries, so the default
        threshold is ``1 / (1 + 10)`` rather than 0.5.
        """
        if cost_false_match <= 0 or cost_missed_match <= 0:
            raise ValueError("costs must be positive")
        threshold = cost_false_match / (cost_false_match + cost_missed_match)
        return MATCH if probability >= threshold else DISTINCT

    def compare(self, left: str, right: str) -> MatchResult:
        """Compare two names and explain the decision."""
        keys_left = name_keys(left)
        keys_right = name_keys(right)
        return self._compare_keys(keys_left, keys_right)

    def _score_keys(self, keys_left: NameKeys, keys_right: NameKeys) -> tuple[float, float, dict]:
        features = pair_features(keys_left, keys_right)
        raw = model.score(self.weights, features)
        probability = apply_calibration(self.calibration, raw)
        return probability, raw, features

    def _compare_keys(self, keys_left: NameKeys, keys_right: NameKeys) -> MatchResult:
        probability, raw, features = self._score_keys(keys_left, keys_right)
        return MatchResult(
            probability=probability,
            raw_score=raw,
            band=self.decide(probability),
            features=features,
            keys_a=keys_left.as_dict(),
            keys_b=keys_right.as_dict(),
            reasons=self.explain(features, probability),
        )

    # ----------------------------------------------------------- explanation
    def explain(self, features: dict[str, float], probability: float) -> list[str]:
        """Turn feature values into short, factual statements."""
        reasons: list[str] = []
        if features["key_sim"] >= 0.999:
            reasons.append("Phonetic keys are identical.")
        elif features["skeleton_sim"] >= 0.999:
            reasons.append("Consonant skeletons are identical once vowels are removed.")
        elif features["key_sim"] >= 0.75:
            reasons.append(f"Phonetic keys are {features['key_sim']:.0%} similar.")

        if features["token_min_sim"] >= 0.99 and features["key_sim"] < 0.999:
            reasons.append("Every name token has a near-identical counterpart.")
        if features["last_token_sim"] >= 0.99:
            reasons.append("The family-name token matches.")
        if features["first_token_sim"] >= 0.99:
            reasons.append("The given-name token matches.")
        if features["latin_sim"] >= 0.92:
            reasons.append("The Latin forms are nearly identical.")
        if features["token_min_sim"] < 0.6:
            reasons.append("At least one name token has no close counterpart.")

        if not reasons:
            reasons.append("No individual signal is strong; score is dominated by weak similarity.")
        if probability >= self.auto_threshold:
            reasons.append("Probability is above the automatic-match threshold.")
        elif probability >= self.review_threshold:
            reasons.append("Probability falls in the human-review band.")
        return reasons[:4]

    # ------------------------------------------------------------- batch ops
    def dedupe(
        self,
        records: list[dict],
        name_field: str = "name",
        id_field: str = "id",
    ) -> dict:
        """Cluster duplicate records within one list.

        Returns a dict with ``clusters``, ``review_pairs`` and ``stats``.
        Only pairs at or above the auto threshold are merged; everything in the
        review band is returned for a human instead of being guessed at.
        """
        if not records:
            return {"clusters": [], "review_pairs": [], "stats": {"n_records": 0}}
        for position, record in enumerate(records):
            if name_field not in record:
                raise KeyError(f"record {position} has no field {name_field!r}")

        keys = [name_keys(str(record[name_field])) for record in records]
        index = BlockingIndex().build(keys)
        candidates = index.candidate_pairs()

        parent = list(range(len(records)))

        def find(node: int) -> int:
            while parent[node] != node:
                parent[node] = parent[parent[node]]
                node = parent[node]
            return node

        def union(a: int, b: int) -> None:
            root_a, root_b = find(a), find(b)
            if root_a != root_b:
                parent[max(root_a, root_b)] = min(root_a, root_b)

        edges: list[tuple[int, int, float]] = []
        review_pairs: list[dict] = []
        for left, right in sorted(candidates):
            result = self._compare_keys(keys[left], keys[right])
            if result.probability >= self.auto_threshold:
                union(left, right)
                edges.append((left, right, result.probability))
            elif result.probability >= self.review_threshold:
                review_pairs.append(
                    {
                        "left": self._record_id(records[left], id_field, left),
                        "right": self._record_id(records[right], id_field, right),
                        "left_name": records[left][name_field],
                        "right_name": records[right][name_field],
                        "probability": round(result.probability, 6),
                        "reasons": result.reasons[:2],
                    }
                )

        grouped: dict[int, list[int]] = {}
        for position in range(len(records)):
            grouped.setdefault(find(position), []).append(position)

        clusters: list[dict] = []
        for members in grouped.values():
            if len(members) < 2:
                continue
            member_set = set(members)
            cluster_edges = [prob for a, b, prob in edges if a in member_set and b in member_set]
            clusters.append(
                {
                    "cluster_id": self._record_id(records[min(members)], id_field, min(members)),
                    "size": len(members),
                    "members": [
                        self._record_id(records[pos], id_field, pos) for pos in members
                    ],
                    "names": [records[pos][name_field] for pos in members],
                    "min_probability": round(min(cluster_edges), 6) if cluster_edges else 1.0,
                }
            )
        clusters.sort(key=lambda cluster: (-cluster["size"], cluster["cluster_id"]))

        stats = index.stats().as_dict()
        stats.update(
            {
                "candidate_pairs": stats["n_candidate_pairs"],
                "auto_pairs": len(edges),
                "review_pairs": len(review_pairs),
                "clusters": len(clusters),
                "clustered_records": sum(cluster["size"] for cluster in clusters),
            }
        )
        return {"clusters": clusters, "review_pairs": review_pairs, "stats": stats}

    def link(
        self,
        left_records: list[dict],
        right_records: list[dict],
        name_field: str = "name",
        id_field: str = "id",
    ) -> dict:
        """Link two lists: return cross-list pairs at or above the auto threshold."""
        if not left_records or not right_records:
            return {"matches": [], "review_pairs": [], "stats": {"candidates": 0}}

        right_keys = [name_keys(str(record[name_field])) for record in right_records]
        right_index: dict[str, list[int]] = {}
        for position, keys in enumerate(right_keys):
            for key in blocking_keys(keys):
                right_index.setdefault(key, []).append(position)

        candidate_count = 0
        matches: list[dict] = []
        review_pairs: list[dict] = []
        for left_position, record in enumerate(left_records):
            left_keys = name_keys(str(record[name_field]))
            seen: set[int] = set()
            for key in blocking_keys(left_keys):
                for right_position in right_index.get(key, ()):
                    if right_position in seen:
                        continue
                    seen.add(right_position)
                    candidate_count += 1
                    result = self._compare_keys(left_keys, right_keys[right_position])
                    payload = {
                        "left": self._record_id(record, id_field, left_position),
                        "right": self._record_id(
                            right_records[right_position], id_field, right_position
                        ),
                        "left_name": record[name_field],
                        "right_name": right_records[right_position][name_field],
                        "probability": round(result.probability, 6),
                        "reasons": result.reasons[:2],
                    }
                    if result.probability >= self.auto_threshold:
                        matches.append(payload)
                    elif result.probability >= self.review_threshold:
                        review_pairs.append(payload)

        matches.sort(key=lambda item: -item["probability"])
        return {
            "matches": matches,
            "review_pairs": review_pairs,
            "stats": {
                "candidates": candidate_count,
                "matches": len(matches),
                "review_pairs": len(review_pairs),
            },
        }

    # ---------------------------------------------------------------- helpers
    @staticmethod
    def _record_id(record: dict, id_field: str, position: int) -> str:
        value = record.get(id_field)
        return str(value) if value is not None else f"row-{position}"

    def describe(self) -> dict:
        """Return configuration and provenance, for ``GET /api/info``."""
        return {
            "weights": {name: round(float(value), 6) for name, value in self.weights.items()},
            "thresholds": {"auto": self.auto_threshold, "review": self.review_threshold},
            "calibrated": bool(self.calibration),
            "features": list(FEATURES),
            "metadata": self.metadata,
        }

