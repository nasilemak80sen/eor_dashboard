"""UI-independent production execution path: engineering -> CatBoost -> fusion."""
from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, Optional
import pandas as pd
from config.settings import settings
from ml.model_service import ModelService
from ml.hybrid_intelligence import HybridDecisionService, build_opportunity_context
from services.engineering_screening import ExcelScreeningService
def _build_legacy_catboost_input(values: Dict[str, Any], formation: str) -> Dict[str, Any]:
    """Build the exact range-based input expected by the current v1 CatBoost artifact."""
    formation_map = {
        "Sandstone": "Sandstone",
        "Carbonate": "Carbonates",
        "Carbonates": "Carbonates",
        "Unconsolidated sands": "Unconsolidated sands",
    }
    mapped = formation_map.get(formation)
    if mapped is None:
        raise ValueError(f"Unsupported formation: {formation}")

    required = ["depth_ft", "porosity_pct", "perm_md", "api", "visc_cp", "so_pct"]
    missing = [key for key in required if values.get(key) is None]
    if missing:
        raise KeyError(f"Missing CatBoost inputs: {missing}")

    def positive(key: str) -> float:
        value = float(values[key])
        if value <= 0:
            raise ValueError(f"{key} must be greater than zero.")
        return value

    depth = positive("depth_ft")
    porosity = float(values["porosity_pct"])
    permeability = positive("perm_md")
    api = float(values["api"])
    viscosity = positive("visc_cp")
    oil_saturation = float(values["so_pct"])

    if not 0 <= porosity <= 100:
        raise ValueError("Porosity must be between 0 and 100%.")
    if not 0 <= api <= 100:
        raise ValueError("API gravity must be between 0 and 100°.")
    if not 0 <= oil_saturation <= 100:
        raise ValueError("Oil saturation must be between 0 and 100%.")

    return {
        "depth_min_ft": depth,
        "depth_max_ft": depth,
        "porosity_min_pct": porosity,
        "porosity_max_pct": porosity,
        "perm_min_md": permeability,
        "perm_max_md": permeability,
        "api_min": api,
        "api_max": api,
        "visc_min_cp": viscosity,
        "visc_max_cp": viscosity,
        "so_min_pct": oil_saturation,
        "so_max_pct": oil_saturation,
        "formation_category": mapped,
    }

class EORAtlasExecutionService:
    def __init__(self, model_service: Any = None, workbook_path: Path | None = None):
        self.workbook_path = Path(workbook_path or settings.workbook_path)
        self.screening_service = ExcelScreeningService()
        self._model_service = model_service
        self._model_load_error: str | None = None
        if self._model_service is None:
            try: self._model_service = ModelService()
            except Exception as exc: self._model_load_error = type(exc).__name__

    def _workbook_sheets(self) -> list[str]:
        if not self.workbook_path.is_file(): return []
        try: return list(pd.ExcelFile(self.workbook_path).sheet_names)
        except Exception: return []

    def readiness(self) -> dict[str, Any]:
        sheets = self._workbook_sheets()
        model_ready = bool(self._model_service and self._model_service.is_loaded())
        return {"ready": bool(sheets), "workbook_ready": bool(sheets), "model_ready": model_ready,
                "reason": None if sheets else "workbook_unavailable"}

    def screen(self, inputs: Dict[str, Any], formation: str) -> Dict[str, Any]:
        if not self._workbook_sheets(): raise RuntimeError("Engineering workbook is unavailable.")
        return self.screening_service.screen(dict(inputs), formation)

    def hybrid(self, inputs: Dict[str, Any], formation: str) -> Dict[str, Any]:
        screening_result = self.screen(inputs, formation)
        model_service = self._model_service
        if model_service is None or not model_service.is_loaded():
            raise RuntimeError("CatBoost model is unavailable; hybrid evaluation is disabled.")
        ml_available = False
        ml_probabilities: Dict[str, float] = {}
        ml_top3 = []
        model_info: Dict[str, Any] = {}
        ml_error: Optional[str] = None
        try:
            ml_available = bool(model_service.is_loaded())
            if ml_available:
                prediction = model_service.predict(_build_legacy_catboost_input(inputs, formation))
                if not prediction.success: raise RuntimeError(prediction.warning or "CatBoost prediction failed.")
                ml_top3 = list(prediction.top_n(3))
                ml_probabilities = {str(candidate.technique): float(candidate.probability) for candidate in prediction.candidates}
                model_info = model_service.get_model_info()
        except Exception as exc:
            ml_available = False
            ml_error = str(exc)
        hybrid_result = HybridDecisionService().fuse(
            screening_result, ml_probabilities, top_n=3,
            opportunity_context=build_opportunity_context(inputs))
        return {"formation": formation, "inputs": inputs, "screening": screening_result,
                "ml_available": ml_available, "ml_probabilities": ml_probabilities,
                "ml_top3": ml_top3, "ml_error": ml_error, "model_info": model_info,
                "hybrid": hybrid_result}
