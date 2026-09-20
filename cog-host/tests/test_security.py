import pytest

from app.config import Settings, validate_startup


def test_lan_bind_without_password_hash_refuses_to_start():
    s = Settings(_env_file=None, bind_lan=True, auth_password_hash="")
    with pytest.raises(RuntimeError, match="AUTH_PASSWORD_HASH"):
        validate_startup(s)


def test_lan_bind_with_password_hash_is_allowed():
    s = Settings(_env_file=None, bind_lan=True, auth_password_hash="fakehash")
    validate_startup(s)  # should not raise


def test_localhost_only_by_default():
    s = Settings(_env_file=None)
    assert s.bind_lan is False
