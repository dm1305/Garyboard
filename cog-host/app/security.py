import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import HTTPException, Request

_hasher = PasswordHasher()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False
    except Exception:  # noqa: BLE001 - malformed hash, treat as no match
        return False


def is_authenticated(request: Request) -> bool:
    return bool(request.session.get("authenticated"))


def require_login(request: Request) -> None:
    settings = request.app.state.settings
    if not settings.bind_lan:
        return
    if not is_authenticated(request):
        raise HTTPException(status_code=303, headers={"Location": "/login"})


def get_csrf_token(request: Request) -> str:
    token = request.session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        request.session["csrf_token"] = token
    return token


def check_csrf(request: Request, submitted_token: str | None) -> None:
    expected = request.session.get("csrf_token")
    if not expected or not submitted_token or not secrets.compare_digest(expected, submitted_token):
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token")
