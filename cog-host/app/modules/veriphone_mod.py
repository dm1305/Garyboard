import httpx

from app.models import Confidence, Finding, Kind
from app.modules.base import note

name = "veriphone"
timeout_seconds = 8.0
quota_cost = 1


async def run(query: str, ctx: dict) -> list[Finding]:
    key = ctx.get("settings").veriphone_api_key
    if not key:
        return [note(name, "no key")]

    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        resp = await client.get(
            "https://api.veriphone.io/v2/verify", params={"phone": query, "key": key}
        )
    ctx.setdefault("outbound_calls", []).append(
        {"module": name, "host": "api.veriphone.io", "status": str(resp.status_code)}
    )
    if resp.status_code != 200:
        return [note(name, f"Veriphone lookup failed ({resp.status_code})")]

    data = resp.json()
    if not data.get("phone_valid"):
        return [note(name, "Veriphone: number not valid")]
    return [
        Finding(
            module=name,
            kind=Kind.LINE_INFO,
            title=f"Veriphone: {data.get('phone_type', 'unknown type')}, {data.get('carrier', 'unknown carrier')}",
            confidence=Confidence.HIGH,
            detail={
                "country": data.get("country"),
                "phone_type": data.get("phone_type"),
                "carrier": data.get("carrier"),
            },
        )
    ]
