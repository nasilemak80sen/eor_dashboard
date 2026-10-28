"""Read-only, schema-aware access to the explicitly configured screening history DB."""
from __future__ import annotations
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any
from app.config import settings
class HistoryUnavailable(RuntimeError):
    """Raised when an approved history database is not configured or readable."""
_REQUIRED_COLUMNS = {"id","timestamp","formation","status","recommended_technique","recommendation_status","recommendation_score","recommendation_mode"}
_OPTIONAL_COLUMNS = {"user","depth_ft","porosity_pct","perm_md","api","visc_cp","so_pct","data_quality_status","data_readiness_pct","input_payload","rule_trace","assumptions","workbook_version","rule_version","fuzzy_model_version","model_version","evidence_summary"}
class HistoryRepository:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path if db_path is not None else settings.history_db_path
    def _connect(self) -> sqlite3.Connection:
        if self.db_path is None: raise HistoryUnavailable("History database is not configured.")
        if not self.db_path.is_file(): raise HistoryUnavailable("Configured history database is unavailable.")
        uri = self.db_path.resolve().as_uri() + "?mode=ro"
        try:
            con = sqlite3.connect(uri, uri=True, timeout=3)
            con.row_factory = sqlite3.Row
            return con
        except sqlite3.Error as exc: raise HistoryUnavailable("History database cannot be opened read-only.") from exc
    @staticmethod
    def _columns(con: sqlite3.Connection) -> set[str]:
        try: available = {row["name"] for row in con.execute("PRAGMA table_info(screening_runs)").fetchall()}
        except sqlite3.Error as exc: raise HistoryUnavailable("History schema could not be inspected.") from exc
        if not _REQUIRED_COLUMNS.issubset(available):
            missing = sorted(_REQUIRED_COLUMNS - available)
            raise HistoryUnavailable("History schema does not match the supported read contract: " + ", ".join(missing))
        return available
    @staticmethod
    def _select_columns(available: set[str]) -> str:
        columns = sorted(_OPTIONAL_COLUMNS.intersection(available))
        return ", ".join(["id","timestamp","formation","status","recommended_technique","recommendation_status","recommendation_score","recommendation_mode",*columns])
    @staticmethod
    def _decode_record(record: dict[str, Any]) -> dict[str, Any]:
        for key in ("input_payload","rule_trace","assumptions","evidence_summary"):
            value = record.get(key)
            if isinstance(value, str):
                try: record[key] = json.loads(value)
                except (json.JSONDecodeError, TypeError): pass
        return record
    def list(self, *, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        if not 1 <= limit <= 100: raise ValueError("limit must be between 1 and 100")
        if offset < 0: raise ValueError("offset must be non-negative")
        try:
            with closing(self._connect()) as con:
                available = self._columns(con)
                sql = f"SELECT {self._select_columns(available)} FROM screening_runs ORDER BY id DESC LIMIT ? OFFSET ?"
                return [self._decode_record(dict(row)) for row in con.execute(sql, (limit, offset)).fetchall()]
        except sqlite3.Error as exc: raise HistoryUnavailable("History records could not be read.") from exc
    def get(self, run_id: int) -> dict[str, Any] | None:
        if run_id < 1: raise ValueError("run_id must be positive")
        try:
            with closing(self._connect()) as con:
                available = self._columns(con)
                sql = f"SELECT {self._select_columns(available)} FROM screening_runs WHERE id = ?"
                row = con.execute(sql, (run_id,)).fetchone()
                return self._decode_record(dict(row)) if row else None
        except sqlite3.Error as exc: raise HistoryUnavailable("History record could not be read.") from exc
    def health(self) -> dict[str, Any]:
        if self.db_path is None: return {"configured":False,"readable":False,"schema_valid":False,"record_count":None}
        try:
            with closing(self._connect()) as con:
                self._columns(con)
                count = int(con.execute("SELECT COUNT(*) FROM screening_runs").fetchone()[0])
            return {"configured":True,"readable":True,"schema_valid":True,"record_count":count}
        except (HistoryUnavailable, sqlite3.Error):
            return {"configured":True,"readable":False,"schema_valid":False,"record_count":None}
