"""Command-line interface.

``milaun compare``/``dedupe``/``link`` are the primary surface: they work
offline on CSV files, which is how most registries and NGOs actually store
data. ``serve`` adds a local web UI for demonstration and manual review.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from milaun import __version__
from milaun.matcher import Matcher
from milaun.phonetic import name_keys
from milaun.privacy import load_or_create_key, pseudonymize, safe_csv_row
from milaun.store import AuditStore

MAX_ROWS = 200_000


def _read_csv(path: Path) -> list[dict]:
    if not path.is_file():
        raise FileNotFoundError(f"no such file: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"{path} is empty (no header row)")
        rows = []
        for index, row in enumerate(reader):
            if index >= MAX_ROWS:
                raise ValueError(f"{path} exceeds the {MAX_ROWS}-row safety limit")
            rows.append(row)
    return rows


def _write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(safe_csv_row(row))


def _matcher(args: argparse.Namespace) -> Matcher:
    return Matcher(auto_threshold=args.auto, review_threshold=args.review)


def cmd_compare(args: argparse.Namespace) -> int:
    matcher = _matcher(args)
    result = matcher.compare(args.left, args.right)
    if args.json:
        print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2))
        return 0
    print(f"Probability: {result.probability:.4f}  band={result.band}")
    print(f"  {args.left!r:>28} -> key={result.keys_a['key']} skeleton={result.keys_a['skeleton']}")
    right_keys = result.keys_b
    print(
        f"  {args.right!r:>28} -> key={right_keys['key']} "
        f"skeleton={right_keys['skeleton']}"
    )
    print("Reasons:")
    for reason in result.reasons:
        print(f"  - {reason}")
    print("Features: " + "  ".join(f"{k}={v:.3f}" for k, v in result.features.items()))
    return 0


def cmd_key(args: argparse.Namespace) -> int:
    keys = name_keys(args.name)
    payload = keys.as_dict()
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    print(f"normalized: {keys.normalized}")
    print(f"latin     : {keys.latin}")
    print(f"script    : {keys.script}")
    print(f"tokens    : {' '.join(keys.tokens)}")
    print(f"keys      : {' '.join(keys.keys)}")
    print(f"key       : {keys.key}")
    print(f"skeleton  : {keys.skeleton}")
    return 0


def cmd_dedupe(args: argparse.Namespace) -> int:
    rows = _read_csv(Path(args.csv))
    if not rows:
        print("error: no data rows", file=sys.stderr)
        return 2
    if args.name_col not in rows[0]:
        print(f"error: column {args.name_col!r} not in {list(rows[0])}", file=sys.stderr)
        return 2

    matcher = _matcher(args)
    result = matcher.dedupe(rows, name_field=args.name_col, id_field=args.id_col)

    store = AuditStore(args.store) if args.store else None
    if store:
        run = store.start_run(
            "dedupe",
            {"rows": len(rows), "name_col": args.name_col, "auto": matcher.auto_threshold},
            result["stats"],
        )
        for cluster in result["clusters"]:
            for member in cluster["members"]:
                store.record_pair(
                    run.run_id, cluster["cluster_id"], member, cluster["min_probability"], "match"
                )
        store.close()

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    stats = result["stats"]
    print(
        f"{len(rows)} records -> {stats['candidate_pairs']} candidate pairs "
        f"({stats['reduction_ratio']:.1%} blocking reduction), "
        f"{stats['clusters']} duplicate clusters covering {stats['clustered_records']} records"
    )
    for cluster in result["clusters"][:10]:
        print(f"\ncluster {cluster['cluster_id']} (size {cluster['size']}, "
              f"min p={cluster['min_probability']:.3f})")
        for member, name in zip(cluster["members"], cluster["names"], strict=False):
            print(f"  - {member}: {name}")
    if len(result["clusters"]) > 10:
        print(f"\n... {len(result['clusters']) - 10} more clusters")
    if result["review_pairs"]:
        print(f"\n{len(result['review_pairs'])} pairs need human review "
              f"(probabilities {matcher.review_threshold:.2f}-{matcher.auto_threshold:.2f})")

    if args.out:
        out_rows: list[dict] = []
        for cluster in result["clusters"]:
            for member, name in zip(cluster["members"], cluster["names"], strict=False):
                out_rows.append(
                    {
                        "cluster_id": cluster["cluster_id"],
                        "size": cluster["size"],
                        "member_id": member,
                        "name": name,
                        "min_probability": cluster["min_probability"],
                    }
                )
        _write_csv(Path(args.out), out_rows, ["cluster_id", "size", "member_id", "name",
                                              "min_probability"])
        print(f"\nwrote {len(out_rows)} rows to {args.out}")
    return 0


def cmd_link(args: argparse.Namespace) -> int:
    left = _read_csv(Path(args.left))
    right = _read_csv(Path(args.right))
    for label, rows, column in (("left", left, args.left_col), ("right", right, args.right_col)):
        if not rows:
            print(f"error: {label} file has no data rows", file=sys.stderr)
            return 2
        if column not in rows[0]:
            print(f"error: column {column!r} not in {label} file", file=sys.stderr)
            return 2

    matcher = _matcher(args)
    result = matcher.link(left, right, name_field=args.left_col, id_field=args.id_col)
    if args.right_col != args.left_col:
        right_for_match = []
        for record in right:
            right_for_match.append({"id": record.get(args.id_col), "name": record[args.right_col]})
        result = matcher.link(
            [{"id": record.get(args.id_col), "name": record[args.left_col]} for record in left],
            right_for_match,
            name_field="name",
            id_field="id",
        )

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    stats = result["stats"]
    print(
        f"{len(left)} x {len(right)} records -> {stats['candidates']} candidates, "
        f"{stats['matches']} matches, {stats['review_pairs']} for review"
    )
    for match in result["matches"][:10]:
        print(f"  {match['left']} {match['left_name']!r} <-> {match['right']} "
              f"{match['right_name']!r}  p={match['probability']:.3f}")
    if args.out:
        rows = result["matches"] + result["review_pairs"]
        _write_csv(
            Path(args.out),
            [
                {
                    "left_id": item["left"],
                    "left_name": item["left_name"],
                    "right_id": item["right"],
                    "right_name": item["right_name"],
                    "probability": item["probability"],
                }
                for item in rows
            ],
            ["left_id", "left_name", "right_id", "right_name", "probability"],
        )
        print(f"wrote {len(rows)} rows to {args.out}")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    try:
        import uvicorn
    except ImportError:
        print("error: the web UI needs extra packages: pip install 'milaun[web]'", file=sys.stderr)
        return 2
    from milaun.api import create_app

    uvicorn.run(create_app(), host=args.host, port=args.port, log_level="warning")
    return 0


def cmd_pseudonymize(args: argparse.Namespace) -> int:
    rows = _read_csv(Path(args.csv))
    if not rows or args.column not in rows[0]:
        print(f"error: column {args.column!r} not found", file=sys.stderr)
        return 2
    key = load_or_create_key(args.key_file)
    for row in rows:
        row[args.column] = pseudonymize(row[args.column], key)
    _write_csv(Path(args.out), rows, list(rows[0].keys()))
    print(f"pseudonymised {len(rows)} rows -> {args.out}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="milaun",
        description="Offline record linkage for Nepali names across Devanagari and Latin script.",
    )
    parser.add_argument("--version", action="version", version=f"milaun {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_thresholds(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--auto", type=float, default=0.90,
            help="auto-match threshold (default 0.90)",
        )
        p.add_argument("--review", type=float, default=0.55, help="review threshold (default 0.55)")

    compare = sub.add_parser("compare", help="compare two names")
    compare.add_argument("left")
    compare.add_argument("right")
    compare.add_argument("--json", action="store_true")
    add_thresholds(compare)
    compare.set_defaults(func=cmd_compare)

    key = sub.add_parser("key", help="show phonetic keys for one name")
    key.add_argument("name")
    key.add_argument("--json", action="store_true")
    key.set_defaults(func=cmd_key)

    dedupe = sub.add_parser("dedupe", help="cluster duplicates inside a CSV")
    dedupe.add_argument("csv")
    dedupe.add_argument("--name-col", default="name")
    dedupe.add_argument("--id-col", default="id")
    dedupe.add_argument("--out")
    dedupe.add_argument("--store", help="write an audit trail to this SQLite file")
    dedupe.add_argument("--json", action="store_true")
    add_thresholds(dedupe)
    dedupe.set_defaults(func=cmd_dedupe)

    link = sub.add_parser("link", help="link two CSV files")
    link.add_argument("left")
    link.add_argument("right")
    link.add_argument("--left-col", default="name")
    link.add_argument("--right-col", default="name")
    link.add_argument("--id-col", default="id")
    link.add_argument("--out")
    link.add_argument("--json", action="store_true")
    add_thresholds(link)
    link.set_defaults(func=cmd_link)

    serve = sub.add_parser("serve", help="run the local web UI")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.set_defaults(func=cmd_serve)

    pseudo = sub.add_parser("pseudonymize", help="replace a CSV column with keyed pseudonyms")
    pseudo.add_argument("csv")
    pseudo.add_argument("--column", required=True)
    pseudo.add_argument("--key-file", default="milaun.key")
    pseudo.add_argument("--out", required=True)
    pseudo.set_defaults(func=cmd_pseudonymize)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except (ValueError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
