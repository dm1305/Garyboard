"""LinkedIn people search via Tavily, restricted to linkedin.com. Nothing on
the Pi ever fetches linkedin.com directly - only Tavily's search API is
called, and results are shown as unverified search snippets.
"""
import httpx

from app.models import Confidence, Finding, Kind
from app.modules.base import note

name = "tavily"
timeout_seconds = 15.0
quota_cost = 1


async def run(query: str, ctx: dict) -> list[Finding]:
    key = ctx["settings"].tavily_api_key
    if not key:
        return [note(name, "no key")]

    detail = ctx.get("detail", {})
    name_part = detail.get("name", "")
    company_part = detail.get("company", "")
    search_query = f'"{name_part}" "{company_part}"' if company_part else f'"{name_part}"'

    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        resp = await client.post(
            "https://api.tavily.com/search",
            json={
                "api_key": key,
                "query": search_query,
                "include_domains": ["linkedin.com"],
                "max_results": 5,
            },
        )
    ctx.setdefault("outbound_calls", []).append(
        {"module": name, "host": "api.tavily.com", "status": str(resp.status_code)}
    )
    if resp.status_code != 200:
        return [note(name, f"Tavily search failed ({resp.status_code})")]

    results = resp.json().get("results", [])
    if not results:
        return [note(name, "No LinkedIn results from Tavily - try the dork links instead")]

    findings = [
        Finding(
            module=name,
            kind=Kind.PROFILE,
            title=f"{r.get('title', 'LinkedIn result')} (search result, unverified)",
            url=r.get("url"),
            confidence=Confidence.LOW,
            detail={"snippet": r.get("content", "")[:300]},
        )
        for r in results
    ]
    from urllib.parse import quote_plus

    findings.append(
        Finding(
            module="linkedin_search",
            kind=Kind.LINK,
            title="Open LinkedIn people search in your browser",
            url=f"https://www.linkedin.com/search/results/people/?keywords={quote_plus(search_query)}",
            confidence=Confidence.LOW,
        )
    )
    return findings
