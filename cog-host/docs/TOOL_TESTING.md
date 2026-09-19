# Testing Sherlock, Maigret and Holehe against the real CLIs

The plan's Phase 2 flags for these tools were reasonable guesses at the time
of writing. Installing the real tools (`pipx install --backend pip
sherlock-project maigret holehe`) and running them found two real bugs the
docs alone wouldn't have caught, plus one behaviour worth flagging.

## Maigret: nested status field (real bug, fixed)

A real `maigret --json simple` run against a claimed account produces:

```json
{"GitHubGist": {"url_user": "...", "status": {"status": "Claimed", ...}}}
```

`status` is an object, not a string. The original adapter checked
`info.get("status") != "Claimed"`, which is a dict-vs-string comparison that
is always true - every result would have been silently dropped as
"unclaimed", even genuine matches. Fixed to
`info.get("status", {}).get("status") != "Claimed"` and covered by
`tests/test_subprocess_tools.py::test_maigret_parses_real_nested_status_shape`,
which fixes a JSON fixture in that exact shape so a regression trips a test,
not a silent no-op in production.

Confirmed against a real run (username `octocat`, the GitHub mascot test
account - not a real private individual): the fixed adapter correctly
surfaced `Launchpad` and `GitHubGist` matches.

## Holehe: no `--json` flag exists (real bug, fixed)

Holehe 1.61's `--help` has no JSON output option at all - `-C`/`--csv` is the
only structured output, and reading its source
(`holehe/core.py::export_csv`) shows it always writes to the **current
working directory** as `holehe_<unix-timestamp>_<email>_results.csv`; there
is no `--folderoutput` equivalent. The original adapter assumed a `--json`
flag that doesn't exist and would have failed outright. Rewritten to run the
subprocess with `cwd` set to a temp directory and glob for that filename
pattern, parsing the CSV's `domain`/`exists` columns (confirmed against a
real run with the RFC 2606 placeholder `test@example.com` - no real
third party was queried).

Also: Holehe's CLI calls Python's `exit("All results have been
exported...")` on its own success path, so it **always exits with status 1**,
success or failure. Sherlock and Maigret's own errors (see below) are
distinguished by return code, but that signal doesn't exist for Holehe -
whether the CSV file appeared is the only reliable signal, and the adapter
is commented accordingly so this isn't "fixed" incorrectly later.

## Sherlock and Maigret: errors print to stdout, not stderr

Confirmed by forcing both tools to fail (Sherlock's online site-data host
unreachable; Maigret given a `--site` filter matching nothing): both print
their error message to **stdout**, with stderr empty. The original adapters
only captured stderr for diagnostics on failure, so a real failure looked
identical to "no results found" - a silent false negative. Both adapters now
check `proc.returncode` and read the last non-empty line of stdout+stderr
combined when the expected output file is missing, so a genuine tool error
is reported as `"<tool> error: ..."` rather than misreported as a clean
empty result.

## What's still unverified

PhoneInfoga could not be tested at all in this environment: its release
binary is `linux/arm64`-only for the Pi, this container is `x86_64`, and its
GitHub releases page was blocked by this container's egress policy. Its
scanner list (`local`, `ovh`, `googlesearch`) and the `/api/v2/scan` response
shape used by `app/modules/phoneinfoga_mod.py` are taken from the plan and
PhoneInfoga's public docs, not confirmed against a live instance. Follow
`docs/PHONEINFOGA.md` step 3 (`GET /api/v2/scanners`) on the Pi before
trusting it, and treat the response-parsing logic in that module as the part
most likely to need adjustment.
