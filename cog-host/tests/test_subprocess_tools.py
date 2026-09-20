import json
from pathlib import Path

import pytest

from app.modules import holehe_mod, maigret_mod, sherlock_mod


class FakeSettings:
    enable_holehe = False


class FakeProcess:
    async def communicate(self):
        return b"", b""

    def kill(self):
        pass


def _fake_exec_writing(write_fn):
    """Build a fake create_subprocess_exec that writes a fixture file before returning,
    mimicking the real CLI producing its report as a side effect."""

    async def fake_exec(*args, **kwargs):
        write_fn(args, kwargs)
        return FakeProcess()

    return fake_exec


@pytest.mark.asyncio
async def test_sherlock_skips_cleanly_when_not_installed(monkeypatch):
    monkeypatch.setattr(sherlock_mod.shutil, "which", lambda name: None)
    findings = await sherlock_mod.run("bob", {})
    assert "not installed" in findings[0].title


@pytest.mark.asyncio
async def test_maigret_skips_cleanly_when_not_installed(monkeypatch):
    monkeypatch.setattr(maigret_mod.shutil, "which", lambda name: None)
    findings = await maigret_mod.run("bob", {})
    assert "not installed" in findings[0].title


@pytest.mark.asyncio
async def test_holehe_disabled_by_default():
    findings = await holehe_mod.run("bob@example.com", {"settings": FakeSettings()})
    assert "disabled" in findings[0].title


@pytest.mark.asyncio
async def test_holehe_requires_confirmation_even_when_enabled():
    class Enabled(FakeSettings):
        enable_holehe = True

    findings = await holehe_mod.run(
        "bob@example.com", {"settings": Enabled(), "holehe_confirmed": False}
    )
    assert "not confirmed" in findings[0].title


@pytest.mark.asyncio
async def test_maigret_parses_real_nested_status_shape(monkeypatch, tmp_path):
    """Regression test: Maigret's JSON nests the verdict as status.status, a dict,
    not a flat string - confirmed against a real `maigret --json simple` run.
    A naive `info.get("status") != "Claimed"` check silently drops every result.
    """
    monkeypatch.setattr(maigret_mod.shutil, "which", lambda name: "/usr/bin/maigret")

    def write_report(args, kwargs):
        folder = args[args.index("--folderoutput") + 1]
        report = Path(folder) / "report_bob_simple.json"
        report.write_text(
            json.dumps(
                {
                    "GitHubGist": {
                        "url_user": "https://gist.github.com/bob",
                        "url_main": "https://gist.github.com",
                        "status": {"status": "Claimed", "site_name": "GitHubGist"},
                    },
                    "SomeUnclaimedSite": {
                        "url_user": "https://example.com/bob",
                        "status": {"status": "Not found"},
                    },
                }
            )
        )

    monkeypatch.setattr(
        maigret_mod.asyncio, "create_subprocess_exec", _fake_exec_writing(write_report)
    )
    findings = await maigret_mod.run("bob", {})
    assert len(findings) == 1
    assert findings[0].url == "https://gist.github.com/bob"


@pytest.mark.asyncio
async def test_holehe_parses_real_csv_shape(monkeypatch):
    """Regression test: Holehe 1.61 has no --json flag; it writes
    holehe_<ts>_<email>_results.csv (via -C) to the CWD, with an `exists`
    column of the literal strings "True"/"False" - confirmed against the
    real CLI's export_csv().
    """
    monkeypatch.setattr(holehe_mod.shutil, "which", lambda name: "/usr/bin/holehe")

    def write_csv(args, kwargs):
        cwd = kwargs["cwd"]
        csv_path = Path(cwd) / "holehe_1234567890_bob@example.com_results.csv"
        csv_path.write_text(
            "name,domain,exists,rateLimit,emailrecovery,phoneNumber,others\n"
            "github,github.com,True,False,,,\n"
            "adobe,adobe.com,False,False,,,\n"
        )

    monkeypatch.setattr(
        holehe_mod.asyncio, "create_subprocess_exec", _fake_exec_writing(write_csv)
    )

    class Enabled(FakeSettings):
        enable_holehe = True

    findings = await holehe_mod.run(
        "bob@example.com", {"settings": Enabled(), "holehe_confirmed": True}
    )
    assert len(findings) == 1
    assert "github.com" in findings[0].title
