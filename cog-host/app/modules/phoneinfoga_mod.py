"""PhoneInfoga v2 local-service adapter. Calls only the key-free scanners:
local, ovh, googlesearch. Requires `phoneinfoga serve --no-client -p 5000`
running on 127.0.0.1 (see docs/PHONEINFOGA.md).
"""
import httpx

from app.models import Confidence, Finding, Kind
from app.modules.base import note

name = "phoneinfoga"
timeout_seconds = 20.0
quota_cost = 0

SCANNERS = ["local", "ovh", "googlesearch"]


async def run(query: str, ctx: dict) -> list[Finding]:
    base_url = ctx.get("settings").phoneinfoga_url
    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            resp = await client.get(
                f"{base_url}/api/v2/scan",
                params={"number": query, "scanners": ",".join(SCANNERS)},
            )
    except httpx.ConnectError:
        return [note(name, f"PhoneInfoga not reachable at {base_url} (is the service running?)")]

    ctx.setdefault("outbound_calls", []).append(
        {"module": name, "host": base_url, "status": str(resp.status_code)}
    )
    if resp.status_code != 200:
        return [note(name, f"PhoneInfoga scan failed ({resp.status_code})")]

    data = resp.json()
    findings = []
    for result in data.get("results", []):
        for link in result.get("links", []) if isinstance(result, dict) else []:
            findings.append(
                Finding(
                    module=name,
                    kind=Kind.LINK,
                    title=f"PhoneInfoga ({result.get('scanner', 'scanner')}) result",
                    url=link,
                    confidence=Confidence.LOW,
                )
            )
    return findings or [note(name, "PhoneInfoga found no results")]
