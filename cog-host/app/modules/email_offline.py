"""Offline-first email checks: syntax was already validated by detect.py.
This module does MX lookup, a disposable-domain check, and RDAP domain age.
MX and RDAP are network calls but hit only public DNS/registry infrastructure,
not any third-party OSINT service.
"""
from datetime import datetime, timezone

import dns.exception
import dns.resolver
import httpx

from app.models import Confidence, Finding, Kind

name = "email_offline"
timeout_seconds = 10.0
quota_cost = 0

# A small, illustrative starting list - not exhaustive.
DISPOSABLE_DOMAINS = {
    "mailinator.com",
    "10minutemail.com",
    "guerrillamail.com",
    "temp-mail.org",
    "yopmail.com",
    "trashmail.com",
}

DOMAIN_AGE_WARN_DAYS = 90


async def _mx_lookup(domain: str) -> list[str]:
    try:
        answers = await _resolve_mx(domain)
        return [str(r.exchange).rstrip(".") for r in answers]
    except (dns.exception.DNSException, OSError):
        return []


async def _resolve_mx(domain: str):
    import asyncio

    loop = asyncio.get_running_loop()
    resolver = dns.resolver.Resolver()
    return await loop.run_in_executor(None, lambda: resolver.resolve(domain, "MX"))


async def _domain_age_days(domain: str, client: httpx.AsyncClient) -> int | None:
    try:
        resp = await client.get(f"https://rdap.org/domain/{domain}", timeout=8.0)
        if resp.status_code != 200:
            return None
        data = resp.json()
    except (httpx.HTTPError, ValueError):
        return None

    for event in data.get("events", []):
        if event.get("eventAction") == "registration":
            try:
                registered = datetime.fromisoformat(event["eventDate"].replace("Z", "+00:00"))
            except (KeyError, ValueError):
                return None
            return (datetime.now(timezone.utc) - registered).days
    return None


async def run(query: str, ctx: dict) -> list[Finding]:
    domain = query.rsplit("@", 1)[-1].lower()
    findings: list[Finding] = []

    if domain in DISPOSABLE_DOMAINS:
        findings.append(
            Finding(
                module=name,
                kind=Kind.NOTE,
                title=f"{domain} is a known disposable-email domain",
                confidence=Confidence.HIGH,
            )
        )

    mx_hosts = await _mx_lookup(domain)
    findings.append(
        Finding(
            module=name,
            kind=Kind.NOTE,
            title=(
                f"MX records found for {domain}" if mx_hosts else f"No MX records for {domain}"
            ),
            confidence=Confidence.HIGH,
            detail={"mx_hosts": mx_hosts},
        )
    )

    async with httpx.AsyncClient() as client:
        age_days = await _domain_age_days(domain, client)
    ctx.setdefault("outbound_calls", []).append(
        {"module": name, "host": "rdap.org", "status": "ok" if age_days is not None else "unknown"}
    )
    if age_days is not None:
        title = f"Domain {domain} registered {age_days} days ago"
        if age_days < DOMAIN_AGE_WARN_DAYS:
            title += " (recently registered - treat with caution, not as proof of anything)"
        findings.append(
            Finding(
                module=name,
                kind=Kind.NOTE,
                title=title,
                confidence=Confidence.MEDIUM,
                detail={"age_days": age_days},
            )
        )
    else:
        findings.append(
            Finding(
                module=name,
                kind=Kind.NOTE,
                title=f"Domain age for {domain} unknown (RDAP coverage varies by TLD)",
                confidence=Confidence.LOW,
            )
        )

    return findings
