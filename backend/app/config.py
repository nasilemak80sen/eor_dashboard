"""Environment-driven configuration for the EOR Atlas API.

No database is migrated or modified at application startup. Runtime data paths
must be supplied explicitly for internal deployment.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    environment: str = os.getenv("EOR_ENV", "development")
    history_db_path: Path | None = (
        Path(os.environ["EOR_HISTORY_DB_PATH"]).expanduser().resolve()
        if os.getenv("EOR_HISTORY_DB_PATH")
        else None
    )
    api_prefix: str = os.getenv("EOR_API_PREFIX", "/api/v1")
    allowed_origins: tuple[str, ...] = tuple(
        origin.strip()
        for origin in os.getenv("EOR_ALLOWED_ORIGINS", "").split(",")
        if origin.strip()
    )


settings = Settings()
