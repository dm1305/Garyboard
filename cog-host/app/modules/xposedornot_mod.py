"""XposedOrNot breach-name lookup. No key required, roughly 1 request/second."""
import httpx

from app.models import Confidence, Finding, Kind
from app.modules.base import note

name = "xposedornot"
timeout_seconds = 8.0
quota_cost = 0


async def run(query: str, ctx: dict) -> list[Finding]:
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        resp = await client.get(f"https://api.xposedornot.com/v1/check-email/{query}")
    ctx.setdefault("outbound_calls", []).append(
        {"module": name, "host": "api.xposedornot.com", "status": str(resp.status_code)}
    )
    if resp.status_code == 404:
        return [note(name, "No breaches found")]
    if resp.status_code != 200:
        return [note(name, f"XposedOrNot lookup failed ({resp.status_code})")]

    data = resp.json()
    breaches = data.get("breaches", [])
    nested = bool(breaches) and isinstance(breaches[0], list)
    flat = [b for group in breaches for b in group] if nested else breaches
    if not flat:
        return [note(name, "No breaches found")]
    return [
        Finding(
            module=name,
            kind=Kind.BREACH,
            title=f"Listed in breach: {breach_name}",
            confidence=Confidence.HIGH,
        )
        for breach_name in flat
    ]
