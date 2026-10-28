"""FastAPI adapter for the shared UI-independent EOR Atlas services."""
from __future__ import annotations
from typing import Any
from uuid import uuid4
import sys
from pathlib import Path
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPOSITORY_ROOT / "src"
if str(SRC_DIR) not in sys.path: sys.path.insert(0, str(SRC_DIR))
from services.hybrid_evaluation import EORAtlasExecutionService
class EngineUnavailable(RuntimeError):
    """Raised when the shared EOR Atlas execution services are unavailable."""
class EORAtlasEngine:
    def __init__(self, execution: EORAtlasExecutionService | None = None) -> None:
        self._execution = execution
    def _load(self) -> EORAtlasExecutionService:
        if self._execution is None: self._execution = EORAtlasExecutionService()
        return self._execution
    def readiness(self) -> dict[str, Any]:
        try: return self._load().readiness()
        except Exception: return {"ready": False, "workbook_ready": False, "model_ready": False, "reason": "engine_unavailable"}
    def screen(self, inputs: dict[str, Any], formation: str) -> dict[str, Any]:
        try: return self._load().screen(inputs, formation)
        except RuntimeError as exc: raise EngineUnavailable(str(exc)) from exc
    def hybrid(self, inputs: dict[str, Any], formation: str) -> dict[str, Any]:
        try: return self._load().hybrid(inputs, formation)
        except RuntimeError as exc: raise EngineUnavailable(str(exc)) from exc
    @staticmethod
    def new_run_id() -> str: return str(uuid4())
