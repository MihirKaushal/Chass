from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATABASE_PATH = Path(__file__).resolve().parent / "chass.db"
DEFAULT_DATABASE_URL = f"sqlite:///{DEFAULT_DATABASE_PATH}"
DEFAULT_FRONTEND_URL = "http://localhost:5173"
DEFAULT_TOKEN_SECRET = "chass-local-development-secret"


def _positive_int(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, str(default))))
    except ValueError:
        return default


def _origins(frontend_url: str, include_development: bool) -> tuple[str, ...]:
    configured = os.getenv("ALLOWED_ORIGINS", "")
    values = [
        origin.strip().rstrip("/")
        for origin in configured.split(",")
        if origin.strip()
    ]
    values.append(frontend_url.rstrip("/"))
    if include_development:
        values.extend(["http://localhost:5173", "http://127.0.0.1:5173"])
    return tuple(dict.fromkeys(values))


@dataclass(frozen=True)
class Settings:
    database_url: str
    frontend_url: str
    allowed_origins: tuple[str, ...]
    token_secret: str
    environment: str
    invite_ttl_hours: int
    game_ttl_days: int

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


def get_settings() -> Settings:
    frontend_url = os.getenv("FRONTEND_URL", DEFAULT_FRONTEND_URL).rstrip("/")
    environment = os.getenv("ENVIRONMENT", "development")
    token_secret = os.getenv("TOKEN_SECRET", DEFAULT_TOKEN_SECRET)

    if environment.lower() == "production" and (
        token_secret == DEFAULT_TOKEN_SECRET or len(token_secret) < 32
    ):
        raise RuntimeError(
            "TOKEN_SECRET must be set to a private value of at least 32 characters "
            "in production"
        )

    return Settings(
        database_url=os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL),
        frontend_url=frontend_url,
        allowed_origins=_origins(
            frontend_url,
            include_development=environment.lower() != "production",
        ),
        token_secret=token_secret,
        environment=environment,
        invite_ttl_hours=_positive_int("INVITE_TTL_HOURS", 24),
        game_ttl_days=_positive_int("GAME_TTL_DAYS", 30),
    )
