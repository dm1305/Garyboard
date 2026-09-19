import pytest
from fastapi.testclient import TestClient

from app import main
from app.db import get_conn, init_db


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    monkeypatch.setattr(main.settings, "db_path", db_path)

    with get_conn(db_path) as conn:
        cursor = conn.execute(
            "INSERT INTO searches (input_type, raw_value, purpose) VALUES (?, ?, ?)",
            ("email", "test@example.com", "own_footprint"),
        )
        search_id = cursor.lastrowid
        conn.execute(
            """
            INSERT INTO findings
                (search_id, module, kind, title, url, detail_json, confidence, sensitive, fetched_at, cached)
            VALUES (?, 'github', 'profile', 'GitHub: test', 'https://github.com/test', '{"note": "x"}',
                    'high', 0, '2026-01-01T00:00:00+00:00', 0)
            """,
            (search_id,),
        )

    return TestClient(main.app), search_id


def test_export_json_returns_search_and_findings(client):
    test_client, search_id = client
    resp = test_client.get(f"/history/{search_id}/export.json")
    assert resp.status_code == 200
    data = resp.json()
    assert data["search"]["raw_value"] == "test@example.com"
    assert len(data["findings"]) == 1
    assert data["findings"][0]["module"] == "github"
    assert data["findings"][0]["detail"] == {"note": "x"}
    assert "attachment" in resp.headers["content-disposition"]


def test_export_csv_returns_rows(client):
    test_client, search_id = client
    resp = test_client.get(f"/history/{search_id}/export.csv")
    assert resp.status_code == 200
    assert "github" in resp.text
    assert "https://github.com/test" in resp.text
    assert "attachment" in resp.headers["content-disposition"]


def test_export_404_for_unknown_search(client):
    test_client, _ = client
    resp = test_client.get("/history/999999/export.json")
    assert resp.status_code == 404
