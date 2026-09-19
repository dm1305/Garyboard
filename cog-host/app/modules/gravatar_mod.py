"""Gravatar public profile lookup by SHA-256 of the lowercased, trimmed email."""
import hashlib

import httpx

from app.models import Confidence, Finding, Kind
from app.modules.base import note

name = "gravatar"
timeout_seconds = 8.0
quota_cost = 1


async def run(query: str, ctx: dict) -> list[Finding]:
    email_hash = hashlib.sha256(query.strip().lower().encode("utf-8")).hexdigest()
    key = ctx.get("settings").gravatar_api_key
    headers = {"Authorization": f"Bearer {key}"} if key else {}

    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        resp = await client.get(
            f"https://api.gravatar.com/v3/profiles/{email_hash}", headers=headers
        )
    ctx.setdefault("outbound_calls", []).append(
        {"module": name, "host": "api.gravatar.com", "status": str(resp.status_code)}
    )
    if resp.status_code == 404:
        return [note(name, "No Gravatar profile for that email")]
    if resp.status_code != 200:
        return [note(name, f"Gravatar lookup failed ({resp.status_code})")]

    data = resp.json()
    return [
        Finding(
            module=name,
            kind=Kind.PROFILE,
            title=f"Gravatar profile: {data.get('display_name') or query}",
            url=data.get("profile_url"),
            confidence=Confidence.HIGH,
            detail={"location": data.get("location")},
        )
    ]
