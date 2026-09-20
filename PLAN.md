# Cog Host: local OSINT dashboard for the Raspberry Pi 500

**How to use this file:** save it as `PLAN.md` in an empty `~/cog-host/` folder, start Claude Code there, and paste the kickoff prompt at the bottom.

Written 18 September 2026. Free tiers, CLI flags and site lists change often, so treat every limit and flag below as "check before relying on it". Some choices in section 1 are assumptions, because the clarifying questions went unanswered. Edit them before you start.

---

## 0. Rules for Claude Code

- Work only inside `~/cog-host` unless a step says otherwise. Commit small and often.
- **Never** create accounts, accept terms, solve CAPTCHAs, or type keys or passwords into web forms. Those are HUMAN STEPs.
- Never commit secrets. Keys live in `~/cog-host/.env` (`chmod 600`, listed in `.gitignore`). I will add them myself, so do not ask me to paste keys into the chat.
- Ask before any `sudo` beyond `apt install`, before changing firewall, SSH or network settings, and before adding me to the `docker` group.
- Check every command against `--help` or current docs before running it. If this plan is wrong or out of date, say so and propose a fix. Do not guess.
- Test only with data I supply about myself (my own email, phone number, handles). Use mocks and fixtures for everything else. Never look up a real third party while testing.
- After each phase, run the tests, summarise what changed in five lines or fewer, then wait for "go".

---

## 1. Goal, scope and defaults

**Goal:** one local web page, **Cog Host**, where I paste an email, phone number, username, name plus company, or profile URL and get combined results from several open-source tools and free APIs, shown as normalised findings with a source and a confidence level.

**Coverage requested:** email addresses, phone numbers, social handles and profile links, LinkedIn, WhatsApp.

**Defaults chosen (change any row before you start):**

| Decision | Default | Why |
|---|---|---|
| Intended use | Self-audit, verifying recruiters and work contacts, checking unknown callers and scam senders | Keeps the design defensive and proportionate |
| Reach | `127.0.0.1` only. LAN access is opt-in and needs a login | The box will hold API keys and search history |
| Storage | Local SQLite history, auto-purged after 30 days, plus a "delete everything" button | Data minimisation |
| Cost | Free tiers only | As requested |
| Address | `http://localhost:8080`. Also try `http://cog.localhost:8080` (recent Chromium and Firefox should resolve `*.localhost` to loopback; confirm) | No hosts-file edits |
| Runtime | Python venv for the app, `pipx` for third-party tools, PhoneInfoga as a small local service | Avoids dependency clashes and PEP 668 errors on Debian |

---

## 2. Guardrails to build in

1. **Purpose gate.** Every search needs a purpose picked from a short list (own footprint, verify a contact, scam check, other with a note) and a tick box. Write an audit log entry containing the identifier type, purpose, time and a salted hash of the identifier, not the raw value. Raw values live only in History, which is purged.
2. **One identifier at a time.** No CSV upload, no bulk mode. Default rate limit: 10 searches an hour (configurable).
3. **LinkedIn:** never scrape and never automate a logged-in session. Only (a) search-API queries restricted to `linkedin.com`, and (b) prefilled links that open in my own browser.
4. **WhatsApp:** no unofficial libraries (Baileys, whatsapp-web.js and similar). Only number validation, line type, and a `wa.me` link I click myself.
5. **Sensitive categories hidden by default.** Filter adult, dating and similar sites out of username and email-registration results (`SHOW_SENSITIVE=false`).
6. **Out of scope by design:** physical addresses, data-broker or people-search sites, leaked-credential contents, and anything that logs in as me to view someone else's data. Breach checks return breach names only.
7. **No third-party telemetry or CDN scripts.** Vendor HTMX locally. Do not hotlink avatars (it leaks my IP); show links instead.
8. **Every outbound call is logged** (module, host, time, status) with keys and query-string secrets redacted.
9. **Notice on the About page:** looking up other people means handling personal data. UK GDPR and the Data Protection Act 2018 apply beyond purely personal or household use, and the Computer Misuse Act applies to anything that bypasses access controls. Not legal advice.

---

## 3. Architecture

Recommended: a thin FastAPI app with an HTMX front end and one adapter module per tool.

