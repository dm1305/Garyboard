"""Holehe adapter - off by default. Probes sign-up/recovery endpoints on
120+ third-party sites, some adult, so results go through the sensitive
filter and this module only runs when ENABLE_HOLEHE=true AND the caller
has ticked the per-search confirm box.
Install on the Pi with: pipx install holehe

Holehe 1.61 has no JSON output flag - only -C/--csv, and it writes
`holehe_<timestamp>_<email>_results.csv` to the current working directory
(no --folderoutput option), so this adapter runs the subprocess with cwd
set to a temp dir and globs for that file afterwards.
"""
import asyncio
import csv
import glob
import io
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
        proc = await asyncio.create_subprocess_exec(
            binary,
            "--only-used",
            "--no-color",
            "--csv",
            "--",
            query,
            cwd=tmpdir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            await asyncio.wait_for(proc.communicate(), timeout=timeout_seconds)
        except TimeoutError:
            proc.kill()
            return [note(name, "Holehe timed out")]

        # Holehe's own CLI calls exit("All results have been exported...") on the
        # success path, so it always exits 1 - the return code can't distinguish
        # success from failure here. Whether the CSV appeared is the only signal.
        csv_files = glob.glob(f"{tmpdir}/holehe_*_results.csv")
        if not csv_files:
            return [note(name, "Holehe found no results (or the CLI errored - check the Pi's logs)")]

        content = await asyncio.to_thread(Path(csv_files[0]).read_text, encoding="utf-8")
        findings = []
        for row in csv.DictReader(io.StringIO(content)):
            if row.get("exists") != "True":
                continue
            findings.append(
                Finding(
                    module=name,
                    kind=Kind.ACCOUNT,
                    title=f"{row.get('domain', row.get('name'))}: account registered",
                    confidence=Confidence.MEDIUM,
                    detail={"note": "Community modules break often; verify independently."},
                )
            )
        return findings or [note(name, "Holehe found no results")]
