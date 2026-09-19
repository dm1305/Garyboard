# Cog Host

A local OSINT dashboard: paste an email, phone number, username, name plus
company, or profile URL and get combined results from several open-source
tools and free APIs, shown as normalised findings with a source and a
confidence level. See `../PLAN.md` for the full design and guardrails this
implements.

**Built where, tested where:** this codebase was written and tested in a
cloud dev container (Ubuntu 24.04, x86_64), not the target Raspberry Pi 500.
See `docs/ENVIRONMENT.md` for exactly what that does and doesn't change.
Everything under `app/` and `tests/` is portable and runs as-is on the Pi;
hardware-specific setup (PhoneInfoga's ARM64 binary, the systemd unit, the
desktop launcher) is drafted in `docs/` but untested on real hardware.

## Installing on the Pi

Download and read `scripts/bootstrap_pi.sh` before running it (it uses
`sudo` for `apt install` only - never for anything else):

```bash
curl -fsSL -o bootstrap_pi.sh \
  https://raw.githubusercontent.com/dm1305/Garyboard/OSIN/cog-host/scripts/bootstrap_pi.sh
less bootstrap_pi.sh   # read it first
bash bootstrap_pi.sh
```

It installs system packages, clones this branch into `~/cog-host`, sets up
the Python venv and dependencies, installs Sherlock/Maigret/Holehe via
`pipx`, and runs the test suite to confirm the install is healthy. It's
safe to re-run to update later - your `.env`, database and venv are never
touched. It prints the remaining human steps (API keys, PhoneInfoga,
vendoring htmx, autostart) at the end rather than doing them for you -
tested end-to-end, including a second re-run to confirm nothing gets
clobbered.

## What's built

- **Guardrails**: purpose gate, hourly rate limit, sensitive-site filter,
  salted-hash audit log (raw values never stored in the audit log, only in
  History), CSRF protection, security headers, localhost-only bind by
  default with a hard refusal to bind to the LAN without a password hash set.
- **Offline modules** (no API key, no third party contacted beyond public
  DNS/RDAP): email syntax + MX + disposable-domain check + RDAP domain age;
  SPF/DMARC records + RDAP registrar for the email's domain (DKIM is
  deliberately skipped - its selector can't be guessed); phone
  type/region/carrier via `phonenumbers` plus a `wa.me` link; dork links
  (Google/Bing/DuckDuckGo) as the keyless fallback for everything.
- **Dark-web search link**: a prefilled Ahmia (ahmia.fi) search URL, exactly
  the same keyless-link pattern as the dork links - Cog Host never fetches
  it or any `.onion` address itself; you open results yourself in Tor
  Browser. Raw dark-web crawling and leaked-credential contents stay out of
  scope by design (see `PLAN.md` section 2).
- **Finding deduplication**: when two modules independently find the same
  URL (e.g. a GitHub profile via both the API and Sherlock), the lower-
  confidence duplicate is merged in as "also found by" rather than shown
  twice.
- **Export**: download any past search's findings as JSON or CSV from the
  History page.
- **Keyed modules**, each skipping cleanly with "no key" when unconfigured:
  Hunter (behind a "limited-quota checks" opt-in, since it spends shared
  monthly credits), EmailRep, Veriphone, Tavily (LinkedIn search restricted
  to `linkedin.com`, never fetched directly), Gravatar, GitHub, XposedOrNot
  (breach names only, no key needed).
- **External-tool adapters**, subprocess-based, skip cleanly if the binary
  isn't installed: Sherlock, Maigret, Holehe (off by default, needs
  `ENABLE_HOLEHE=true` **and** a per-search confirmation tick), PhoneInfoga
  (calls a local service, see `docs/PHONEINFOGA.md`). Sherlock, Maigret and
  Holehe were installed and run for real here, which found and fixed two
  real bugs (Maigret's nested status field, Holehe's actual CSV-only output)
  - see `docs/TOOL_TESTING.md` for exactly what was checked. PhoneInfoga
  couldn't be tested (arm64-only binary, blocked releases page) - its
  scanner list is unverified.
- **UI**: search page with type auto-detection and an override, purpose
  dropdown, live per-module progress, confidence chips, and Status /
  History / Keys / About pages. Vendor HTMX per `app/static/README.md` for
  the live-progress enhancement; the app works fully without it.
- **59 tests** covering input detection/rejection, the guard, offline
  modules (mocked HTTP/DNS), keyed-module key handling, subprocess-tool
  fallback, DB purge, the LAN-bind refusal, deduplication, JSON/CSV export,
  and regression tests for the two real bugs found while testing
  Sherlock/Maigret/Holehe against the real CLIs.

## What's still a human step

- Creating API key accounts (Phase 3 of `../PLAN.md`) and pasting them into
  `.env` - nobody but you should do this.
- Running Phase 0/1 on the actual Pi and updating `docs/ENVIRONMENT.md`.
- Installing Sherlock/Maigret/Holehe/PhoneInfoga on the Pi (`pipx install
  --backend pip ...` - the default `uv` backend needs a newer `uv` than this
  container had; check the Pi's `uv --version` before dropping that flag).
- PhoneInfoga specifically still needs its own setup on the Pi and its
  scanner behaviour confirmed - see `docs/PHONEINFOGA.md` and the "what's
  still unverified" section of `docs/TOOL_TESTING.md`.
- Vendoring `htmx.min.js` (blocked by this container's network policy, see
  `app/static/README.md`).
- The Phase 6 human smoke test: search your own email, phone, and handle
  once running on the Pi.

## Running it

```bash
cd cog-host
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env && chmod 600 .env   # fill in only the keys you have
python -m uvicorn app.main:app --host 127.0.0.1 --port 8080
```

Open `http://localhost:8080`.

## Testing

```bash
. .venv/bin/activate
python -m pytest -q
ruff check app/ tests/ scripts/
mypy app/ --ignore-missing-imports
python scripts/check_keys.py   # after adding keys to .env
```

All three (48 tests, ruff, mypy) are clean as of this commit.

## Adding a module

1. Add `app/modules/your_thing.py` with `name`, `timeout_seconds`,
   `quota_cost`, and `async def run(query, ctx) -> list[Finding]`. Never
   raise - return a `note()` Finding on error instead (see
   `app/modules/base.py`); the runner also catches exceptions defensively,
   but modules should report their own failures clearly.
2. Register it in `MODULES_BY_TYPE` in `app/runner.py` under the relevant
   input type(s).
3. If it costs quota, add it to `MONTHLY_LIMITS` in `app/quota.py`.
4. Add a test in `tests/` following the pattern in
   `tests/test_modules_offline.py` (mock HTTP with `respx`) or
   `tests/test_modules_keyed.py` (fake settings object).

## Updating tools

```bash
scripts/update_tools.sh
```

Do this monthly - Sherlock/Maigret site lists and free-tier API limits both
go stale (Phase 7 of `../PLAN.md`).