```
Browser (localhost:8080)
  | HTMX + server-sent events (results stream in live)
FastAPI app "cog_host"
  |- detect.py    classify input: email | phone | username | name+company | url
  |- guard.py     purpose gate, rate limit, sensitive filter
  |- runner.py    run modules concurrently, per-module timeout, 24h cache
  |- quota.py     monthly counters per API, warn at 80%
  |- modules/     each returns list[Finding]
  |    email:     offline syntax + MX + domain age (RDAP), Gravatar, EmailRep,
  |               XposedOrNot, Hunter (verify only), GitHub, Holehe (opt-in)
  |    phone:     phonenumbers (offline), Veriphone, PhoneInfoga, wa.me builder
  |    username:  Sherlock, Maigret (subprocess)
  |    web:       Tavily (restricted domains), dork-link builder, LinkedIn links
  |- SQLite       searches, findings, quota, audit_log
```

**Options considered**

| Option | Pros | Cons |
|---|---|---|
| **A. Thin custom app (recommended)** | Full control of guardrails, one results view, easy to add modules | You maintain roughly 1,000 lines of glue |
| B. SpiderFoot as the engine | Web UI and many modules out of the box | Heavier on a Pi, collects broadly, own UI, harder to enforce the guardrails above |
| C. Static launcher page | Ten minutes to build | No combined results, no quota tracking |

**Finding schema:** `module, kind (account | profile | breach | reputation | line_info | link | note), title, url, detail{}, confidence (high | medium | low), fetched_at, cached`.

**Confidence rules:** an exact match from an API is **high**. A username existing on a site is **medium**, and the UI must say that the same username does not prove the same person. A search snippet is **low**.

---

## 4. Phases

### Phase 0: audit the Pi

- Run: `cat /etc/os-release; uname -m; free -h; df -h ~; python3 --version; docker --version; systemctl --user is-system-running`
- Expect Raspberry Pi OS (Debian Bookworm), `aarch64`, Python 3.11. Record the results in `docs/ENVIRONMENT.md`.
- Report anything unexpected before continuing.

### Phase 1: base install

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip pipx git curl sqlite3 build-essential libxml2-dev libxslt1-dev libffi-dev libssl-dev
mkdir -p ~/cog-host && cd ~/cog-host && git init
python3 -m venv .venv && . .venv/bin/activate && pip install --upgrade pip
pipx ensurepath
```

- Debian marks system Python as externally managed. Use the venv or `pipx`. Never use `--break-system-packages`.
- Create `.gitignore` (`.env`, `.venv`, `*.db`, `reports/`) and `.env.example` before anything else.

### Phase 2: install the engines

1. **App libraries (in the venv):** `fastapi`, `uvicorn[standard]`, `jinja2`, `python-multipart`, `httpx`, `pydantic-settings`, `phonenumbers`, `email-validator`, `dnspython`, `argon2-cffi`, `pytest`, `respx`. Pin versions in `pyproject.toml`.
2. **Sherlock:** `pipx install sherlock-project`. Check `sherlock --version` and `--help`. Never pass `--nsfw`. Use `--print-found --no-color --timeout N` and `--csv` with `--folderoutput` pointing at a temp folder. Its `--json` flag loads site data; it does not produce JSON output.
3. **Maigret:** `pipx install maigret` (needs Python 3.10 or newer). By default it checks the top 500 sites. Confirm flag names in `maigret --help`, then use JSON output, a timeout, and the flags that turn off recursive search and page-data extraction, so scope stays limited to what I typed.
4. **Holehe (optional, off by default):** `pipx install holehe`. It probes sign-up or recovery endpoints on 120+ third-party sites, and its module list includes adult sites, so results go through the sensitive filter. Community modules break often; record which ones work.
5. **PhoneInfoga v2:** prefer the official `linux/arm64` release binary (releases include GPG signatures; verify it) and run it as a systemd user service: `phoneinfoga serve --no-client -p 5000`, bound to `127.0.0.1` only. Use the Docker image only if Docker is already installed and the image has an arm64 manifest.
   - Read its Swagger spec and call `GET /api/v2/scanners` before writing the adapter.
   - Enable only scanners that need no key: `local`, `ovh`, and `googlesearch` (which only generates search links).
   - **Do not use** `numverify` (free plan reported to be HTTP-only) or `googlecse` (Google's Custom Search JSON API is closed to new customers).

### Phase 3: API keys (HUMAN STEP, about 20 minutes)

Before you start:

- Use a dedicated alias address (for example a plus-address such as `you+cog@yourdomain`) so these sign-ups are easy to separate and delete later.
- Use a password manager. Paste each key straight into `~/cog-host/.env` with a text editor, not into chat.
- The limits below were checked on 18 September 2026. Confirm them at sign-up.

| # | Service | Used for | Free tier | Get a key | `.env` name |
|---|---|---|---|---|---|
| 1 | Hunter | Email verification, company email patterns | 50 credits a month shared across finder, domain search and verifier; API access included | hunter.io | `HUNTER_API_KEY` |
| 2 | EmailRep | Email reputation, linked-profile hints | Free tier | emailrep.io/key | `EMAILREP_API_KEY` |
| 3 | Veriphone | Phone validity, line type, carrier | 1,000 lookups a month, HTTPS on free | veriphone.io | `VERIPHONE_API_KEY` |
| 4 | Tavily | Search restricted to linkedin.com and social sites | 1,000 credits a month, no card | app.tavily.com | `TAVILY_API_KEY` |
| 5 | Gravatar (optional) | Public profile by email hash (SHA-256 of the lowercased, trimmed address) | Free; 1,000 requests an hour with a key, 100 without | Gravatar developer dashboard (needs a Gravatar account) | `GRAVATAR_API_KEY` |
| 6 | GitHub | Public profile and commit-email links | Free read-only personal token, no scopes | github.com/settings/tokens | `GITHUB_TOKEN` |
| 7 | XposedOrNot | Breach names for an email (no passwords) | No key; roughly 1 request a second | none | none |

**Deliberately excluded:** Have I Been Pwned API (paid key), Numverify (free plan reported HTTP-only), Google Custom Search JSON API (closed to new customers), Brave Search API (free tier reported removed for new sign-ups in 2026, sources conflict, so use Tavily instead), LinkedIn scraper APIs, breach-dump search engines, and people-search brokers.

**Claude Code:** build `scripts/check_keys.py`, which makes one minimal call per service and prints OK, FAIL or MISSING. Never print a key. Then wait for my "keys done".

### Phase 4: build Cog Host

**Layout**

```
cog-host/
  app/      main.py config.py detect.py guard.py runner.py quota.py cache.py db.py models.py
            modules/ templates/ static/
  scripts/  check_keys.py  update_tools.sh  purge_history.py
  tests/  docs/  .env.example  .gitignore  README.md  pyproject.toml
