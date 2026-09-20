"""Keyless fallback: prefilled search-engine links the user clicks themselves.
No requests are made from the Pi - these are just links.
"""
from urllib.parse import quote_plus

from app.models import Confidence, Finding, Kind

name = "dorks"
timeout_seconds = 1.0
quota_cost = 0

ENGINES = {
    "Google": "https://www.google.com/search?q={q}",
    "Bing": "https://www.bing.com/search?q={q}",
    "DuckDuckGo": "https://duckduckgo.com/?q={q}",
}


async def run(query: str, ctx: dict) -> list[Finding]:
    quoted = quote_plus(f'"{query}"')
    findings = []
    for engine, template in ENGINES.items():
        findings.append(
            Finding(
                module=name,
                kind=Kind.LINK,
                title=f"Search {engine} for \"{query}\"",
                url=template.format(q=quoted),
                confidence=Confidence.LOW,
                detail={"engine": engine},
            )
        )
    return findings
