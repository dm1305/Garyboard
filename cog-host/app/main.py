import json
import secrets
import shutil
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.cache import ModuleCache
from app.config import settings, validate_startup
from app.db import get_conn, init_db
from app.detect import InvalidInput, classify
from app.guard import (
    PurposeRequired,
    RateLimitExceeded,
    apply_sensitive_filter,
    check_purpose,
    check_rate_limit,
    record_audit,
)
from app.quota import status as quota_status
from app.runner import MODULES_BY_TYPE, run_search
from app.security import (
    check_csrf,
    get_csrf_token,
    require_login,
    verify_password,
)

BASE_DIR = Path(__file__).resolve().parent

validate_startup(settings)
init_db(settings.db_path)

app = FastAPI(title="Cog Host")
app.state.settings = settings
app.state.cache = ModuleCache()

session_secret_path = BASE_DIR.parent / ".session_secret"
if not session_secret_path.exists():
    session_secret_path.write_text(secrets.token_urlsafe(32))
    try:
        session_secret_path.chmod(0o600)
    except OSError:
        pass

app.add_middleware(
    SessionMiddleware,
    secret_key=session_secret_path.read_text().strip(),
    same_site="strict",
    https_only=False,
)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' data:; frame-ancestors 'none'"
    )
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


PURPOSE_LABELS = {
    "own_footprint": "Checking my own footprint",
    "verify_contact": "Verifying a recruiter or work contact",
    "scam_check": "Checking an unknown caller or scam sender",
    "other": "Other",
}


@app.get("/login", response_class=HTMLResponse)
async def login_form(request: Request):
    return templates.TemplateResponse(
        "login.html", {"request": request, "csrf_token": get_csrf_token(request), "error": None}
    )


@app.post("/login", response_class=HTMLResponse)
async def login_submit(request: Request, password: str = Form(...), csrf_token: str = Form(...)):
    check_csrf(request, csrf_token)
    if settings.auth_password_hash and verify_password(password, settings.auth_password_hash):
        request.session["authenticated"] = True
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "csrf_token": get_csrf_token(request), "error": "Wrong password."},
        status_code=401,
    )


@app.get("/", response_class=HTMLResponse)
async def index(request: Request, _=Depends(require_login)):
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "csrf_token": get_csrf_token(request),
            "findings": None,
            "enable_holehe": settings.enable_holehe,
        },
    )


