import pytest

from app.modules import darkweb_dorks


@pytest.mark.asyncio
async def test_darkweb_dorks_builds_ahmia_link():
    findings = await darkweb_dorks.run("someone@example.com", {})
    assert len(findings) == 1
    assert "ahmia.fi" in findings[0].url
    assert "someone%40example.com" in findings[0].url
    assert "Tor Browser" in findings[0].detail["note"]