```

**Module contract:** `async def run(query, ctx) -> list[Finding]`. Modules must obey a timeout (45 s default, 120 s for Maigret), never raise (return a `note` finding with the error instead), declare their quota cost, and skip cleanly with "no key" when their key is missing. Cache results for 24 hours by (module, normalised input); cache errors for 5 minutes at most.

**Input handling**

- Email: lowercase, validate, then MX check.
- Phone: assume GB when there is no `+` prefix; convert to E.164.
- Username: strip a leading `@`; allow letters, digits and `._-` only; cap at 40 characters.
- Name plus company: for the LinkedIn finder.
- URL: parse the handle out (LinkedIn, GitHub, X, Instagram and so on). Do not fetch the page.
- **Subprocess safety:** never `shell=True`; pass arguments as a list; validate against the strict patterns above first; put `--` before the user value so it cannot be read as an option.

**Module behaviour**

- **Email:** offline checks first (syntax, MX, disposable-domain list, domain age via RDAP, flagging domains under 90 days old; RDAP coverage varies by TLD, so treat missing data as unknown, not suspicious). Then Gravatar, EmailRep, XposedOrNot, GitHub, and Hunter verify behind a "use limited-quota checks" toggle that shows credits left. Holehe only if `ENABLE_HOLEHE=true`, behind a confirm box: "This probes third-party sign-up or recovery endpoints. Only use it on addresses you own or have consent to check."
- **Phone:** `phonenumbers` (region, type, offline carrier prefix), Veriphone, PhoneInfoga local scanners, plus dork links.
- **WhatsApp:** show line type (landlines cannot have WhatsApp) and a `https://wa.me/<digits only>` link with the note "Opens WhatsApp. If the number is not registered, WhatsApp says so. Nothing here is automated."
- **LinkedIn:** build `"First Last" "Company"` queries and send them to Tavily with `include_domains=["linkedin.com"]`. Show title, snippet and URL labelled "search result, unverified". Add a link to LinkedIn's own people search that opens in my browser. Nothing on the Pi fetches linkedin.com. Test with my own name first; if Tavily returns nothing useful for LinkedIn, fall back to dork links only.
- **Social handles:** Sherlock and Maigret, output parsed, sensitive filter applied, banner "same username is not proof of same person". Also check GitHub by handle.
- **Dork links:** prefilled Google, Bing and DuckDuckGo queries (`"<email>"`, `"<phone>"`, `"<handle>"`) that open in my browser. This is the keyless fallback for everything above.

**UI**

