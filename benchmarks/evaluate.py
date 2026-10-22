"""Reproducible evaluation.

Run from the repository root::

    python benchmarks/evaluate.py

Produces ``benchmarks/results/eval.json`` and ``benchmarks/results/RESULTS.md``.
Every number printed here comes from this script; nothing in the documentation
is hand-entered.

The report separates two questions that are easy to conflate:

* in-distribution accuracy on ``dev`` operation families (the ones used for
  training and calibration), and
* generalisation to ``hard`` operations (nukta, halant, sibilant swaps, typos)
  that the model never saw during fitting.

Only the second is evidence of robustness.
"""

from __future__ import annotations

import json
import statistics
import sys
import time
import tracemalloc
from pathlib import Path

BENCH_DIR = Path(__file__).resolve().parent
ROOT = BENCH_DIR.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(BENCH_DIR))

import baselines  # noqa: E402
import synth  # noqa: E402

from milaun import Matcher, __version__  # noqa: E402
from milaun.blocking import BlockingIndex, pair_completeness  # noqa: E402
from milaun.calibration import (  # noqa: E402
    brier,
    expected_calibration_error,
    reliability_table,
)
from milaun.phonetic import name_keys  # noqa: E402

RESULTS_DIR = BENCH_DIR / "results"
AUTO = 0.90
REVIEW = 0.55


def confusion(scores: list[float], labels: list[int], threshold: float) -> dict:
    tp = fp = fn = tn = 0
    for score, label in zip(scores, labels, strict=False):
        predicted = score >= threshold
        if predicted and label:
            tp += 1
        elif predicted and not label:
            fp += 1
        elif not predicted and label:
            fn += 1
        else:
            tn += 1
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "threshold": round(threshold, 4),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "false_positive_rate": round(fp / (fp + tn), 4) if fp + tn else 0.0,
    }


def average_precision(scores: list[float], labels: list[int]) -> float:
    """Area under the precision-recall curve, grouping tied scores.

    Scoring one rank at a time is wrong for discrete comparators such as exact
    match or Soundex: thousands of pairs share the same score, and Python's
    stable sort then ranks them in input order. That silently rewards whatever
    order the pairs happened to be generated in. Tied scores must be consumed
    as one operating point.
    """
    if not scores:
        return 0.0
    positives = sum(labels)
    if positives == 0:
        return 0.0

    order = sorted(range(len(scores)), key=lambda i: -scores[i])
    tp = fp = 0
    previous_recall = 0.0
    area = 0.0
    index = 0
    while index < len(order):
        score = scores[order[index]]
        while index < len(order) and scores[order[index]] == score:
            if labels[order[index]]:
                tp += 1
            else:
                fp += 1
            index += 1
        precision = tp / (tp + fp)
        recall = tp / positives
        area += (recall - previous_recall) * precision
        previous_recall = recall
    return area


def roc_auc(scores: list[float], labels: list[int]) -> float:
    """Probability that a random positive outranks a random negative."""
    positives = [s for s, y in zip(scores, labels, strict=False) if y]
    negatives = [s for s, y in zip(scores, labels, strict=False) if not y]
    if not positives or not negatives:
        return 0.0
    wins = 0.0
    for pos in positives:
        for neg in negatives:
            wins += 1.0 if pos > neg else (0.5 if pos == neg else 0.0)
    return wins / (len(positives) * len(negatives))


def tune_threshold(scores: list[float], labels: list[int]) -> float:
    """Choose the threshold with the best F1 on a calibration split."""
    candidates = sorted(set(scores))
    best_threshold, best_f1 = 0.5, -1.0
    for threshold in candidates:
        f1 = confusion(scores, labels, threshold)["f1"]
        if f1 > best_f1:
            best_threshold, best_f1 = threshold, f1
    return best_threshold


