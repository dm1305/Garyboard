import pytest

from app.db import init_db


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "test.db"
    init_db(path)
    return path


@pytest.fixture
def salt_path(tmp_path):
    return tmp_path / ".audit_salt"
