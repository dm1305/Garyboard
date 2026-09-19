"""Company-domain checks for recruiter/contact verification (PLAN.md stretch
goal 5): SPF and DMARC records, plus the registrar name from RDAP. All are
public DNS/registry lookups, not a third-party OSINT service.

DKIM is deliberately not checked: its public key lives at
`<selector>._domainkey.<domain>`, and the selector is chosen by whichever
mail provider the domain uses - there is no way to guess it without more
information, so a "no DKIM found" result here would be misleading rather
than informative.
"""
import asyncio

import dns.exception
import dns.resolver
import httpx

from app.models import Confidence, Finding, Kind

name = "domain_checks"
timeout_seconds = 10.0
quota_cost = 0


async def _txt_records(domain: str) -> list[str]:
    try:
        loop = asyncio.get_running_loop()
        resolver = dns.resolver.Resolver()
        answers = await loop.run_in_executor(None, lambda: resolver.resolve(domain, "TXT"))
        return ["".join(part.decode("utf-8", "replace") for part in r.strings) for r in answers]
    except (dns.exception.DNSException, OSError):
        return []


async def _registrar(domain: str, client: httpx.AsyncClient) -> str | None:
    try:
        resp = await client.get(f"https://rdap.org/domain/{domain}", timeout=8.0)
        if resp.status_code != 200:
            return None
        data = resp.json()
    except (httpx.HTTPError, ValueError):
        return None

    for entity in data.get("entities", []):
        if "registrar" not in entity.get("roles", []):
            continue
        for vcard_item in entity.get("vcardArray", [[], []])[1]:
            if vcard_item[0] == "fn":
                return vcard_item[3]
    return None


async def run(query: str, ctx: dict) -> list[Finding]:
    domain = query.rsplit("@", 1)[-1].lower()
    findings: list[Finding] = []

    spf_records = [r for r in await _txt_records(domain) if r.lower().startswith("v=spf1")]
    findings.append(
        Finding(
            module=name,
            kind=Kind.NOTE,
            title=f"SPF record found for {domain}" if spf_records else f"No SPF record for {domain}",
            confidence=Confidence.HIGH,
            detail={"spf": spf_records[0] if spf_records else None},
        )
    )

    dmarc_records = [
        r for r in await _txt_records(f"_dmarc.{domain}") if r.lower().startswith("v=dmarc1")
    ]
    findings.append(
        Finding(
            module=name,
            kind=Kind.NOTE,
            title=(
                f"DMARC record found for {domain}"
                if dmarc_records
                else f"No DMARC record for {domain} (spoofed email is easier without one)"
            ),
            confidence=Confidence.HIGH,
            detail={"dmarc": dmarc_records[0] if dmarc_records else None},
        )
    )

    async with httpx.AsyncClient() as client:
        registrar = await _registrar(domain, client)
    ctx.setdefault("outbound_calls", []).append(
        {"module": name, "host": "rdap.org", "status": "ok" if registrar else "unknown"}
    )
    if registrar:
        findings.append(
            Finding(
                module=name,
                kind=Kind.NOTE,
                title=f"Registrar: {registrar}",
                confidence=Confidence.MEDIUM,
            )
        )

    return findings
