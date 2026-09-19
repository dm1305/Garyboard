"""GitHub public profile lookup by username or by commit email search.
Free read-only personal access token, no scopes needed.
"""
import httpx

from app.models import Confidence, Finding, Kind
from app.modules.base import note

name = "github"
timeout_seconds = 10.0
quota_cost = 1


def _headers(ctx: dict) -> dict:
    token = ctx.get("settings").github_token
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


async def run(query: str, ctx: dict) -> list[Finding]:
    is_email = "@" in query
    async with httpx.AsyncClient(headers=_headers(ctx), timeout=timeout_seconds) as client:
        if is_email:
            resp = await client.get(
                "https://api.github.com/search/users", params={"q": f"{query} in:email"}
            )
            host, status = "api.github.com", str(resp.status_code)
            ctx.setdefault("outbound_calls", []).append({"module": name, "host": host, "status": status})
            if resp.status_code != 200:
                return [note(name, f"GitHub search failed ({resp.status_code})")]
            items = resp.json().get("items", [])
            if not items:
                return [note(name, "No GitHub account linked to that email")]
            return [
                Finding(
                    module=name,
                    kind=Kind.PROFILE,
                    title=f"GitHub account: {item['login']}",
                    url=item.get("html_url"),
                    confidence=Confidence.HIGH,
                )
                for item in items[:5]
            ]

        resp = await client.get(f"https://api.github.com/users/{query}")
        ctx.setdefault("outbound_calls", []).append(
            {"module": name, "host": "api.github.com", "status": str(resp.status_code)}
        )
        if resp.status_code == 404:
            return [note(name, f"No GitHub user '{query}'")]
        if resp.status_code != 200:
            return [note(name, f"GitHub lookup failed ({resp.status_code})")]
        data = resp.json()
        return [
            Finding(
                module=name,
                kind=Kind.PROFILE,
                title=f"GitHub: {data.get('login')}" + (f" ({data['name']})" if data.get("name") else ""),
                url=data.get("html_url"),
                confidence=Confidence.HIGH,
                detail={"public_repos": data.get("public_repos"), "created_at": data.get("created_at")},
            )
        ]
