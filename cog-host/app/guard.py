import hashlib
import os
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path

from app.db import get_conn

# Sites filtered out of username/email-registration results by default.
# This is a starting list, not exhaustive - extend it as you find gaps.
SENSITIVE_DOMAINS = {
    "onlyfans.com",
    "pornhub.com",
    "xvideos.com",
    "chaturbate.com",
    "ashleymadison.com",
    "adultfriendfinder.com",
    "fetlife.com",
    "manhunt.net",
    "grindr.com",
}


class Purpose(StrEnum):
    OWN_FOOTPRINT = "own_footprint"
    VERIFY_CONTACT = "verify_contact"
    SCAM_CHECK = "scam_check"
    OTHER = "other"


class RateLimitExceeded(Exception):
    pass


class PurposeRequired(Exception):
    pass


def _get_salt(salt_path: Path) -> bytes:
    if salt_path.exists():
        return salt_path.read_bytes()
    salt = os.urandom(32)
    salt_path.write_bytes(salt)
    try:
        salt_path.chmod(0o600)
    except OSError:
        pass
    return salt


def hash_identifier(value: str, salt_path: Path) -> str:
    salt = _get_salt(salt_path)
    return hashlib.sha256(salt + value.strip().lower().encode("utf-8")).hexdigest()


def check_purpose(purpose: str | None, purpose_note: str | None, confirmed: bool) -> Purpose:
    if not purpose or not confirmed:
        raise PurposeRequired("Select a purpose and confirm the tick box before searching.")
    try:
        parsed = Purpose(purpose)
    except ValueError as exc:
        raise PurposeRequired(f"Unknown purpose: {purpose}") from exc
    if parsed is Purpose.OTHER and not (purpose_note or "").strip():
        raise PurposeRequired("Add a short note when purpose is 'other'.")
    return parsed


def check_rate_limit(db_path: Path, limit_per_hour: int) -> None:
    if limit_per_hour <= 0:
        return
    cutoff = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    with get_conn(db_path) as conn:
        count = conn.execute(
            "SELECT COUNT(*) AS n FROM audit_log WHERE created_at >= ?",
            (cutoff,),
        ).fetchone()["n"]
    if count >= limit_per_hour:
        raise RateLimitExceeded(
            f"Rate limit reached: {limit_per_hour} searches per hour. Try again later."
        )


def record_audit(
    db_path: Path,
    salt_path: Path,
    input_type: str,
    raw_value: str,
    purpose: str,
) -> None:
    identifier_hash = hash_identifier(raw_value, salt_path)
    created_at = datetime.now(UTC).isoformat()
    with get_conn(db_path) as conn:
        conn.execute(
            "INSERT INTO audit_log (input_type, identifier_hash, purpose, created_at) VALUES (?, ?, ?, ?)",
            (input_type, identifier_hash, purpose, created_at),
        )


def is_sensitive_url(url: str | None) -> bool:
    if not url:
        return False
    lowered = url.lower()
    return any(domain in lowered for domain in SENSITIVE_DOMAINS)


def apply_sensitive_filter(findings: list, show_sensitive: bool) -> list:
    """Mark sensitive findings and drop them unless show_sensitive is set."""
    result = []
    for finding in findings:
        if is_sensitive_url(finding.url):
            finding.sensitive = True
        if finding.sensitive and not show_sensitive:
            continue
        result.append(finding)
    return result