def summarise(scores: list[float], labels: list[int]) -> dict:
    auto = confusion(scores, labels, AUTO)
    review = confusion(scores, labels, REVIEW)
    review_band = sum(1 for score in scores if REVIEW <= score < AUTO)
    positives = sum(labels)
    positives_in_review = sum(
        1 for score, label in zip(scores, labels, strict=False) if label and REVIEW <= score < AUTO
    )
    return {
        "n_pairs": len(scores),
        "n_positives": positives,
        "n_negatives": len(scores) - positives,
        "at_auto": auto,
        "at_review": review,
        "review_band": {
            "pairs": review_band,
            "share_of_pairs": round(review_band / len(scores), 4) if scores else 0.0,
            "positives": positives_in_review,
            "share_of_positives": round(positives_in_review / positives, 4) if positives else 0.0,
        },
        "average_precision": round(average_precision(scores, labels), 4),
        "roc_auc": round(roc_auc(scores, labels), 4),
        "brier": round(brier(scores, labels), 4),
        "ece_10bin": round(expected_calibration_error(scores, labels), 4),
        "reliability": reliability_table(scores, labels),
        "score_range": {
            "min": round(min(scores), 4) if scores else 0.0,
            "max": round(max(scores), 4) if scores else 0.0,
            "median": round(statistics.median(scores), 4) if scores else 0.0,
        },
    }


def error_examples(pairs: list[synth.Pair], scores: list[float], limit: int = 8) -> dict:
    false_positives = []
    false_negatives = []
    for pair, score in zip(pairs, scores, strict=False):
        entry = {
            "left": pair.left_name,
            "right": pair.right_name,
            "probability": round(score, 4),
            "ops": pair.ops,
        }
        if pair.label == 0 and score >= AUTO:
            false_positives.append(entry)
        elif pair.label == 1 and score < REVIEW:
            false_negatives.append(entry)
    false_positives.sort(key=lambda item: -item["probability"])
    false_negatives.sort(key=lambda item: item["probability"])
    return {
        "false_positives_at_auto": false_positives[:limit],
        "missed_positives_below_review": false_negatives[:limit],
        "n_false_positives": len(false_positives),
        "n_missed_below_review": len(false_negatives),
    }


def cluster_metrics(records: list[dict], clusters: list[dict]) -> dict:
    membership = {record["id"]: record["true_identity"] for record in records}
    true_pairs = set()
    ids = [record["id"] for record in records]
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            if membership[ids[i]] == membership[ids[j]]:
                true_pairs.add((min(ids[i], ids[j]), max(ids[i], ids[j])))

    predicted_pairs = set()
    for cluster in clusters:
        members = cluster["members"]
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                predicted_pairs.add((min(members[i], members[j]), max(members[i], members[j])))

    intersection = true_pairs & predicted_pairs
    precision = len(intersection) / len(predicted_pairs) if predicted_pairs else 0.0
    recall = len(intersection) / len(true_pairs) if true_pairs else 0.0

    exact = 0
    for cluster in clusters:
        identities = {membership[member] for member in cluster["members"]}
        if len(identities) == 1:
            exact += 1
    total_identities = len(set(membership.values()))
    return {
        "records": len(records),
        "true_duplicate_pairs": len(true_pairs),
        "predicted_pairs": len(predicted_pairs),
        "pairwise_precision": round(precision, 4),
        "pairwise_recall": round(recall, 4),
        "clusters": len(clusters),
        "pure_clusters": exact,
        "total_identities": total_identities,
        "cluster_purity": round(exact / len(clusters), 4) if clusters else 0.0,
    }


