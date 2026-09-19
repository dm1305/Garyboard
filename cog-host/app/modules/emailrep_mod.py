import httpx

from app.models import Confidence, Finding, Kind
from app.modules.base import note

name = "emailrep"
timeout_seconds = 8.0
quota_cost = 1


async def run(query: str, ctx: dict) -> list[Finding]:
    key = ctx.get("settings").emailrep_api_key
    if not key:
        return [note(name, "no key")]

    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        resp = await client.get(
            f"https://emailrep.io/{query}", headers={"Key": key}
        )
    ctx.setdefault("outbound_calls", []).append(
        {"module": name, "host": "emailrep.io", "status": str(resp.status_code)}
    )
    if resp.status_code != 200:
        return [note(name, f"EmailRep lookup failed ({resp.status_code})")]

    data = resp.json()
    reputation = data.get("reputation", "unknown")
    suspicious = data.get("suspicious", False)
    title = f"EmailRep reputation: {reputation}" + (" (flagged suspicious)" if suspicious else "")
    findings = [
        Finding(
            module=name,
            kind=Kind.REPUTATION,
            title=title,
            confidence=Confidence.MEDIUM,
            detail={
                "reputation": reputation,
                "suspicious": suspicious,
                "details": data.get("details", {}),
            },
        )
    ]
    profiles = data.get("details", {}).get("profiles", [])
    for site in profiles:
        findings.append(
            Finding(
                module=name,
                kind=Kind.PROFILE,
                title=f"Linked profile hint: {site}",
                confidence=Confidence.LOW,
            )
        )
    return findings
