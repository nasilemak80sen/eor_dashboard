"""Persistence and read-model helpers for EOR Atlas screening report cards.

A screening run is the durable record of one submitted decision case. The
exact input snapshot is preserved alongside independent engineering, CatBoost,
and hybrid decision records so Historical EOR can reproduce what EOR Atlas
actually recommended at the time of execution.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from data.database import DatabaseManager
from data.queries import ScreeningRepository


HYBRID_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS hybrid_results (
    id INTEGER PRIMARY KEY,
    screening_id INTEGER NOT NULL,
    rank INTEGER NOT NULL,
    technique VARCHAR(255) NOT NULL,
    hybrid_score FLOAT,
    catboost_probability FLOAT,
    engineering_score FLOAT,
    engineering_status VARCHAR(50),
    is_recommended BOOLEAN DEFAULT 0,
    details TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
"""


def _json_safe(value: Any) -> Any:
    """Return a recursively JSON-serialisable representation."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "item"):
        try:
            return _json_safe(value.item())
        except Exception:
            pass
    return str(value)


def ensure_history_schema() -> None:
    """Create the small hybrid child table used by the report-card history."""
    session = DatabaseManager.get_session()
    try:
        session.execute(text(HYBRID_TABLE_SQL))
        session.commit()
    finally:
        session.close()


def run_reference(run_id: int, timestamp: Optional[datetime] = None) -> str:
    """Return a stable human-facing report-card reference."""
    year = (timestamp or datetime.utcnow()).year
    return f"EOR-{year}-{int(run_id):06d}"


def _core_inputs(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Extract the mandatory ScreeningRun columns from the full v3 snapshot."""
    return {
        "depth_ft": float(inputs.get("depth_ft", 0.0)),
        "porosity_pct": float(inputs.get("porosity_pct", float(inputs.get("porosity_frac", 0.0)) * 100.0)),
        "perm_md": float(inputs.get("perm_md", 0.0)),
        "api": float(inputs.get("api", 0.0)),
        "visc_cp": float(inputs.get("visc_cp", 0.0)),
        "so_pct": float(inputs.get("so_pct", 0.0)),
    }


