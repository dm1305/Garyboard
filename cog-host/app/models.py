from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class Kind(StrEnum):
    ACCOUNT = "account"
    PROFILE = "profile"
    BREACH = "breach"
    REPUTATION = "reputation"
    LINE_INFO = "line_info"
    LINK = "link"
    NOTE = "note"


class Confidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class InputType(StrEnum):
    EMAIL = "email"
    PHONE = "phone"
    USERNAME = "username"
    NAME_COMPANY = "name_company"
    URL = "url"
    UNKNOWN = "unknown"


@dataclass
class Finding:
    module: str
    kind: Kind
    title: str
    confidence: Confidence
    url: str | None = None
    detail: dict = field(default_factory=dict)
    sensitive: bool = False
    fetched_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )
    cached: bool = False

    def to_dict(self) -> dict:
        return {
            "module": self.module,
            "kind": self.kind.value,
            "title": self.title,
            "confidence": self.confidence.value,
            "url": self.url,
            "detail": self.detail,
            "sensitive": self.sensitive,
            "fetched_at": self.fetched_at,
            "cached": self.cached,
        }
