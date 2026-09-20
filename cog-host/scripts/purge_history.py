#!/usr/bin/env python3
"""Deletes searches (and their findings, via ON DELETE CASCADE) and audit_log
entries older than HISTORY_RETENTION_DAYS. Intended to run nightly, e.g. from
a systemd user timer or cron:

    .venv/bin/python scripts/purge_history.py
"""
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings
from app.db import get_conn


def main() -> None:
    cutoff = (
        datetime.now(UTC) - timedelta(days=settings.history_retention_days)
    ).isoformat()
    with get_conn(settings.db_path) as conn:
        searches_deleted = conn.execute(
            "DELETE FROM searches WHERE created_at < ?", (cutoff,)
        ).rowcount
        audit_deleted = conn.execute(
            "DELETE FROM audit_log WHERE created_at < ?", (cutoff,)
        ).rowcount
    print(f"Purged {searches_deleted} searches and {audit_deleted} audit_log entries older than {cutoff}")


if __name__ == "__main__":
    main()
