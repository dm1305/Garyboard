import re
from dataclasses import dataclass
from urllib.parse import urlparse

import phonenumbers
from email_validator import EmailNotValidError, validate_email

from app.models import InputType

USERNAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,39}$")

URL_HANDLE_PATTERNS = {
    "linkedin.com": re.compile(r"linkedin\.com/in/([^/?#]+)"),
    "github.com": re.compile(r"github\.com/([^/?#]+)"),
    "x.com": re.compile(r"(?:x|twitter)\.com/([^/?#]+)"),
    "instagram.com": re.compile(r"instagram\.com/([^/?#]+)"),
}


@dataclass
class DetectedInput:
    input_type: InputType
    normalised: str
    detail: dict


class InvalidInput(Exception):
    pass


def normalise_email(value: str) -> str:
    try:
        result = validate_email(value.strip(), check_deliverability=False)
    except EmailNotValidError as exc:
        raise InvalidInput(str(exc)) from exc
    return result.normalized.lower()


def normalise_phone(value: str, default_region: str = "GB") -> str:
    value = value.strip()
    try:
        parsed = phonenumbers.parse(value, None if value.startswith("+") else default_region)
    except phonenumbers.NumberParseException as exc:
        raise InvalidInput(str(exc)) from exc
    if not phonenumbers.is_valid_number(parsed):
        raise InvalidInput("Not a valid phone number.")
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)


def normalise_username(value: str) -> str:
    value = value.strip().lstrip("@")
    if not USERNAME_RE.match(value):
        raise InvalidInput(
            "Usernames may only contain letters, digits, '.', '_' or '-', max 40 characters."
        )
    return value


def extract_url_handle(value: str) -> tuple[str, str]:
    parsed = urlparse(value if "://" in value else f"https://{value}")
    host = parsed.netloc.lower().removeprefix("www.")
    for domain, pattern in URL_HANDLE_PATTERNS.items():
        if domain in host:
            match = pattern.search(value)
            if match:
                return domain, match.group(1).rstrip("/")
    if parsed.path:
        return host, parsed.path.strip("/").split("/")[0]
    raise InvalidInput("Could not extract a handle from that URL.")


def classify(value: str, hint: str | None = None) -> DetectedInput:
    """Classify raw input into an InputType, applying an optional user override hint."""
    value = value.strip()
    if not value:
        raise InvalidInput("Empty input.")
    if len(value) > 320:
        raise InvalidInput("Input too long.")

    order = [hint] if hint else []
    order += [t.value for t in InputType if t.value != hint]

    for candidate in order:
        try:
            if candidate == InputType.EMAIL.value and "@" in value:
                return DetectedInput(InputType.EMAIL, normalise_email(value), {})
            if candidate == InputType.URL.value and (
                value.startswith(("http://", "https://")) or "/" in value
            ):
                domain, handle = extract_url_handle(value)
                return DetectedInput(InputType.URL, value, {"domain": domain, "handle": handle})
            if candidate == InputType.PHONE.value and len(re.sub(r"\D", "", value)) >= 7:
                return DetectedInput(InputType.PHONE, normalise_phone(value), {})
            if candidate == InputType.NAME_COMPANY.value and "," in value:
                name, _, company = value.partition(",")
                return DetectedInput(
                    InputType.NAME_COMPANY,
                    value,
                    {"name": name.strip(), "company": company.strip()},
                )
            if candidate == InputType.USERNAME.value:
                return DetectedInput(InputType.USERNAME, normalise_username(value), {})
        except InvalidInput:
            continue

    raise InvalidInput(
        "Could not classify that input. Try an email, phone number (with country code "
        "or a GB number), @username, 'Name, Company', or a profile URL."
    )