@app.post("/search", response_class=HTMLResponse)
async def search(
    request: Request,
    query: str = Form(...),
    hint: str = Form(""),
    purpose: str = Form(""),
    purpose_note: str = Form(""),
    confirmed: str = Form(""),
    use_limited_quota: str = Form(""),
    holehe_confirmed: str = Form(""),
    csrf_token: str = Form(...),
    _=Depends(require_login),
):
    check_csrf(request, csrf_token)
    ctx_common = {
        "request": request,
        "csrf_token": get_csrf_token(request),
        "query": query,
        "hint": hint,
        "findings": None,
        "enable_holehe": settings.enable_holehe,
    }

    try:
        check_purpose(purpose, purpose_note, confirmed == "yes")
    except PurposeRequired as exc:
        return templates.TemplateResponse("index.html", {**ctx_common, "error": str(exc)})

    try:
        check_rate_limit(settings.db_path, settings.rate_limit_per_hour)
    except RateLimitExceeded as exc:
        return templates.TemplateResponse("index.html", {**ctx_common, "error": str(exc)})

    try:
        detected = classify(query, hint or None)
    except InvalidInput as exc:
        return templates.TemplateResponse("index.html", {**ctx_common, "error": str(exc)})

    record_audit(settings.db_path, settings.audit_salt_path, detected.input_type.value, query, purpose)

    with get_conn(settings.db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO searches (input_type, raw_value, purpose, purpose_note, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (detected.input_type.value, query, purpose, purpose_note, datetime.now(UTC).isoformat()),
        )
        search_id = cursor.lastrowid

    findings = await run_search(
        detected.input_type,
        detected.normalised,
        settings,
        request.app.state.cache,
        extra_detail=detected.detail,
        use_limited_quota=use_limited_quota == "yes",
        holehe_confirmed=holehe_confirmed == "yes",
    )
    findings = apply_sensitive_filter(findings, settings.show_sensitive)

    with get_conn(settings.db_path) as conn:
        for f in findings:
            conn.execute(
                """
                INSERT INTO findings
                    (search_id, module, kind, title, url, detail_json,
                     confidence, sensitive, fetched_at, cached)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    search_id,
                    f.module,
                    f.kind.value,
                    f.title,
                    f.url,
                    json.dumps(f.detail),
                    f.confidence.value,
                    int(f.sensitive),
                    f.fetched_at,
                    int(f.cached),
                ),
            )

    grouped = defaultdict(list)
    for f in findings:
        grouped[f.module].append(f)

    module_names = [m.name for m in MODULES_BY_TYPE.get(detected.input_type, [])]
    progress = {}
    for name in module_names:
        mod_findings = grouped.get(name, [])
        if not mod_findings:
            progress[name] = "skip"
        elif any(
            f.title.startswith(f"{name} error") or "timed out" in f.title for f in mod_findings
        ):
            progress[name] = "error"
        elif any(
            phrase in f.title
            for f in mod_findings
            for phrase in ("no key", "not installed", "disabled")
        ):
            progress[name] = "skip"
        else:
            progress[name] = "ok"

    return templates.TemplateResponse(
        "index.html",
        {
            **ctx_common,
            "detected_type": detected.input_type.value,
            "findings": findings,
            "grouped": grouped,
            "progress": progress,
        },
    )


@app.get("/status", response_class=HTMLResponse)
async def status_page(request: Request, _=Depends(require_login)):
    tool_checks = [
        {
            "name": "sherlock",
            "available": bool(shutil.which("sherlock")),
            "note": "pipx install sherlock-project",
        },
        {
            "name": "maigret",
            "available": bool(shutil.which("maigret")),
            "note": "pipx install maigret",
        },
        {
            "name": "holehe",
            "available": bool(shutil.which("holehe")),
            "note": "pipx install holehe (also needs ENABLE_HOLEHE=true)",
        },
    ]
    return templates.TemplateResponse(
        "status.html",
        {"request": request, "modules": tool_checks, "quota": quota_status(settings.db_path)},
    )


@app.get("/history", response_class=HTMLResponse)
async def history_page(request: Request, _=Depends(require_login)):
    with get_conn(settings.db_path) as conn:
        searches = conn.execute(
            """
            SELECT id, input_type, raw_value, purpose, created_at FROM searches
            ORDER BY created_at DESC LIMIT 200
            """
        ).fetchall()
    return templates.TemplateResponse(
        "history.html",
        {
            "request": request,
            "searches": searches,
            "csrf_token": get_csrf_token(request),
            "retention_days": settings.history_retention_days,
        },
    )


@app.post("/history/{search_id}/delete")
async def history_delete(
    request: Request,
    search_id: int,
    csrf_token: str = Form(...),
    _=Depends(require_login),
):
    check_csrf(request, csrf_token)
    with get_conn(settings.db_path) as conn:
        conn.execute("DELETE FROM searches WHERE id = ?", (search_id,))
    return RedirectResponse("/history", status_code=303)


@app.post("/history/purge")
async def history_purge(request: Request, csrf_token: str = Form(...), _=Depends(require_login)):
    check_csrf(request, csrf_token)
    with get_conn(settings.db_path) as conn:
        conn.execute("DELETE FROM searches")
        conn.execute("DELETE FROM audit_log")
    return RedirectResponse("/history", status_code=303)


@app.get("/keys", response_class=HTMLResponse)
async def keys_page(request: Request, _=Depends(require_login)):
    def mask(value: str) -> str:
        if not value:
            return ""
        return value[:4] + "…" if len(value) > 4 else "…"

    key_fields = [
        ("HUNTER_API_KEY", settings.hunter_api_key),
        ("EMAILREP_API_KEY", settings.emailrep_api_key),
        ("VERIPHONE_API_KEY", settings.veriphone_api_key),
        ("TAVILY_API_KEY", settings.tavily_api_key),
        ("GRAVATAR_API_KEY", settings.gravatar_api_key),
        ("GITHUB_TOKEN", settings.github_token),
    ]
    keys = [
        {"name": name, "configured": bool(value), "masked": mask(value)}
        for name, value in key_fields
    ]
    return templates.TemplateResponse("keys.html", {"request": request, "keys": keys})


@app.get("/about", response_class=HTMLResponse)
async def about_page(request: Request):
    return templates.TemplateResponse("about.html", {"request": request})
