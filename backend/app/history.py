"""Read-only history access; never creates or migrates a database."""
from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from app.config import settings


class HistoryUnavailable(RuntimeError):
    """Raised when an approved history database is not configured or readable."""


_COLUMNS = {
    "id", "timestamp", "formation", "status", "recommended_technique",
    "recommendation_status", "recommendation_score", "recommendation_mode",
}


class HistoryRepository:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or settings.history_db_path

    def _connect(self) -> sqlite3.Connection:
        if self.db_path is None:
            raise HistoryUnavailable("History database is not configured.")
        if not self.db_path.is_file():
            raise HistoryUnavailable("Configured history database is unavailable.")
        # SQLite URI read-only mode prevents accidental creation or mutation.
        uri = self.db_path.resolve().as_uri() + "?mode=ro"
        try:
            return sqlite3.connect(uri, uri=True, timeout=3)
        except sqlite3.Error as exc:
            raise HistoryUnavailable("History database cannot be opened read-only.") from exc

    @staticmethod
    def _ensure_schema(con: sqlite3.Connection) -> None:
        con.row_factory = sqlite3.Row
        try:
            available = {
                row["name"]
                for row in con.execute("PRAGMA table_info(screening_runs)").fetchall()
            }
        except sqlite3.Error as exc:
            raise HistoryUnavailable("History schema could not be inspected.") from exc
        if not _COLUMNS.issubset(available):
            raise HistoryUnavailable("History schema does not match the supported read contract.")

    def list(self, *, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        if offset < 0:
            raise ValueError("offset must be non-negative")
        try:
            with closing(self._connect()) as con:
                self._ensure_schema(con)
                sql = (
                    "SELECT id, timestamp, formation, status, recommended_technique, "
                    "recommendation_status, recommendation_score, recommendation_mode "
                    "FROM screening_runs ORDER BY id DESC LIMIT ? OFFSET ?"
                )
                return [dict(row) for row in con.execute(sql, (limit, offset)).fetchall()]
        except sqlite3.Error as exc:
            raise HistoryUnavailable("History records could not be read.") from exc

    def get(self, run_id: int) -> dict[str, Any] | None:
        try:
            with closing(self._connect()) as con:
                self._ensure_schema(con)
                row = con.execute(
                    "SELECT id, timestamp, formation, status, recommended_technique, "
                    "recommendation_status, recommendation_score, recommendation_mode "
                    "FROM screening_runs WHERE id = ?",
                    (run_id,),
                ).fetchone()
                return dict(row) if row else None
        except sqlite3.Error as exc:
            raise HistoryUnavailable("History record could not be read.") from exc
