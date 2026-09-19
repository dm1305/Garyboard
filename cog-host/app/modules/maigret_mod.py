"""Maigret adapter. Runs the installed `maigret` CLI as a subprocess with a
strict argument list, JSON output, no recursion and no page-data extraction.
Install on the Pi with: pipx install maigret (needs Python >= 3.10)
"""
import asyncio
import json
import shutil
import tempfile
from pathlib import Path

from app.models import Confidence, Finding, Kind
from app.modules.base import note

name = "maigret"
timeout_seconds = 120.0
quota_cost = 0


async def run(query: str, ctx: dict) -> list[Finding]:
    binary = shutil.which("maigret")
    if not binary:
        return [note(name, "Maigret not installed (pipx install maigret)")]

    with tempfile.TemporaryDirectory() as tmpdir:
        proc = await asyncio.create_subprocess_exec(
            binary,
            "--json",
            "simple",
            "--folderoutput",
            tmpdir,
            "--timeout",
            "20",
            "--no-recursion",
            "--no-extracting",
            "--no-autoupdate",
            "--no-progressbar",
            "--",
            query,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_seconds)
        except asyncio.TimeoutError:
            proc.kill()
            return [note(name, "Maigret timed out")]

        json_files = list(Path(tmpdir).glob(f"report_{query}_simple.json"))
        if not json_files:
            if proc.returncode != 0:
                # Maigret prints its own errors to stdout, not stderr.
                combined = (stderr + b"\n" + stdout).decode("utf-8", "replace").strip().splitlines()
                detail = combined[-1] if combined else f"exit {proc.returncode}"
                return [note(name, f"Maigret error: {detail}")]
            return [note(name, "Maigret found no results")]

        try:
            data = json.loads(json_files[0].read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return [note(name, "Could not parse Maigret output")]

        findings = []
        for site, info in data.items():
            # Maigret nests the verdict under status.status, not a flat "status" key.
            if info.get("status", {}).get("status") != "Claimed":
                continue
            findings.append(
                Finding(
                    module=name,
                    kind=Kind.ACCOUNT,
                    title=f"{site}: account found",
                    url=info.get("url_user") or info.get("url_main"),
                    confidence=Confidence.MEDIUM,
                    detail={"note": "Same username does not prove the same person."},
                )
            )
        return findings or [note(name, "Maigret found no results")]
