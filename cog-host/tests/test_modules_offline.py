import httpx
import pytest
import respx

from app.modules import dorks, email_offline, phone_offline


@pytest.mark.asyncio
async def test_dorks_builds_three_engine_links():
    findings = await dorks.run("someone@example.com", {})
    assert len(findings) == 3
    engines = {f.detail["engine"] for f in findings}
    assert engines == {"Google", "Bing", "DuckDuckGo"}
    for f in findings:
        assert "someone%40example.com" in f.url or "someone" in f.url


@pytest.mark.asyncio
async def test_phone_offline_flags_landline_no_whatsapp():
    # A UK landline number (not mobile)
    findings = await phone_offline.run("+442071234567", {})
    titles = [f.title for f in findings]
    assert any("cannot have WhatsApp" in t for t in titles)
    assert not any(f.module == "whatsapp" for f in findings)


@pytest.mark.asyncio
async def test_phone_offline_mobile_gets_whatsapp_link():
    findings = await phone_offline.run("+447911123456", {})
    wa = [f for f in findings if f.module == "whatsapp"]
    assert len(wa) == 1
    assert wa[0].url == "https://wa.me/447911123456"


@pytest.mark.asyncio
@respx.mock
async def test_email_offline_detects_disposable_domain():
    respx.get(url__regex=r"https://rdap\.org/.*").mock(
        return_value=httpx.Response(404)
    )
    findings = await email_offline.run("user@mailinator.com", {})
    titles = [f.title for f in findings]
    assert any("disposable-email domain" in t for t in titles)


@pytest.mark.asyncio
@respx.mock
async def test_email_offline_reports_domain_age():
    respx.get(url__regex=r"https://rdap\.org/.*").mock(
        return_value=httpx.Response(
            200,
            json={"events": [{"eventAction": "registration", "eventDate": "2020-01-01T00:00:00Z"}]},
        )
    )
    findings = await email_offline.run("user@example.com", {})
    titles = [f.title for f in findings]
    assert any("registered" in t and "days ago" in t for t in titles)


@pytest.mark.asyncio
@respx.mock
async def test_email_offline_handles_rdap_failure_gracefully():
    respx.get(url__regex=r"https://rdap\.org/.*").mock(side_effect=httpx.ConnectError("boom"))
    findings = await email_offline.run("user@example.com", {})
    titles = [f.title for f in findings]
    assert any("unknown" in t for t in titles)