def main() -> int:
    identities = synth.load_identities()
    dev_pairs = synth.build_pairs(identities, family="dev")
    hard_pairs = synth.build_pairs(identities, family="hard")
    dev_test = [pair for pair in dev_pairs if pair.split == "test"]
    dev_calib = [pair for pair in dev_pairs if pair.split == "calib"]
    hard_test = [pair for pair in hard_pairs if pair.split == "hard_test"]

    matcher = Matcher(auto_threshold=AUTO, review_threshold=REVIEW)
    started = time.perf_counter()
    dev_scores = [matcher.compare(pair.left_name, pair.right_name).probability for pair in dev_test]
    hard_scores = [
        matcher.compare(pair.left_name, pair.right_name).probability for pair in hard_test
    ]
    compare_seconds = time.perf_counter() - started
    n_compared = len(dev_test) + len(hard_test)

    report: dict = {
        "tool": {"name": "milaun", "version": __version__},
        "dataset": {
            "seed_file": "benchmarks/data/seed_names.csv",
            "identities": len(identities),
            "seed": synth.DEFAULT_SEED,
            "dev_test_pairs": len(dev_test),
            "dev_test_positives": sum(pair.label for pair in dev_test),
            "hard_test_pairs": len(hard_test),
            "hard_test_positives": sum(pair.label for pair in hard_test),
            "note": "synthetic variants generated from documented orthographic operations",
        },
        "model": {
            "thresholds": {"auto": AUTO, "review": REVIEW},
            "metadata": matcher.metadata,
            "dev_test": summarise(dev_scores, [pair.label for pair in dev_test]),
            "hard_test": summarise(hard_scores, [pair.label for pair in hard_test]),
            "errors_hard_test": error_examples(hard_test, hard_scores),
        },
        "performance": {
            "pairs_scored": n_compared,
            "seconds": round(compare_seconds, 3),
            "pairs_per_second": round(n_compared / compare_seconds, 1) if compare_seconds else 0.0,
            "milliseconds_per_pair": round(1000 * compare_seconds / n_compared, 3)
            if n_compared
            else 0.0,
        },
        "baselines": {},
    }

    # ---------------------------------------------------------- baselines
    calib_scores_by_name: dict[str, list[float]] = {}
    for name, function in baselines.BASELINES.items():
        calib_scores_by_name[name] = [function(p.left_name, p.right_name) for p in dev_calib]
        threshold = tune_threshold(calib_scores_by_name[name], [p.label for p in dev_calib])
        test_scores = [function(p.left_name, p.right_name) for p in dev_test]
        hard_scores_b = [function(p.left_name, p.right_name) for p in hard_test]
        report["baselines"][name] = {
            "threshold_tuned_on_dev_calib": round(threshold, 4),
            "dev_test": confusion(test_scores, [p.label for p in dev_test], threshold),
            "hard_test": confusion(hard_scores_b, [p.label for p in hard_test], threshold),
            "hard_test_average_precision": round(
                average_precision(hard_scores_b, [p.label for p in hard_test]), 4
            ),
        }

    # ----------------------------------------------------------- blocking
    registry = synth.build_registry(identities[:60], copies=3, seed=synth.DEFAULT_SEED)
    registry_keys = [name_keys(record["name"]) for record in registry]
    index = BlockingIndex().build(registry_keys)
    candidates = index.candidate_pairs()
    true_pairs_registry = set()
    for i in range(len(registry)):
        for j in range(i + 1, len(registry)):
            if registry[i]["true_identity"] == registry[j]["true_identity"]:
                true_pairs_registry.add((i, j))
    report["blocking"] = index.stats().as_dict()
    report["blocking"]["pair_completeness"] = round(
        pair_completeness(candidates, true_pairs_registry), 4
    )

    # -------------------------------------------------- clustering + memory
    tracemalloc.start()
    cluster_started = time.perf_counter()
    dedupe = matcher.dedupe(registry)
    cluster_seconds = time.perf_counter() - cluster_started
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    report["clusters"] = cluster_metrics(registry, dedupe["clusters"])
    report["clusters"].update(
        {
            "records": len(registry),
            "review_pairs": len(dedupe["review_pairs"]),
            "seconds": round(cluster_seconds, 3),
            "peak_memory_kib": round(peak / 1024, 1),
            "blocking_stats": dedupe["stats"],
        }
    )

    # ---------------------------------------------- irreducible collisions
    homonyms = 0
    flagged = 0
    for identity in identities[:20]:
        homonyms += 1
        if matcher.compare(identity.name_lat, identity.name_lat).probability >= AUTO:
            flagged += 1
    report["homonym_probe"] = {
        "pairs": homonyms,
        "scored_above_auto": flagged,
        "note": (
            "identical names belonging to different people are indistinguishable from names "
            "alone; this is the irreducible error floor of any name-only matcher"
        ),
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "eval.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (RESULTS_DIR / "RESULTS.md").write_text(render_markdown(report), encoding="utf-8")

    print_markdown(report)
    print(f"\nwrote {RESULTS_DIR / 'eval.json'} and {RESULTS_DIR / 'RESULTS.md'}")
    return 0


def render_markdown(report: dict) -> str:
    model = report["model"]
    dev = model["dev_test"]
    hard = model["hard_test"]
    lines = [
        "# Milaun evaluation results",
        "",
        "Generated by `python benchmarks/evaluate.py`. Do not edit by hand.",
        "",
        f"Dataset: {report['dataset']['identities']} seed identities, "
        f"seed {report['dataset']['seed']}, "
        f"{report['dataset']['dev_test_pairs']} dev-test pairs "
        f"({report['dataset']['dev_test_positives']} positives), "
        f"{report['dataset']['hard_test_pairs']} hard-test pairs "
        f"({report['dataset']['hard_test_positives']} positives).",
        "",
        "## Headline",
        "",
        "| Split | Precision @0.90 | Recall @0.90 | F1 | PR-AUC | ROC-AUC | ECE | Brier |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for name, block in (("dev-test (in-distribution)", dev), ("hard-test (held-out ops)", hard)):
        auto = block["at_auto"]
        lines.append(
            f"| {name} | {auto['precision']:.3f} | {auto['recall']:.3f} | {auto['f1']:.3f} | "
            f"{block['average_precision']:.3f} | {block['roc_auc']:.3f} | "
            f"{block['ece_10bin']:.3f} | {block['brier']:.3f} |"
        )

    lines += [
        "",
        "## Baseline comparison on hard-test",
        "",
        "Baselines were tuned on the dev-calibration split (best F1) and then frozen.",
        "",
        "| Method | Precision | Recall | F1 | PR-AUC |",
        "|---|---|---|---|---|",
    ]
    for name, block in report["baselines"].items():
        hard_block = block["hard_test"]
        lines.append(
            f"| {name} | {hard_block['precision']:.3f} | {hard_block['recall']:.3f} | "
            f"{hard_block['f1']:.3f} | {block['hard_test_average_precision']:.3f} |"
        )
    lines.append(
        f"| **milaun** | **{hard['at_auto']['precision']:.3f}** | "
        f"**{hard['at_auto']['recall']:.3f}** | **{hard['at_auto']['f1']:.3f}** | "
        f"**{hard['average_precision']:.3f}** |"
    )

    lines += [
        "",
        "## Review band",
        "",
        f"Pairs scored between {REVIEW:.2f} and {AUTO:.2f} are routed to a human. "
        "On hard-test that band holds "
        f"{hard['review_band']['positives']} true matches "
        f"({hard['review_band']['share_of_positives']:.1%} of all positives).",
        "",
        "## Blocking",
        "",
        f"- Candidate pairs: {report['blocking']['n_candidate_pairs']} of "
        f"{report['blocking']['total_possible_pairs']} possible "
        f"({report['blocking']['reduction_ratio']:.1%} reduction)",
        f"- Pair completeness: {report['blocking']['pair_completeness']:.1%}",
        "",
        "## Duplicate clustering",
        "",
        f"- Records: {report['clusters']['records']}",
        f"- Pairwise precision / recall: {report['clusters']['pairwise_precision']:.3f} / "
        f"{report['clusters']['pairwise_recall']:.3f}",
        f"- Cluster purity: {report['clusters']['cluster_purity']:.3f} "
        f"({report['clusters']['pure_clusters']} of {report['clusters']['clusters']} clusters)",
        f"- Runtime: {report['clusters']['seconds']}s, peak memory "
        f"{report['clusters']['peak_memory_kib']} KiB",
        "",
        "## Performance",
        "",
        f"- {report['performance']['pairs_per_second']:.0f} pairs/second "
        f"({report['performance']['milliseconds_per_pair']:.3f} ms per pair) on one CPU core",
        "",
        "## Known failure modes",
        "",
        f"- {report['model']['errors_hard_test']['n_false_positives']} false positives at 0.90 "
        "on hard-test; see `eval.json` for examples.",
        f"- {report['model']['errors_hard_test']['n_missed_below_review']} positives scored below "
        "0.55 on hard-test.",
        f"- Homonym probe: {report['homonym_probe']['scored_above_auto']} of "
        f"{report['homonym_probe']['pairs']} identical-name pairs scored above 0.90 by "
        "construction. Names alone cannot separate two people who share a name; combine "
        "with date of birth, address or an identifier.",
        "",
    ]
    return "\n".join(lines)


def print_markdown(report: dict) -> None:
    print(render_markdown(report))


if __name__ == "__main__":
    raise SystemExit(main())
