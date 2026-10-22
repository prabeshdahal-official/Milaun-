import sqlite3

import pytest

from milaun.privacy import (
    load_or_create_key,
    pseudonymize,
    pseudonymize_records,
    redact_name,
    safe_csv_cell,
    safe_csv_row,
)
from milaun.store import AuditStore


def test_pseudonym_is_deterministic_and_keyed(tmp_path):
    key_a = load_or_create_key(tmp_path / "a.key")
    key_b = load_or_create_key(tmp_path / "b.key")
    assert key_a != key_b
    first = pseudonymize("Prabesh Dahal", key_a)
    assert first == pseudonymize("Prabesh Dahal", key_a)
    assert first != pseudonymize("Prabesh Dahal", key_b)
    assert first.startswith("p_")
    assert len(first) == 18


def test_pseudonym_ignores_case_and_padding():
    key = b"0123456789abcdef"
    assert pseudonymize(" Prabesh ", key) == pseudonymize("prabesh", key)


def test_pseudonym_empty_value():
    assert pseudonymize("", b"0123456789abcdef") == ""


def test_key_reuse(tmp_path):
    path = tmp_path / "key.bin"
    first = load_or_create_key(path)
    second = load_or_create_key(path)
    assert first == second


def test_key_too_short_is_rejected(tmp_path):
    path = tmp_path / "short.key"
    path.write_bytes(b"short")
    with pytest.raises(ValueError):
        load_or_create_key(path)


def test_pseudonymize_records_does_not_mutate_input():
    records = [{"id": "1", "name": "Sita Sharma"}]
    output = pseudonymize_records(records, ["name"], b"0123456789abcdef")
    assert records[0]["name"] == "Sita Sharma"
    assert output[0]["name"] != "Sita Sharma"
    assert output[0]["id"] == "1"


def test_redact_name():
    assert redact_name("Prabesh Bahadur Dahal") == "P. B. D."
    assert redact_name("") == ""


@pytest.mark.parametrize("value", ["=cmd()", "+1", "-2", "@x", "\tdata"])
def test_csv_formula_injection_is_neutralised(value):
    assert safe_csv_cell(value).startswith("'")


def test_csv_plain_values_untouched():
    assert safe_csv_cell("Prabesh") == "Prabesh"
    assert safe_csv_cell(None) == ""
    assert safe_csv_row({"a": "=1", "b": "ok"}) == {"a": "'=1", "b": "ok"}


def test_store_roundtrip(tmp_path):
    with AuditStore(tmp_path / "audit.db") as store:
        run = store.start_run("dedupe", {"rows": 2}, {"clusters": 1})
        store.record_pair(run.run_id, "1", "2", 0.97, "match", {"key_sim": 1.0})
        store.finish_run(run.run_id, {"clusters": 1})
        runs = store.runs()
        assert runs[0]["kind"] == "dedupe"
        pairs = store.pairs(run.run_id)
        assert pairs[0]["left"] == "1"
        assert pairs[0]["probability"] == pytest.approx(0.97)


def test_store_schema_has_no_name_column(tmp_path):
    path = tmp_path / "audit.db"
    with AuditStore(path):
        pass
    connection = sqlite3.connect(path)
    columns = [row[1] for row in connection.execute("PRAGMA table_info(pairs)")]
    connection.close()
    assert "name" not in columns
    assert {"left_ref", "right_ref", "probability", "band"}.issubset(columns)


def test_store_rejects_newer_schema(tmp_path):
    path = tmp_path / "audit.db"
    with AuditStore(path):
        pass
    connection = sqlite3.connect(path)
    connection.execute("UPDATE schema_version SET version = 99")
    connection.commit()
    connection.close()
    with pytest.raises(RuntimeError):
        AuditStore(path)
