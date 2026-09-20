"""Keyless dark-web search link, same pattern as dorks.py: a prefilled
Ahmia (https://ahmia.fi) search URL the user opens themselves. Ahmia's own
search page is on the clearnet, but the .onion results it lists need Tor
Browser to open - nothing here fetches any .onion address, and no leaked-
credential contents are shown, only a link the user follows at their own
discretion (per PLAN.md's guardrail: breach/leak data stays out of scope
beyond breach *names*, and this module never touches leak content at all).
"""
from urllib.parse import quote_plus

from app.models import Confidence, Finding, Kind

name = "darkweb_dorks"
timeout_seconds = 1.0
quota_cost = 0

AHMIA_URL = "https://ahmia.fi/search/?q={q}"


async def run(query: str, ctx: dict) -> list[Finding]:
    quoted = quote_plus(f'"{query}"')
    return [
        Finding(
            module=name,
            kind=Kind.LINK,
            title=f'Search Ahmia (dark web) for "{query}"',
            url=AHMIA_URL.format(q=quoted),
            confidence=Confidence.LOW,
            detail={
                "engine": "Ahmia",
                "note": (
                    "Ahmia's search page itself is on the clearnet, but its .onion "
                    "results need Tor Browser to open. Nothing here is fetched "
                    "automatically - open results at your own discretion."
                ),
            },
        )
    ]
