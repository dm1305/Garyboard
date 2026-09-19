import sqlite3

from app.db import get_conn


def test_purge_deletes_searches_and_findings(db_path):
    with get_conn(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO searches (input_type, raw_value, purpose) VALUES (?, ?, ?)",
            ("email", "a@example.com", "own_footprint"),
        )
        search_id = cur.lastrowid
        conn.execute(
            """INSERT INTO findings
               (search_id, module, kind, title, confidence, fetched_at)
               VALUES (?, 'm', 'note', 'x', 'low', '2026-01-01')""",
            (search_id,),
        )

    with get_conn(db_path) as conn:
        conn.execute("DELETE FROM searches")

    with get_conn(db_path) as conn:
        remaining_searches = conn.execute("SELECT COUNT(*) FROM searches").fetchone()[0]
        remaining_findings = conn.execute("SELECT COUNT(*) FROM findings").fetchone()[0]

    assert remaining_searches == 0
    assert remaining_findings == 0  # ON DELETE CASCADE


def test_db_file_permissions_are_owner_only(db_path):
    mode = oct(db_path.stat().st_mode)[-3:]
    assert mode == "600"
