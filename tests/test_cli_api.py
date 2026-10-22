import csv
import json

import pytest

from milaun.api import create_app
from milaun.cli import main


@pytest.fixture()
def people_csv(tmp_path):
    path = tmp_path / "people.csv"
    rows = [
        ("1", "प्रवेश दाहाल"),
        ("2", "Prabesh Dahal"),
        ("3", "सीता शर्मा"),
        ("4", "Ramesh Karki"),
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["id", "name"])
        writer.writerows(rows)
    return path


# ------------------------------------------------------------------ CLI
def test_cli_compare_json(capsys):
    code = main(["compare", "Prabesh Dahal", "प्रवेश दाहाल", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["probability"] > 0.9


def test_cli_compare_human_output(capsys):
    code = main(["compare", "Sita Sharma", "Sita Karki"])
    output = capsys.readouterr().out
    assert code == 0
    assert "Probability" in output
    assert "Reasons" in output


def test_cli_key(capsys):
    assert main(["key", "Prabesh Dahal"]) == 0
    assert "DAHALPRABES" in capsys.readouterr().out


def test_cli_dedupe(people_csv, tmp_path, capsys):
    out = tmp_path / "clusters.csv"
    code = main(["dedupe", str(people_csv), "--out", str(out), "--store", str(tmp_path / "a.db")])
    assert code == 0
    assert out.is_file()
    with out.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert {row["member_id"] for row in rows} == {"1", "2"}
    assert "duplicate clusters" in capsys.readouterr().out


def test_cli_dedupe_missing_file(tmp_path, capsys):
    assert main(["dedupe", str(tmp_path / "nope.csv")]) == 2
    assert "no such file" in capsys.readouterr().err


def test_cli_dedupe_missing_column(people_csv, capsys):
    assert main(["dedupe", str(people_csv), "--name-col", "full_name"]) == 2
    assert "not in" in capsys.readouterr().err


def test_cli_link(people_csv, tmp_path, capsys):
    out = tmp_path / "pairs.csv"
    code = main(["link", str(people_csv), str(people_csv), "--out", str(out)])
    assert code == 0
    assert out.is_file()


def test_cli_pseudonymize(people_csv, tmp_path):
    out = tmp_path / "pseudo.csv"
    code = main([
        "pseudonymize", str(people_csv), "--column", "name",
        "--key-file", str(tmp_path / "key.bin"), "--out", str(out),
    ])
    assert code == 0
    with out.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert all(row["name"].startswith("p_") for row in rows)


# ------------------------------------------------------------------- API
@pytest.fixture()
def client():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    return TestClient(create_app())


def test_api_health(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_api_index_is_html(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Milaun" in response.text
    assert response.headers["x-content-type-options"] == "nosniff"


def test_api_compare(client):
    response = client.post("/api/compare", json={"left": "Sita Sharma", "right": "सीता शर्मा"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["probability"] > 0.9
    assert payload["band"] == "match"


def test_api_compare_rejects_blank(client):
    response = client.post("/api/compare", json={"left": "", "right": "Ram"})
    assert response.status_code == 422


def test_api_dedupe(client):
    response = client.post(
        "/api/dedupe",
        json={
            "records": [
                {"id": "1", "name": "Prabesh Dahal"},
                {"id": "2", "name": "प्रवेश दाहाल"},
                {"id": "3", "name": "Sita Sharma"},
            ]
        },
    )
    assert response.status_code == 200
    assert len(response.json()["clusters"]) == 1


def test_api_keys(client):
    response = client.get("/api/keys", params={"name": "Prabesh Dahal"})
    assert response.status_code == 200
    assert response.json()["key"] == "DAHALPRABES"


def test_api_info(client):
    response = client.get("/api/info")
    assert response.status_code == 200
    assert response.json()["thresholds"]["auto"] == 0.9
