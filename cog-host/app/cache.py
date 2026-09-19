import time
from dataclasses import dataclass
from threading import Lock

from app.models import Finding

CACHE_TTL_SECONDS = 24 * 60 * 60
ERROR_TTL_SECONDS = 5 * 60


@dataclass
class _Entry:
    findings: list[Finding]
    expires_at: float
    is_error: bool


class ModuleCache:
    """In-memory cache keyed by (module, normalised input). Cleared on restart."""

    def __init__(self) -> None:
        self._store: dict[tuple[str, str], _Entry] = {}
        self._lock = Lock()

    def get(self, module: str, query: str) -> list[Finding] | None:
        with self._lock:
            entry = self._store.get((module, query))
            if entry is None:
                return None
            if entry.expires_at < time.monotonic():
                del self._store[(module, query)]
                return None
            for finding in entry.findings:
                finding.cached = True
            return entry.findings

    def set(self, module: str, query: str, findings: list[Finding], is_error: bool = False) -> None:
        ttl = ERROR_TTL_SECONDS if is_error else CACHE_TTL_SECONDS
        with self._lock:
            self._store[(module, query)] = _Entry(
                findings=findings, expires_at=time.monotonic() + ttl, is_error=is_error
            )
