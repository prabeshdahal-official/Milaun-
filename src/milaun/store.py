"""Append-only SQLite audit trail.

Record linkage decisions often need to be explained months later ("why were
these two patients merged?"). The store keeps one row per run and one row per
reviewed pair. It never stores raw names: callers pass record ids or
pseudonyms, and the schema has no free-text name column.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    kind TEXT NOT NULL,
    params TEXT NOT NULL,
    stats TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pairs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES runs(id),
    left_ref TEXT NOT NULL,
    right_ref TEXT NOT NULL,
    probability REAL NOT NULL,
    band TEXT NOT NULL,
    features TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_pairs_run ON pairs(run_id);
"""


@dataclass
class RunRecord:
    run_id: int
    created_at: str
    kind: str


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class AuditStore:
    """Thin wrapper around a local SQLite file."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(str(self.path))
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.executescript(_SCHEMA)
        row = self._connection.execute("SELECT version FROM schema_version").fetchone()
        if row is None:
            self._connection.execute(
                "INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,)
            )
        elif row[0] > SCHEMA_VERSION:
            raise RuntimeError(
                f"audit database schema v{row[0]} is newer than this Milaun build "
                f"(v{SCHEMA_VERSION}); upgrade Milaun instead of downgrading the file"
            )
        self._connection.commit()

    def start_run(self, kind: str, params: dict, stats: dict) -> RunRecord:
        cursor = self._connection.execute(
            "INSERT INTO runs (created_at, kind, params, stats) VALUES (?, ?, ?, ?)",
            (_now(), kind, json.dumps(params, sort_keys=True), json.dumps(stats, sort_keys=True)),
        )
        self._connection.commit()
        return RunRecord(run_id=int(cursor.lastrowid), created_at=_now(), kind=kind)

    def record_pair(
        self,
        run_id: int,
        left_ref: str,
        right_ref: str,
        probability: float,
        band: str,
        features: dict[str, float] | None = None,
    ) -> None:
        self._connection.execute(
            "INSERT INTO pairs (run_id, left_ref, right_ref, probability, band, features)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (
                run_id,
                left_ref,
                right_ref,
                float(probability),
                band,
                json.dumps(features or {}, sort_keys=True),
            ),
        )

    def finish_run(self, run_id: int, stats: dict) -> None:
        self._connection.execute(
            "UPDATE runs SET stats = ? WHERE id = ?", (json.dumps(stats, sort_keys=True), run_id)
        )
        self._connection.commit()

    def runs(self, limit: int = 20) -> list[dict]:
        rows = self._connection.execute(
            "SELECT id, created_at, kind, stats FROM runs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [
            {"run_id": row[0], "created_at": row[1], "kind": row[2], "stats": json.loads(row[3])}
            for row in rows
        ]

    def pairs(self, run_id: int) -> list[dict]:
        rows = self._connection.execute(
            "SELECT left_ref, right_ref, probability, band FROM pairs WHERE run_id = ?"
            " ORDER BY probability DESC",
            (run_id,),
        ).fetchall()
        return [
            {"left": row[0], "right": row[1], "probability": row[2], "band": row[3]}
            for row in rows
        ]

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> AuditStore:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()