- Header "Cog Host" with a small inline SVG cog. One search box with auto-detected type chips (Email, Phone, Username, Name + company, URL) that I can override. Purpose dropdown and tick box.
- Result tabs: Summary, Email, Phone, Social, LinkedIn, WhatsApp, Raw. Findings grouped by module with confidence chips and an Open link (`target="_blank" rel="noopener noreferrer"`).
- Live progress row per module: running, OK, skipped (no key), quota used up, error.
- Pages: **Status** (module health, tool versions, quota bars), **History** (open, delete, purge all, retention setting), **Keys** (configured or missing, masked, read-only), **About** (notice from section 2).
- Design: system font stack, light and dark via `prefers-color-scheme`, keyboard accessible, no frameworks beyond HTMX.

**Security**

- Bind `127.0.0.1:8080`. If `BIND_LAN=true`, refuse to start unless `AUTH_PASSWORD_HASH` (argon2) is set; use an HttpOnly, SameSite=Strict session cookie and CSRF tokens on every POST.
- Headers: `Content-Security-Policy: default-src 'self'; img-src 'self' data:; frame-ancestors 'none'`, `Referrer-Policy: no-referrer`, `X-Content-Type-Options: nosniff`.
- Some APIs take the key in the query string (Veriphone may). Redact query strings in all logs.
- Database file `chmod 600`. Nightly purge of History older than the retention setting.

**Build order:** (1) skeleton, config, DB, guard; (2) offline modules plus UI end to end; (3) keyed API modules with quota tracking and cache; (4) Sherlock, Maigret, PhoneInfoga; (5) Holehe opt-in; (6) Status, History, Keys and About pages.

### Phase 5: autostart and launcher

- systemd **user** unit at `~/.config/systemd/user/cog-host.service`: `WorkingDirectory=%h/cog-host`, `EnvironmentFile=%h/cog-host/.env`, `ExecStart=%h/cog-host/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080`, `Restart=on-failure`. Add sandbox options only if they work under the user manager; do not sink time into it.
- Ask me before `loginctl enable-linger` (only needed if the Pi should run headless).
- Desktop launcher at `~/.local/share/applications/cog-host.desktop`, named "Cog Host", opening the page in Chromium (confirm the binary name with `which chromium chromium-browser`).

### Phase 6: test and accept

- `pytest`: input detection and normalisation, guard (purpose gate, rate limit, sensitive filter), every module against mocked HTTP or fake binaries, database purge.
- Security tests: inputs such as `; rm -rf ~`, `--help`, `-h`, newlines and very long strings are rejected; the app refuses a LAN bind without auth.
- **HUMAN STEP smoke test:** search my own email, phone number and main handle. Confirm results look right, quotas count down, History shows the searches, and Purge empties it.

**Acceptance checklist**

- [ ] Cog Host loads at `http://localhost:8080` after a reboot
- [ ] Email, phone, username, name plus company and URL inputs are each detected correctly
- [ ] Modules without keys skip cleanly
- [ ] No request goes to linkedin.com or WhatsApp servers from the Pi
- [ ] Sensitive-category results are hidden by default
- [ ] Quotas are visible and warn at 80%
- [ ] All outbound calls appear in the audit log, and no secrets appear in any log
- [ ] `check_keys.py` passes for every key I added
- [ ] Purge deletes History, and audit entries older than the retention setting
- [ ] README explains how to update tools and add a module

### Phase 7: maintenance

- `scripts/update_tools.sh`: `pipx upgrade-all`, update PhoneInfoga, then run the smoke tests. Sherlock and Maigret site lists go stale, so do this monthly.
- Re-run `check_keys.py` monthly. Free tiers change, and the table in Phase 3 will age.
- The Status page should flag any module that has failed three runs in a row.

---

## 5. Non-goals

- Scraping LinkedIn, WhatsApp, Facebook, Instagram or any site that forbids it
- Unofficial WhatsApp clients, or reading someone's WhatsApp photo or status
- Physical address lookup, people-search brokers, leaked-password content
- Bulk or scheduled lookups, or monitoring a person over time
- Exposing the app to the public internet

## 6. Stretch goals (only after acceptance)

1. Print-friendly report page (browser "Save as PDF") for a saved search.
2. Optional AI summary of findings through the Claude API. Off by default: it sends findings to a third party and needs a paid key.
3. Local SearXNG (Docker, bound to localhost) as a keyless alternative to Tavily.
4. Reach Cog Host from my phone over Tailscale only, with login still required.
5. Company-domain checks for recruiter verification: SPF, DKIM and DMARC records, domain age, registrar.

## 7. Kickoff prompt to paste into Claude Code

> Read PLAN.md in full. Do Phase 0 and Phase 1 now. Follow the rules in section 0, stop at every HUMAN STEP, and summarise each phase in five lines or fewer before waiting for me to say "go".
