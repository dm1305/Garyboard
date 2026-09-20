import pytest

from app.modules import emailrep_mod, hunter_mod, veriphone_mod


class FakeSettings:
    emailrep_api_key = ""
    hunter_api_key = ""
    veriphone_api_key = ""


@pytest.mark.asyncio
async def test_keyed_modules_skip_cleanly_without_key():
    ctx = {"settings": FakeSettings()}
    for mod in (emailrep_mod, hunter_mod, veriphone_mod):
        findings = await mod.run("someone@example.com", ctx)
        assert len(findings) == 1
        assert "no key" in findings[0].title


@pytest.mark.asyncio
async def test_hunter_skips_without_quota_opt_in():
    class Settings(FakeSettings):
        hunter_api_key = "fake-key"

    ctx = {"settings": Settings(), "use_limited_quota": False}
    findings = await hunter_mod.run("someone@example.com", ctx)
    assert len(findings) == 1
    assert "not enabled" in findings[0].title
