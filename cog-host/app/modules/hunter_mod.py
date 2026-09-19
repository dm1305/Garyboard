"""Hunter email verification. Costs credits (50/month shared across Hunter's
finder, domain search and verifier), so it only runs when the caller opts in
via ctx["use_limited_quota"].
"""
import httpx

from app.models import Confidence, Finding, Kind
from app.modules.base import note

name = "hunter"
timeout_seconds = 8.0
quota_cost = 1


async def run(query: str, ctx: dict) -> list[Finding]:
    key = ctx.get("settings").hunter_api_key
    if not key:
        return [note(name, "no key")]
    if not ctx.get("use_limited_quota"):
        return [note(name, "skipped: limited-quota checks not enabled for this search")]

    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        resp = await client.get(
            "https://api.hunter.io/v2/email-verifier",
            params={"email": query, "api_key": key},
        )
    ctx.setdefault("outbound_calls", []).append(
        {"module": name, "host": "api.hunter.io", "status": str(resp.status_code)}
    )
    if resp.status_code != 200:
        return [note(name, f"Hunter verification failed ({resp.status_code})")]

    data = resp.json().get("data", {})
    status = data.get("status", "unknown")
    score = data.get("score")
    return [
        Finding(
            module=name,
            kind=Kind.REPUTATION,
            title=f"Hunter verification: {status}" + (f" (score {score})" if score is not None else ""),
            confidence=Confidence.MEDIUM,
            detail={"status": status, "score": score, "disposable": data.get("disposable")},
        )
    ]
