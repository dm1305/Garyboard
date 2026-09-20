import asyncio
import time

from app.cache import ModuleCache
from app.config import Settings
from app.db import get_conn
from app.models import Confidence, Finding, InputType, Kind
from app.modules import (
    darkweb_dorks,
    domain_checks,
    dorks,
    email_offline,
    emailrep_mod,
    github_mod,
    gravatar_mod,
    holehe_mod,
    hunter_mod,
    maigret_mod,
    phone_offline,
    phoneinfoga_mod,
    sherlock_mod,
    tavily_mod,
    veriphone_mod,
    xposedornot_mod,
)

MODULES_BY_TYPE = {
    InputType.EMAIL: [
        email_offline,
        domain_checks,
        gravatar_mod,
        emailrep_mod,
        xposedornot_mod,
        github_mod,
        hunter_mod,
        holehe_mod,
        dorks,
        darkweb_dorks,
    ],
    InputType.PHONE: [phone_offline, veriphone_mod, phoneinfoga_mod, dorks, darkweb_dorks],
    InputType.USERNAME: [sherlock_mod, maigret_mod, github_mod, dorks, darkweb_dorks],
    InputType.NAME_COMPANY: [tavily_mod, dorks, darkweb_dorks],
    InputType.URL: [dorks, darkweb_dorks],
}


class ModuleProgress:
    def __init__(self, modules: list) -> None:
        self.status = {m.name: "pending" for m in modules}


async def _run_one(module, query: str, ctx: dict, cache: ModuleCache, quota_increment) -> list[Finding]:
    cached = cache.get(module.name, query)
    if cached is not None:
        return cached

    started = time.monotonic()
    try:
        findings = await asyncio.wait_for(module.run(query, ctx), timeout=module.timeout_seconds)
        quota_increment(module.name, getattr(module, "quota_cost", 0))
        cache.set(module.name, query, findings)
        return findings
    except TimeoutError:
        err = [
            Finding(
                module=module.name,
                kind=Kind.NOTE,
                title=f"{module.name} timed out after {module.timeout_seconds:.0f}s",
                confidence=Confidence.LOW,
            )
        ]
        cache.set(module.name, query, err, is_error=True)
        return err
    except Exception as exc:  # noqa: BLE001 - modules must never crash the search
        err = [
            Finding(
                module=module.name,
                kind=Kind.NOTE,
                title=f"{module.name} error: {exc}",
                confidence=Confidence.LOW,
            )
        ]
        cache.set(module.name, query, err, is_error=True)
        return err
    finally:
        ctx.setdefault("timings", {})[module.name] = round(time.monotonic() - started, 2)


_CONFIDENCE_RANK = {Confidence.HIGH: 3, Confidence.MEDIUM: 2, Confidence.LOW: 1}


def _dedupe_findings(findings: list[Finding]) -> list[Finding]:
    """Merge findings that share a URL (e.g. the same GitHub profile found by
    both the keyed API and Sherlock), keeping the highest-confidence one and
    noting which other modules also found it."""
    kept_by_url: dict[str, Finding] = {}
    modules_by_url: dict[str, list[str]] = {}
    deduped: list[Finding] = []

    for finding in findings:
        if not finding.url:
            deduped.append(finding)
            continue

        modules = modules_by_url.setdefault(finding.url, [])
        if finding.module not in modules:
            modules.append(finding.module)

        current_best = kept_by_url.get(finding.url)
        if current_best is None or _CONFIDENCE_RANK[finding.confidence] > _CONFIDENCE_RANK[
            current_best.confidence
        ]:
            kept_by_url[finding.url] = finding
            if current_best is not None:
                deduped.remove(current_best)
            deduped.append(finding)

    for url, modules in modules_by_url.items():
        if len(modules) > 1:
            kept_by_url[url].detail = {**kept_by_url[url].detail, "also_found_by": modules}

    return deduped


async def run_search(
    input_type: InputType,
    query: str,
    settings: Settings,
    cache: ModuleCache,
    extra_detail: dict | None = None,
    use_limited_quota: bool = False,
    holehe_confirmed: bool = False,
) -> list[Finding]:
    modules = MODULES_BY_TYPE.get(input_type, [dorks])

    def quota_increment(module_name: str, cost: int) -> None:
        if cost:
            from app.quota import increment

            increment(settings.db_path, module_name, cost)

    outbound_calls: list[dict] = []
    ctx = {
        "settings": settings,
        "detail": extra_detail or {},
        "use_limited_quota": use_limited_quota,
        "holehe_confirmed": holehe_confirmed,
        "outbound_calls": outbound_calls,
    }

    results = await asyncio.gather(
        *(_run_one(m, query, ctx, cache, quota_increment) for m in modules)
    )

    with get_conn(settings.db_path) as conn:
        for call in outbound_calls:
            conn.execute(
                "INSERT INTO outbound_log (module, host, status) VALUES (?, ?, ?)",
                (call["module"], call["host"], call["status"]),
            )

    all_findings: list[Finding] = [f for group in results for f in group]
    return _dedupe_findings(all_findings)
