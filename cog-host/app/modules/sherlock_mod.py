"""Sherlock adapter. Runs the installed `sherlock` CLI as a subprocess with a
strict argument list (no shell=True), and skips cleanly if it isn't installed.
Install on the Pi with: pipx install sherlock-project
"""
import asyncio
import csv
import shutil
import tempfile
from pathlib import Path

from app.models import Confidence, Finding, Kind
from app.modules.base import note

name = "sherlock"
timeout_seconds = 90.0
quota_cost = 0


async def run(query: str, ctx: dict) -> list[Finding]:
    binary = shutil.which("sherlock")
    if not binary:
        return [note(name, "Sherlock not installed (pipx install sherlock-project)")]

    with tempfile.TemporaryDirectory() as tmpdir:
        proc = await asyncio.create_subprocess_exec(
            binary,
            "--print-found",
            "--no-color",
            "--timeout",
            "20",
            "--csv",
            "--folderoutput",
            tmpdir,
            "--",
            query,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_seconds)
        except asyncio.TimeoutError:
            proc.kill()
            return [note(name, "Sherlock timed out")]

        csv_path = Path(tmpdir) / f"{query}.csv"
        if not csv_path.exists():
            if proc.returncode != 0:
                # Sherlock prints its own errors (e.g. can't reach its site-data
                # host) to stdout, not stderr - check both, preferring stderr.
                combined = (stderr + b"\n" + stdout).decode("utf-8", "replace").strip().splitlines()
                detail = combined[-1] if combined else f"exit {proc.returncode}"
                return [note(name, f"Sherlock error: {detail}")]
            return [note(name, "Sherlock found no results")]

        findings = []
        with csv_path.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                url = row.get("url_user") or row.get("url")
                site = row.get("name") or row.get("site")
                if not url:
                    continue
                findings.append(
                    Finding(
                        module=name,
                        kind=Kind.ACCOUNT,
                        title=f"{site}: account found",
                        url=url,
                        confidence=Confidence.MEDIUM,
                        detail={"note": "Same username does not prove the same person."},
                    )
                )
        return findings or [note(name, "Sherlock found no results")]