def _engineering_map(screening_result: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Convert the deterministic result list into the repository's eligibility schema."""
    rows = screening_result.get("results", []) or []
    return {
        str(row.get("EOR Technique", "Unknown")): {
            "status": row.get("Status", "FAIL"),
            "criteria_passed": None,
            "criteria_total": None,
            "details": _json_safe(row),
        }
        for row in rows
    }


def _best_engineering(screening_result: Dict[str, Any]) -> Dict[str, Any]:
    rows = screening_result.get("results", []) or []
    if not rows:
        return {}
    return dict(rows[0])


def _persist_base_run(
    *,
    inputs: Dict[str, Any],
    formation: str,
    screening_result: Dict[str, Any],
    user: Optional[str],
    mode: str,
    model_version: Optional[str] = None,
) -> Any:
    """Create the root ScreeningRun and preserve its exact input/result trace."""
    session = DatabaseManager.get_session()
    try:
        repo = ScreeningRepository(session)
        core = _core_inputs(inputs)
        row = repo.create(
            formation=formation,
            **core,
            name=None,
            user=user,
            status="completed",
        )

        repo.update_results(
            row.id,
            recommended_technique=_best_engineering(screening_result).get("EOR Technique", ""),
            recommendation_status=_best_engineering(screening_result).get("Status", ""),
            recommendation_score=float(_best_engineering(screening_result).get("Score (%)", 0.0)),
            recommendation_mode=mode,
        )
        repo.update_run_metadata(
            row.id,
            input_payload=_json_safe(inputs),
            rule_trace=_json_safe(screening_result.get("results", [])),
            assumptions={
                "formation": formation,
                "source_sheet": screening_result.get("source_sheet", "Screening"),
            },
            model_version=model_version,
            evidence_summary={
                "run_reference": run_reference(row.id, row.timestamp),
                "record_type": mode,
                "production_path": "Excel Gate -> CatBoost -> Decision Fusion" if mode == "HYBRID" else "Excel Gate",
                "created_at_utc": (row.timestamp or datetime.utcnow()).isoformat(),
            },
        )
        repo.save_eligibility_results(row.id, _engineering_map(screening_result))
        return row
    finally:
        session.close()


def persist_engineering_run(
    inputs: Dict[str, Any],
    formation: str,
    screening_result: Dict[str, Any],
    *,
    user: Optional[str] = None,
) -> Dict[str, Any]:
    """Persist an Engineering Screening submission and return its report-card metadata."""
    row = _persist_base_run(
        inputs=inputs,
        formation=formation,
        screening_result=screening_result,
        user=user,
        mode="ENGINEERING",
    )
    return {
        "id": row.id,
        "reference": run_reference(row.id, row.timestamp),
        "timestamp": row.timestamp,
        "mode": "ENGINEERING",
    }


def persist_hybrid_run(
    result: Dict[str, Any],
    *,
    user: Optional[str] = None,
) -> Dict[str, Any]:
    """Persist Engineering + CatBoost + Hybrid results as one report-card run."""
    screening_result = result.get("screening", {}) or {}
    inputs = result.get("inputs", {}) or {}
    formation = result.get("formation", "Unknown")
    model_info = result.get("model_info", {}) or {}

    row = _persist_base_run(
        inputs=inputs,
        formation=formation,
        screening_result=screening_result,
        user=user,
        mode="HYBRID",
        model_version=str(model_info.get("version") or model_info.get("model_version") or "Unknown"),
    )

    session = DatabaseManager.get_session()
    try:
        repo = ScreeningRepository(session)
        ml_probabilities = result.get("ml_probabilities", {}) or {}
        repo.save_ml_results(row.id, {str(k): float(v) for k, v in ml_probabilities.items()})

        ranking = (result.get("hybrid", {}) or {}).get("ranking", []) or []
        session.execute(text("DELETE FROM hybrid_results WHERE screening_id = :screening_id"), {"screening_id": row.id})
        for rank, item in enumerate(ranking, start=1):
            session.execute(
                text(
                    """INSERT INTO hybrid_results
                    (screening_id, rank, technique, hybrid_score, catboost_probability,
                     engineering_score, engineering_status, is_recommended, details)
                    VALUES (:screening_id, :rank, :technique, :hybrid_score,
                            :catboost_probability, :engineering_score, :engineering_status,
                            :is_recommended, :details)"""
                ),
                {
                    "screening_id": row.id,
                    "rank": rank,
                    "technique": item.get("EOR Technique", ""),
                    "hybrid_score": float(item.get("Hybrid Score", 0.0)),
                    "catboost_probability": float(item.get("CatBoost Probability", 0.0)),
                    "engineering_score": float(item.get("Engineering Score", 0.0)),
                    "engineering_status": item.get("Engineering Status", ""),
                    "is_recommended": rank == 1,
                    "details": json.dumps(_json_safe(item), ensure_ascii=False),
                },
            )

        hybrid = result.get("hybrid", {}) or {}
        recommendation = hybrid.get("recommendation", {}) or {}
        session.execute(
            text("""UPDATE screening_runs
                    SET recommended_technique = :technique,
                        recommendation_status = :status,
                        recommendation_score = :score,
                        recommendation_mode = 'HYBRID',
                        evidence_summary = :evidence
                    WHERE id = :id"""),
            {
                "id": row.id,
                "technique": recommendation.get("EOR Technique", row.recommended_technique),
                "status": recommendation.get("Engineering Status", row.recommendation_status),
                "score": float(recommendation.get("Hybrid Score", row.recommendation_score or 0.0)),
                "evidence": json.dumps(
                    _json_safe({
                        "run_reference": run_reference(row.id, row.timestamp),
                        "record_type": "HYBRID",
                        "production_path": "Excel Gate -> CatBoost -> Decision Fusion",
                        "weights": hybrid.get("weights", {}),
                        "ml_available": result.get("ml_available", False),
                        "ml_error": result.get("ml_error"),
                        "model_info": model_info,
                        "opportunity_context": hybrid.get("opportunity_context", {}),
                    }),
                    ensure_ascii=False,
                ),
            },
        )
        session.commit()
    finally:
        session.close()

    return {
        "id": row.id,
        "reference": run_reference(row.id, row.timestamp),
        "timestamp": row.timestamp,
        "mode": "HYBRID",
    }


def list_report_cards(days: int = 3650) -> List[Any]:
    """Return saved report-card roots newest first."""
    session = DatabaseManager.get_session()
    try:
        return ScreeningRepository(session).get_recent(days=days)
    finally:
        # The returned SQLAlchemy objects have already been populated by the query;
        # detach by keeping the session open only for the rendering turn.
        pass


def get_report_card(run_id: int) -> Optional[Dict[str, Any]]:
    """Load a complete persisted report card by numeric screening id."""
    ensure_history_schema()
    session = DatabaseManager.get_session()
    try:
        repo = ScreeningRepository(session)
        run = repo.get_detail(run_id)
        if run is None:
            return None

        hybrid_rows = session.execute(
            text("""SELECT rank, technique, hybrid_score, catboost_probability,
                          engineering_score, engineering_status, is_recommended, details
                   FROM hybrid_results
                   WHERE screening_id = :screening_id
                   ORDER BY rank"""),
            {"screening_id": run.id},
        ).mappings().all()

        return {
            "run": run,
            "reference": run_reference(run.id, run.timestamp),
            "engineering": [item for item in (run.eligibility_results or [])],
            "ml": [item for item in (run.ml_results or [])],
            "hybrid": [dict(item) for item in hybrid_rows],
        }
    finally:
        # Caller renders immediately, but the ORM objects reference lazy
        # collections. Keep the session alive for that render.
        pass
