import httpx
import pytest
import respx

from app.modules import domain_checks


@pytest.mark.asyncio
@respx.mock
async def test_domain_checks_detects_spf_and_dmarc(monkeypatch):
    async def fake_txt(domain):
        if domain == "example.com":
            return ["v=spf1 include:_spf.example.com ~all"]
        if domain == "_dmarc.example.com":
            return ["v=DMARC1; p=reject"]
        return []

    monkeypatch.setattr(domain_checks, "_txt_records", fake_txt)
    respx.get(url__regex=r"https://rdap\.org/.*").mock(return_value=httpx.Response(404))

    findings = await domain_checks.run("user@example.com", {})
    titles = [f.title for f in findings]
    assert any("SPF record found" in t for t in titles)
    assert any("DMARC record found" in t for t in titles)


@pytest.mark.asyncio
@respx.mock
async def test_domain_checks_flags_missing_records(monkeypatch):
    async def fake_txt(domain):
        return []

    monkeypatch.setattr(domain_checks, "_txt_records", fake_txt)
    respx.get(url__regex=r"https://rdap\.org/.*").mock(return_value=httpx.Response(404))

    findings = await domain_checks.run("user@example.com", {})
    titles = [f.title for f in findings]
    assert any("No SPF record" in t for t in titles)
    assert any("No DMARC record" in t for t in titles)


@pytest.mark.asyncio
@respx.mock
async def test_domain_checks_extracts_registrar(monkeypatch):
    async def fake_txt(domain):
        return []

    monkeypatch.setattr(domain_checks, "_txt_records", fake_txt)
    respx.get(url__regex=r"https://rdap\.org/.*").mock(
        return_value=httpx.Response(
            200,
            json={
                "entities": [
                    {
                        "roles": ["registrar"],
                        "vcardArray": [
                            "vcard",
                            [["version", {}, "text", "4.0"], ["fn", {}, "text", "Example Registrar Inc"]],
                        ],
                    }
                ]
            },
        )
    )

    findings = await domain_checks.run("user@example.com", {})
    titles = [f.title for f in findings]
    assert any("Example Registrar Inc" in t for t in titles)
