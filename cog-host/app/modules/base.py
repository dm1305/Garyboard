from typing import Protocol

from app.models import Finding


class Module(Protocol):
    name: str
    timeout_seconds: float
    quota_cost: int

    async def run(self, query: str, ctx: dict) -> list[Finding]:
        ...


def note(module: str, message: str) -> Finding:
    from app.models import Confidence, Kind

    return Finding(module=module, kind=Kind.NOTE, title=message, confidence=Confidence.LOW)
