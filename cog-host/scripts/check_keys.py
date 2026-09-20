#!/usr/bin/env python3
"""Makes one minimal call per keyed service and prints OK, FAIL or MISSING.
Never prints a key. Run after Phase 3 to confirm your .env is wired up:

    .venv/bin/python scripts/check_keys.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx

from app.config import settings


async def check_hunter() -> str:
    if not settings.hunter_api_key:
        return "MISSING"
    async with httpx.AsyncClient(timeout=8.0) as client:
        resp = await client.get(
            "https://api.hunter.io/v2/account", params={"api_key": settings.hunter_api_key}
        )
    return "OK" if resp.status_code == 200 else "FAIL"


async def check_emailrep() -> str:
    if not settings.emailrep_api_key:
        return "MISSING"
    async with httpx.AsyncClient(timeout=8.0) as client:
        resp = await client.get(
            "https://emailrep.io/ping", headers={"Key": settings.emailrep_api_key}
        )
    return "OK" if resp.status_code in (200, 404) else "FAIL"


async def check_veriphone() -> str:
    if not settings.veriphone_api_key:
        return "MISSING"
    async with httpx.AsyncClient(timeout=8.0) as client:
        resp = await client.get(
            "https://api.veriphone.io/v2/verify",
            params={"phone": "+14155552671", "key": settings.veriphone_api_key},
        )
    return "OK" if resp.status_code == 200 else "FAIL"


async def check_tavily() -> str:
    if not settings.tavily_api_key:
        return "MISSING"
    async with httpx.AsyncClient(timeout=8.0) as client:
        resp = await client.post(
            "https://api.tavily.com/search",
            json={"api_key": settings.tavily_api_key, "query": "test", "max_results": 1},
        )
    return "OK" if resp.status_code == 200 else "FAIL"


async def check_gravatar() -> str:
    if not settings.gravatar_api_key:
        return "MISSING (optional - works unauthenticated at lower rate limit)"
    async with httpx.AsyncClient(timeout=8.0) as client:
        resp = await client.get(
            "https://api.gravatar.com/v3/profiles/0000000000000000000000000000000000000000000000000000000000000000",
            headers={"Authorization": f"Bearer {settings.gravatar_api_key}"},
        )
    return "OK" if resp.status_code in (200, 404) else "FAIL"


async def check_github() -> str:
    if not settings.github_token:
        return "MISSING (optional - works unauthenticated at lower rate limit)"
    async with httpx.AsyncClient(timeout=8.0) as client:
        resp = await client.get(
            "https://api.github.com/user",
            headers={"Authorization": f"Bearer {settings.github_token}"},
        )
    return "OK" if resp.status_code == 200 else "FAIL"


async def check_xposedornot() -> str:
    async with httpx.AsyncClient(timeout=8.0) as client:
        resp = await client.get("https://api.xposedornot.com/v1/check-email/test@example.com")
    return "OK" if resp.status_code in (200, 404) else "FAIL"


CHECKS = {
    "Hunter": check_hunter,
    "EmailRep": check_emailrep,
    "Veriphone": check_veriphone,
    "Tavily": check_tavily,
    "Gravatar": check_gravatar,
    "GitHub": check_github,
    "XposedOrNot (no key needed)": check_xposedornot,
}


async def main() -> int:
    failures = 0
    for label, check in CHECKS.items():
        try:
            result = await check()
        except httpx.HTTPError as exc:
            result = f"FAIL ({type(exc).__name__})"
        if result.startswith("FAIL"):
            failures += 1
        print(f"{label:<28} {result}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
