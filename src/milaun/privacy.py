"""Privacy helpers: pseudonymisation, redaction and CSV injection guards.

Names are personal data. Milaun runs locally, but two leaks are easy to make
by accident: writing raw identifiers into an audit database that later gets
shared, and exporting a CSV whose cells are executed as formulas by a
spreadsheet. Both are handled here.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from pathlib import Path

KEY_BYTES = 32
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def load_or_create_key(path: str | Path) -> bytes:
    """Return a persistent HMAC key, creating it with owner-only permissions."""
    key_path = Path(path)
    if key_path.is_file():
        key = key_path.read_bytes()
        if len(key) < 16:
            raise ValueError(f"key file {key_path} is too short to be a usable secret")
        return key
    key = secrets.token_bytes(KEY_BYTES)
    key_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_bytes(key)
    try:
        os.chmod(key_path, 0o600)
    except OSError:  # pragma: no cover - platform specific
        pass
    return key


def pseudonymize(value: str, key: bytes, prefix: str = "p_", length: int = 16) -> str:
    """Return a deterministic keyed pseudonym for a value.

    Deterministic on purpose: the same person must map to the same pseudonym in
    two datasets for linkage to be possible. That also means this is
    pseudonymisation, not anonymisation - a secret key plus a small name space
    can still be brute-forced. See ``docs/THREAT_MODEL.md``.
    """
    if not value:
        return ""
    digest = hmac.new(key, value.strip().lower().encode("utf-8"), hashlib.sha256).hexdigest()
    return prefix + digest[:length]


def pseudonymize_records(
    records: list[dict],
    fields: list[str],
    key: bytes,
    prefix: str = "p_",
) -> list[dict]:
    """Return copies of ``records`` with the listed fields pseudonymised."""
    output: list[dict] = []
    for record in records:
        copy = dict(record)
        for field in fields:
            if field in copy and copy[field] is not None:
                copy[field] = pseudonymize(str(copy[field]), key, prefix=prefix)
        output.append(copy)
    return output


def redact_name(name: str) -> str:
    """Reduce a name to initials: ``Prabesh Dahal`` -> ``P. D.``."""
    initials = [part[0].upper() for part in str(name).split() if part]
    return " ".join(f"{letter}." for letter in initials)


def safe_csv_cell(value: object) -> str:
    """Neutralise spreadsheet formula injection without changing the text."""
    text = "" if value is None else str(value)
    if text.startswith(_FORMULA_PREFIXES):
        return "'" + text
    return text


def safe_csv_row(row: dict) -> dict:
    return {key: safe_csv_cell(value) for key, value in row.items()}
