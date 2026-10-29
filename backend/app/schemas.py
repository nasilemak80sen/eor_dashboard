"""Versioned API contracts. Engineering calculations remain in Python."""
from __future__ import annotations
import math
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator
Formation = Literal["Sandstone", "Carbonate", "Carbonates", "Unconsolidated sands"]
class EvaluationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field_id: str | None = Field(default=None, max_length=200)
    formation: Formation
    inputs: dict[str, Any] = Field(min_length=1, max_length=100)
    include_probabilities: bool = True
    @field_validator("inputs")
    @classmethod
    def validate_input_values(cls, values: dict[str, Any]) -> dict[str, Any]:
        required = {"depth_ft","reservoir_pressure","temperature_c","visc_cp","api","perm_md","porosity_frac","porosity_pct","so_pct"}
        missing = sorted(required.difference(values))
        if missing: raise ValueError(f"Missing required reservoir inputs: {', '.join(missing)}")
        bounds = {"depth_ft":(0,100000),"reservoir_pressure":(0,100000),"temperature_c":(-100,500),
                  "visc_cp":(0,1000000),"api":(0,100),"perm_md":(0,1000000000),"porosity_frac":(0,1),
                  "porosity_pct":(0,100),"so_pct":(0,100)}
        for key,(minimum,maximum) in bounds.items():
            value=values[key]
            if isinstance(value,bool) or not isinstance(value,(int,float)): raise ValueError(f"{key} must be numeric")
            if not math.isfinite(float(value)): raise ValueError(f"{key} must be finite")
            if float(value)<minimum or float(value)>maximum: raise ValueError(f"{key} must be between {minimum} and {maximum}")
        if values["depth_ft"]<=0: raise ValueError("depth_ft must be greater than zero")
        if values["visc_cp"]<=0: raise ValueError("visc_cp must be greater than zero")
        if values["perm_md"]<=0: raise ValueError("perm_md must be greater than zero")
        if not math.isclose(float(values["porosity_frac"])*100,float(values["porosity_pct"]),rel_tol=0.0,abs_tol=0.11):
            raise ValueError("porosity_frac and porosity_pct must represent the same porosity")
        return values
class TechniqueResult(BaseModel):
    model_config = ConfigDict(extra="allow")
    technique: str
    status: str | None = None
    score: float | None = None
    eligible: bool | None = None
    reasons: list[str] = Field(default_factory=list)
class EvaluationResponse(BaseModel):
    run_id: str
    mode: Literal["engineering","hybrid"]
    field_id: str | None = None
    formation: str
    screening: dict[str, Any]
    hybrid: dict[str, Any] | None = None
    model: dict[str, Any] | None = None
    history: dict[str, Any] | None = None
class ErrorResponse(BaseModel):
    error: dict[str, Any]
class HistoryRecord(BaseModel):
    id: int
    timestamp: str | None = None
    formation: str | None = None
    status: str | None = None
    recommended_technique: str | None = None
    recommendation_status: str | None = None
    recommendation_score: float | None = None
    recommendation_mode: str | None = None
    user: str | None = None
    depth_ft: float | None = None
    porosity_pct: float | None = None
    perm_md: float | None = None
    api: float | None = None
    visc_cp: float | None = None
    so_pct: float | None = None
    data_quality_status: str | None = None
    data_readiness_pct: float | None = None
    input_payload: Any | None = None
    rule_trace: Any | None = None
    assumptions: Any | None = None
    workbook_version: str | None = None
    rule_version: str | None = None
    fuzzy_model_version: str | None = None
    model_version: str | None = None
    evidence_summary: Any | None = None
