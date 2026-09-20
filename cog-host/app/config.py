from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    bind_lan: bool = False
    auth_password_hash: str = ""

    rate_limit_per_hour: int = 10
    history_retention_days: int = 30
    show_sensitive: bool = False
    enable_holehe: bool = False

    hunter_api_key: str = ""
    emailrep_api_key: str = ""
    veriphone_api_key: str = ""
    tavily_api_key: str = ""
    gravatar_api_key: str = ""
    github_token: str = ""

    phoneinfoga_url: str = "http://127.0.0.1:5000"

    db_path: Path = BASE_DIR / "cog_host.db"
    audit_salt_path: Path = BASE_DIR / ".audit_salt"


def validate_startup(s: "Settings") -> None:
    if s.bind_lan and not s.auth_password_hash:
        raise RuntimeError(
            "BIND_LAN=true requires AUTH_PASSWORD_HASH to be set. "
            "Refusing to start unauthenticated on the LAN."
        )


settings = Settings()
validate_startup(settings)
