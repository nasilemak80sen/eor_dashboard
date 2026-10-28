"""Environment-driven API configuration. Never performs DB mutations."""
from __future__ import annotations
import os
from dataclasses import dataclass
from pathlib import Path
@dataclass(frozen=True)
class Settings:
    environment: str = os.getenv("EOR_ENV", "development").strip().lower()
    history_db_path: Path | None = (Path(os.environ["EOR_HISTORY_DB_PATH"]).expanduser().resolve() if os.getenv("EOR_HISTORY_DB_PATH") else None)
    api_prefix: str = os.getenv("EOR_API_PREFIX", "/api/v1").strip() or "/api/v1"
    allowed_origins: tuple[str, ...] = tuple(origin.strip() for origin in os.getenv("EOR_ALLOWED_ORIGINS", "").split(",") if origin.strip())
    oidc_issuer: str | None = os.getenv("EOR_OIDC_ISSUER", "").strip() or None
    oidc_audience: str | None = os.getenv("EOR_OIDC_AUDIENCE", "").strip() or None
    oidc_jwks_url: str | None = os.getenv("EOR_OIDC_JWKS_URL", "").strip() or None
    oidc_required_scope: str | None = os.getenv("EOR_OIDC_REQUIRED_SCOPE", "").strip() or None
    @property
    def oidc_configured(self) -> bool:
        return bool(self.oidc_issuer and self.oidc_audience and self.oidc_jwks_url)
    @property
    def is_production(self) -> bool:
        return self.environment in {"production", "prod"}
settings = Settings()
