from datetime import UTC, datetime
from pathlib import Path

from app.db import get_conn

MONTHLY_LIMITS = {
    "hunter": 50,
    "veriphone": 1000,
    "tavily": 1000,
    "gravatar": 100,
}


def _current_period() -> str:
    return datetime.now(UTC).strftime("%Y-%m")


def get_used(db_path: Path, module: str) -> int:
    period = _current_period()
    with get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT used FROM quota WHERE module = ? AND period = ?", (module, period)
        ).fetchone()
    return row["used"] if row else 0


def increment(db_path: Path, module: str, cost: int = 1) -> None:
    if cost <= 0:
        return
    period = _current_period()
    with get_conn(db_path) as conn:
        conn.execute(
            """
            INSERT INTO quota (module, period, used) VALUES (?, ?, ?)
            ON CONFLICT(module, period) DO UPDATE SET used = used + excluded.used
            """,
            (module, period, cost),
        )


def status(db_path: Path) -> list[dict]:
    result = []
    for module, limit in MONTHLY_LIMITS.items():
        used = get_used(db_path, module)
        result.append(
            {
                "module": module,
                "used": used,
                "limit": limit,
                "pct": round(100 * used / limit, 1) if limit else 0,
                "warn": limit > 0 and used / limit >= 0.8,
            }
        )
    return result
