import pytest

from app.modules import holehe_mod, maigret_mod, sherlock_mod


class FakeSettings:
    enable_holehe = False


@pytest.mark.asyncio
async def test_sherlock_skips_cleanly_when_not_installed(monkeypatch):
    monkeypatch.setattr(sherlock_mod.shutil, "which", lambda name: None)
    findings = await sherlock_mod.run("bob", {})
    assert "not installed" in findings[0].title


@pytest.mark.asyncio
async def test_maigret_skips_cleanly_when_not_installed(monkeypatch):
    monkeypatch.setattr(maigret_mod.shutil, "which", lambda name: None)
    findings = await maigret_mod.run("bob", {})
    assert "not installed" in findings[0].title


@pytest.mark.asyncio
async def test_holehe_disabled_by_default():
    findings = await holehe_mod.run("bob@example.com", {"settings": FakeSettings()})
    assert "disabled" in findings[0].title


@pytest.mark.asyncio
async def test_holehe_requires_confirmation_even_when_enabled():
    class Enabled(FakeSettings):
        enable_holehe = True

    findings = await holehe_mod.run(
        "bob@example.com", {"settings": Enabled(), "holehe_confirmed": False}
    )
    assert "not confirmed" in findings[0].title
