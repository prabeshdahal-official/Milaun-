"""End-to-end demo on a tiny mixed-script registry.

Run from the repository root::

    python examples/demo.py

The CSV is deliberately messy: names appear in Devanagari and Latin script,
with schwa insertion, aspiration changes and a same-surname different-person
pair that must not be merged.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from milaun import Matcher  # noqa: E402

DATA = Path(__file__).resolve().parent / "people.csv"


def load() -> list[dict]:
    with DATA.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> int:
    records = load()
    matcher = Matcher()

    print(f"Loaded {len(records)} records from {DATA.name}\n")

    print("Pairwise checks")
    print("-" * 72)
    checks = [
        ("प्रवेश दाहाल", "Prabesh Dahal"),
        ("सीता शर्मा", "Sita Karki"),
        ("अनिता तामाङ", "Anita Thapa"),
        ("रमेश ढकाल", "Ramesh Dhakal"),
    ]
    for left, right in checks:
        result = matcher.compare(left, right)
        print(f"  {left:<22} {right:<22} p={result.probability:.3f}  {result.band}")

    print("\nDuplicate clusters")
    print("-" * 72)
    result = matcher.dedupe(records, name_field="name", id_field="id")
    for cluster in result["clusters"]:
        print(f"  cluster {cluster['cluster_id']} (min p={cluster['min_probability']:.3f})")
        for member, name in zip(cluster["members"], cluster["names"], strict=True):
            print(f"    - {member}: {name}")

    stats = result["stats"]
    print(
        f"\n{stats['clusters']} clusters, {stats['clustered_records']} of "
        f"{stats['n_records']} records clustered; "
        f"{stats['candidate_pairs']} candidate pairs after blocking."
    )
    if result["review_pairs"]:
        print(f"\n{len(result['review_pairs'])} pair(s) need human review:")
        for pair in result["review_pairs"]:
            print(
                f"  {pair['left']} {pair['left_name']} <-> {pair['right']} "
                f"{pair['right_name']}  p={pair['probability']:.3f}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
