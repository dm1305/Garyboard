"""Holehe adapter - off by default. Probes sign-up/recovery endpoints on
120+ third-party sites, some adult, so results go through the sensitive
filter and this module only runs when ENABLE_HOLEHE=true AND the caller
has ticked the per-search confirm box.
Install on the Pi with: pipx install holehe
"""
import asyncio
import json
import shutil
import tempfile
from pathlib import Path

from app.models import Confidence, Finding, Kind
from app.modules.base import note

name = "holehe"
timeout_seconds = 60.0
quota_cost = 0

CONFIRM_MESSAGE = (
    "This probes third-party sign-up or recovery endpoints. "
    "Only use it on addresses you own or have consent to check."
)


async def run(query: str, ctx: dict) -> list[Finding]:
    if not ctx.get("settings").enable_holehe:
        return [note(name, "disabled (set ENABLE_HOLEHE=true to enable)")]
    if not ctx.get("holehe_confirmed"):
        return [note(name, f"skipped: not confirmed. {CONFIRM_MESSAGE}")]

    binary = shutil.which("holehe")
    if not binary:
        return [note(name, "Holehe not installed (pipx install holehe)")]

    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = Path(tmpdir) / "out.json"
        proc = await asyncio.create_subprocess_exec(
            binary,
            "--",
            query,
            "--json",
            str(out_path),
            "--only-used",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            await asyncio.wait_for(proc.communicate(), timeout=timeout_seconds)
        except asyncio.TimeoutError:
            proc.kill()
            return [note(name, "Holehe timed out")]

        if not out_path.exists():
            return [note(name, "Holehe found no results")]

        try:
            data = json.loads(out_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return [note(name, "Could not parse Holehe output")]

        findings = []
        for entry in data:
            if not entry.get("exists"):
                continue
            findings.append(
                Finding(
                    module=name,
                    kind=Kind.ACCOUNT,
                    title=f"{entry.get('name')}: account registered",
                    confidence=Confidence.MEDIUM,
                    detail={"note": "Community modules break often; verify independently."},
                )
            )
        return findings or [note(name, "Holehe found no results")]
