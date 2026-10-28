"""Compatibility adapter for the existing EOR Atlas execution layer.

This adapter is intentionally thin: it calls the current screening and hybrid
services instead of reimplementing engineering rules. The existing execution
modules still import Streamlit; fully separating those imports is a tracked
refactor, not something this adapter pretends has already been completed.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPOSITORY_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


class EngineUnavailable(RuntimeError):
    """Raised when existing EOR Atlas services cannot be initialized."""


class EORAtlasEngine:
    def __init__(self) -> None:
        self._hybrid_app: Any = None
        self._app_module: Any = None
        self._services: dict[str, Any] | None = None
        self._import_error: str | None = None

    def _load(self) -> None:
        if self._hybrid_app is not None and self._services is not None:
            return
        try:
            hybrid_app = importlib.import_module("hybrid_app")
            services = hybrid_app.initialize_services()
            if not services.get("workbook_sheets"):
                raise EngineUnavailable("Engineering workbook is unavailable.")
            if not services.get("model_loaded"):
                # Engineering-only screening remains usable without CatBoost.
                services["model_loaded"] = False
            self._hybrid_app = hybrid_app
            self._app_module = importlib.import_module("app_2")
            self._services = services
            self._import_error = None
        except Exception as exc:
            self._import_error = type(exc).__name__
            raise EngineUnavailable(
                "EOR Atlas services are not ready. Check approved workbook and model configuration."
            ) from exc

    def readiness(self) -> dict[str, Any]:
        try:
            self._load()
        except EngineUnavailable:
            return {
                "ready": False,
                "workbook_ready": False,
                "model_ready": False,
                "reason": "engine_unavailable",
            }
        assert self._services is not None
        return {
            "ready": bool(self._services.get("workbook_sheets")),
            "workbook_ready": bool(self._services.get("workbook_sheets")),
            "model_ready": bool(self._services.get("model_loaded")),
            "reason": None if self._services.get("workbook_sheets") else "workbook_unavailable",
        }

    def screen(self, inputs: dict[str, Any], formation: str) -> dict[str, Any]:
        self._load()
        assert self._app_module is not None
        result = self._app_module.ExcelScreeningService().screen(dict(inputs), formation)
        if not isinstance(result, dict) or not isinstance(result.get("results"), list):
            raise EngineUnavailable("Engineering screening returned an unexpected response.")
        return result

    def hybrid(self, inputs: dict[str, Any], formation: str) -> dict[str, Any]:
        self._load()
        assert self._hybrid_app is not None and self._services is not None
        if not self._services.get("model_loaded"):
            raise EngineUnavailable("CatBoost model is unavailable; hybrid evaluation is disabled.")
        result = self._hybrid_app.run_eor_intelligence(self._services, dict(inputs), formation)
        if not isinstance(result, dict) or not isinstance(result.get("screening"), dict):
            raise EngineUnavailable("Hybrid intelligence returned an unexpected response.")
        return result

    @staticmethod
    def new_run_id() -> str:
        return str(uuid4())
