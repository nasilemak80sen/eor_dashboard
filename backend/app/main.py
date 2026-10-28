"""FastAPI application for the EOR Atlas Vue migration."""
from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.config import settings
from app.history import HistoryRepository, HistoryUnavailable
from app.schemas import EvaluationRequest, EvaluationResponse, HistoryRecord
from app.services import EORAtlasEngine, EngineUnavailable

logger = logging.getLogger("eor_atlas.api")


def create_app(*, engine: Any | None = None, history: Any | None = None) -> FastAPI:
    engine_service = engine or EORAtlasEngine()
    history_repository = history or HistoryRepository()
    app = FastAPI(
        title="EOR Atlas API",
        version="0.1.0",
        description="Internal API boundary for EOR Atlas engineering screening and hybrid decision support.",
    )

    @app.middleware("http")
    async def correlation_id(request: Request, call_next):
        response = await call_next(request)
        supplied = request.headers.get("x-correlation-id", "").strip()
        correlation = supplied[:128] if supplied else str(uuid4())
        response.headers["X-Correlation-ID"] = correlation
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "invalid_request",
                    "message": "Request validation failed.",
                    "details": [
                        {"location": [str(p) for p in item.get("loc", [])], "type": item.get("type")}
                        for item in exc.errors()
                    ],
                }
            },
        )

    @app.exception_handler(HTTPException)
    async def http_error_handler(request: Request, exc: HTTPException):
        detail = exc.detail if isinstance(exc.detail, dict) else {}
        return JSONResponse(
            status_code=exc.status_code,
            headers=exc.headers,
            content={
                "error": {
                    "code": str(detail.get("code", "http_error")),
                    "message": str(detail.get("message", "The request could not be completed.")),
                }
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception):
        logger.exception("Unhandled API exception")
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "internal_error", "message": "The request could not be completed."}},
        )

    @app.get("/api/v1/health/live", tags=["health"])
    def live() -> dict[str, str]:
        return {"status": "alive"}

    @app.get("/api/v1/health/ready", tags=["health"])
    def ready() -> dict[str, Any]:
        try:
            status = engine_service.readiness()
        except Exception:
            logger.exception("Readiness check failed")
            status = {"ready": False, "reason": "engine_unavailable"}
        if not status.get("ready"):
            raise HTTPException(
                status_code=503,
                detail={"code": "not_ready", "message": "Required EOR Atlas services are not ready."},
            )
        return {"status": "ready", **status}

    @app.post("/api/v1/screening/evaluate", response_model=EvaluationResponse, tags=["screening"])
    def evaluate_screening(payload: EvaluationRequest) -> dict[str, Any]:
        try:
            result = engine_service.screen(payload.inputs, payload.formation)
        except EngineUnavailable as exc:
            raise HTTPException(status_code=503, detail={"code": "screening_unavailable", "message": str(exc)}) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail={"code": "invalid_engineering_input", "message": str(exc)}) from exc
        return {
            "run_id": engine_service.new_run_id(),
            "mode": "engineering",
            "field_id": payload.field_id,
            "formation": payload.formation,
            "screening": result,
            "hybrid": None,
            "model": None,
            "history": {"persisted": False, "reason": "history writes are disabled until database authority is confirmed"},
        }

    @app.post("/api/v1/intelligence/evaluate", response_model=EvaluationResponse, tags=["intelligence"])
    def evaluate_hybrid(payload: EvaluationRequest) -> dict[str, Any]:
        try:
            result = engine_service.hybrid(payload.inputs, payload.formation)
        except EngineUnavailable as exc:
            raise HTTPException(status_code=503, detail={"code": "hybrid_unavailable", "message": str(exc)}) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail={"code": "invalid_engineering_input", "message": str(exc)}) from exc
        return {
            "run_id": engine_service.new_run_id(),
            "mode": "hybrid",
            "field_id": payload.field_id,
            "formation": payload.formation,
            "screening": result.get("screening", {}),
            "hybrid": result.get("hybrid", {}),
            "model": result.get("model_info", {}),
            "history": {"persisted": False, "reason": "history writes are disabled until database authority is confirmed"},
        }

    @app.get("/api/v1/history", response_model=list[HistoryRecord], tags=["history"])
    def list_history(
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
    ) -> list[dict[str, Any]]:
        try:
            return history_repository.list(limit=limit, offset=offset)
        except HistoryUnavailable as exc:
            raise HTTPException(status_code=503, detail={"code": "history_unavailable", "message": str(exc)}) from exc

    @app.get("/api/v1/history/{run_id}", response_model=HistoryRecord, tags=["history"])
    def get_history(run_id: int) -> dict[str, Any]:
        if run_id < 1:
            raise HTTPException(status_code=422, detail={"code": "invalid_run_id", "message": "run_id must be positive"})
        try:
            record = history_repository.get(run_id)
        except HistoryUnavailable as exc:
            raise HTTPException(status_code=503, detail={"code": "history_unavailable", "message": str(exc)}) from exc
        if record is None:
            raise HTTPException(status_code=404, detail={"code": "history_not_found", "message": "History record was not found."})
        return record

    if settings.allowed_origins:
        from fastapi.middleware.cors import CORSMiddleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(settings.allowed_origins),
            allow_credentials=True,
            allow_methods=["GET", "POST"],
            allow_headers=["Authorization", "Content-Type", "X-Correlation-ID"],
        )

    return app


app = create_app()
