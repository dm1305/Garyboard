import pytest

from app.guard import (
    PurposeRequired,
    RateLimitExceeded,
    apply_sensitive_filter,
    check_purpose,
    check_rate_limit,
    hash_identifier,
    is_sensitive_url,
    record_audit,
)
from app.models import Confidence, Finding, Kind


def test_check_purpose_requires_confirmation():
    with pytest.raises(PurposeRequired):
        check_purpose("own_footprint", None, confirmed=False)


def test_check_purpose_requires_known_value():
    with pytest.raises(PurposeRequired):
        check_purpose("not_a_real_purpose", None, confirmed=True)


def test_check_purpose_other_requires_note():
    with pytest.raises(PurposeRequired):
        check_purpose("other", "", confirmed=True)
    check_purpose("other", "checking a scam text", confirmed=True)


def test_check_purpose_accepts_valid():
    result = check_purpose("scam_check", None, confirmed=True)
    assert result.value == "scam_check"


def test_hash_identifier_is_stable_and_salted(salt_path):
    h1 = hash_identifier("test@example.com", salt_path)
    h2 = hash_identifier("test@example.com", salt_path)
    assert h1 == h2
    assert h1 != "test@example.com"


def test_hash_identifier_differs_by_salt(tmp_path):
    h1 = hash_identifier("test@example.com", tmp_path / "salt1")
    h2 = hash_identifier("test@example.com", tmp_path / "salt2")
    assert h1 != h2


def test_record_audit_stores_hash_not_raw_value(db_path, salt_path):
    record_audit(db_path, salt_path, "email", "secret@example.com", "own_footprint")
    import sqlite3

    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT identifier_hash FROM audit_log").fetchone()
    assert row is not None
    assert "secret@example.com" not in row[0]


def test_rate_limit_blocks_after_threshold(db_path, salt_path):
    for _ in range(3):
        record_audit(db_path, salt_path, "email", "a@example.com", "own_footprint")
    check_rate_limit(db_path, limit_per_hour=5)  # should not raise
    with pytest.raises(RateLimitExceeded):
        check_rate_limit(db_path, limit_per_hour=3)


def test_rate_limit_zero_means_unlimited(db_path, salt_path):
    for _ in range(10):
        record_audit(db_path, salt_path, "email", "a@example.com", "own_footprint")
    check_rate_limit(db_path, limit_per_hour=0)


def test_is_sensitive_url():
    assert is_sensitive_url("https://onlyfans.com/someone")
    assert not is_sensitive_url("https://github.com/someone")
    assert not is_sensitive_url(None)


def test_apply_sensitive_filter_hides_by_default():
    findings = [
        Finding(module="m", kind=Kind.ACCOUNT, title="a", confidence=Confidence.MEDIUM, url="https://onlyfans.com/x"),
        Finding(module="m", kind=Kind.ACCOUNT, title="b", confidence=Confidence.MEDIUM, url="https://github.com/x"),
    ]
    visible = apply_sensitive_filter(findings, show_sensitive=False)
    assert [f.title for f in visible] == ["b"]


def test_apply_sensitive_filter_can_be_shown():
    findings = [
        Finding(module="m", kind=Kind.ACCOUNT, title="a", confidence=Confidence.MEDIUM, url="https://onlyfans.com/x"),
    ]
    visible = apply_sensitive_filter(findings, show_sensitive=True)
    assert len(visible) == 1
    assert visible[0].sensitive is True
