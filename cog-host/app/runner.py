import asyncio
import time

from app.cache import ModuleCache
from app.config import Settings
from app.db import get_conn
from app.models import Confidence, Finding, InputType, Kind
from app.modules import (
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
        gravatar_mod,
        emailrep_mod,
        xposedornot_mod,
        github_mod,
        hunter_mod,
        holehe_mod,
        dorks,
    ],
    InputType.PHONE: [phone_offline, veriphone_mod, phoneinfoga_mod, dorks],
    InputType.USERNAME: [sherlock_mod, maigret_mod, github_mod, dorks],
    InputType.NAME_COMPANY: [tavily_mod, dorks],
    InputType.URL: [dorks],
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
    except asyncio.TimeoutError:
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

    ctx = {
        "settings": settings,
        "detail": extra_detail or {},
        "use_limited_quota": use_limited_quota,
        "holehe_confirmed": holehe_confirmed,
        "outbound_calls": [],
    }

    results = await asyncio.gather(
        *(_run_one(m, query, ctx, cache, quota_increment) for m in modules)
    )

    with get_conn(settings.db_path) as conn:
        for call in ctx["outbound_calls"]:
            conn.execute(
                "INSERT INTO outbound_log (module, host, status) VALUES (?, ?, ?)",
                (call["module"], call["host"], call["status"]),
            )

    all_findings: list[Finding] = [f for group in results for f in group]
    return all_findings
