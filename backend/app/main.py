"""Versioned FastAPI application for EOR Atlas."""
from __future__ import annotations
import logging, re
from typing import Any
from uuid import uuid4
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from app.auth import AuthenticationError, OIDCAuthenticator
from app.config import settings
from app.history import HistoryRepository, HistoryUnavailable
from app.schemas import EvaluationRequest, EvaluationResponse, HistoryRecord
from app.services import EORAtlasEngine, EngineUnavailable
logger=logging.getLogger("eor_atlas.api")
def create_app(*,engine:Any|None=None,history:Any|None=None,authenticator:Any|None=None)->FastAPI:
    engine_service=engine or EORAtlasEngine()
    history_repository=history or HistoryRepository()
    auth_service=authenticator or OIDCAuthenticator(settings)
    app=FastAPI(title="EOR Atlas API",version="0.2.0",
        description="Internal API for EOR Atlas engineering screening, hybrid decision support and history.",
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None if settings.is_production else "/redoc",
        openapi_url=None if settings.is_production else "/openapi.json")
    def require_identity(request:Request)->dict[str,Any]:
        try: return auth_service.authenticate(request.headers.get("authorization"))
        except AuthenticationError as exc:
            headers={"WWW-Authenticate":"Bearer"} if exc.status_code==401 else None
            code="authentication_required" if exc.status_code==401 else "identity_not_configured" if exc.status_code==503 else "insufficient_scope"
            raise HTTPException(status_code=exc.status_code,detail={"code":code,"message":str(exc)},headers=headers) from exc
    @app.middleware("http")
    async def response_safety(request:Request,call_next):
        supplied=request.headers.get("x-correlation-id","").strip()
        correlation=supplied if re.fullmatch(r"[A-Za-z0-9._:-]{1,128}",supplied) else str(uuid4())
        try: response=await call_next(request)
        except Exception:
            logger.exception("Unhandled API exception correlation_id=%s",correlation)
            response=JSONResponse(status_code=500,content={"error":{"code":"internal_error","message":"The request could not be completed."}})
        response.headers["X-Correlation-ID"]=correlation
        response.headers["X-Content-Type-Options"]="nosniff"
        response.headers["X-Frame-Options"]="DENY"
        response.headers["Referrer-Policy"]="no-referrer"
        if request.url.path.startswith(settings.api_prefix): response.headers["Cache-Control"]="no-store"
        return response
    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request:Request,exc:RequestValidationError):
        return JSONResponse(status_code=422,content={"error":{"code":"invalid_request","message":"Request validation failed.",
            "details":[{"location":[str(p) for p in item.get("loc",[])],"type":item.get("type")} for item in exc.errors()]}})
    @app.exception_handler(HTTPException)
    async def http_error_handler(request:Request,exc:HTTPException):
        detail=exc.detail if isinstance(exc.detail,dict) else {}
        return JSONResponse(status_code=exc.status_code,headers=exc.headers,content={"error":{"code":str(detail.get("code","http_error")),
            "message":str(detail.get("message","The request could not be completed."))}})
    @app.exception_handler(Exception)
    async def unhandled_error_handler(request:Request,exc:Exception):
        logger.exception("Unhandled API exception")
        return JSONResponse(status_code=500,content={"error":{"code":"internal_error","message":"The request could not be completed."}})
    @app.get("/api/v1/health/live",tags=["health"])
    def live()->dict[str,str]: return {"status":"alive"}
    @app.get("/api/v1/health/ready",tags=["health"],dependencies=[Depends(require_identity)])
    def ready()->dict[str,Any]:
        try: status=engine_service.readiness()
        except Exception:
            logger.exception("Readiness check failed")
            status={"ready":False,"reason":"engine_unavailable"}
        history_status=history_repository.health() if hasattr(history_repository,"health") else {"configured":False,"readable":False,"schema_valid":False,"record_count":None}
        if not status.get("ready"): raise HTTPException(status_code=503,detail={"code":"not_ready","message":"Required EOR Atlas services are not ready."})
        return {"status":"ready",**status,"history":history_status}
    @app.post("/api/v1/screening/evaluate",response_model=EvaluationResponse,tags=["screening"],dependencies=[Depends(require_identity)])
    def evaluate_screening(payload:EvaluationRequest)->dict[str,Any]:
        try: result=engine_service.screen(payload.inputs,payload.formation)
        except EngineUnavailable as exc: raise HTTPException(status_code=503,detail={"code":"screening_unavailable","message":str(exc)}) from exc
        except ValueError as exc: raise HTTPException(status_code=422,detail={"code":"invalid_engineering_input","message":str(exc)}) from exc
        return {"run_id":engine_service.new_run_id(),"mode":"engineering","field_id":payload.field_id,"formation":payload.formation,
            "screening":result,"hybrid":None,"model":None,"history":{"persisted":False,"reason":"history writes remain disabled pending database-owner approval"}}
    @app.post("/api/v1/intelligence/evaluate",response_model=EvaluationResponse,tags=["intelligence"],dependencies=[Depends(require_identity)])
    def evaluate_hybrid(payload:EvaluationRequest)->dict[str,Any]:
        try: result=engine_service.hybrid(payload.inputs,payload.formation)
        except EngineUnavailable as exc: raise HTTPException(status_code=503,detail={"code":"hybrid_unavailable","message":str(exc)}) from exc
        except ValueError as exc: raise HTTPException(status_code=422,detail={"code":"invalid_engineering_input","message":str(exc)}) from exc
        return {"run_id":engine_service.new_run_id(),"mode":"hybrid","field_id":payload.field_id,"formation":payload.formation,
            "screening":result.get("screening",{}),"hybrid":result.get("hybrid",{}),"model":result.get("model_info",{}),
            "history":{"persisted":False,"reason":"history writes remain disabled pending database-owner approval"}}
    @app.get("/api/v1/history",response_model=list[HistoryRecord],tags=["history"],dependencies=[Depends(require_identity)])
    def list_history(limit:int=Query(default=50,ge=1,le=100),offset:int=Query(default=0,ge=0))->list[dict[str,Any]]:
        try: return history_repository.list(limit=limit,offset=offset)
        except HistoryUnavailable as exc: raise HTTPException(status_code=503,detail={"code":"history_unavailable","message":str(exc)}) from exc
    @app.get("/api/v1/history/health",tags=["history"],dependencies=[Depends(require_identity)])
    def history_health()->dict[str,Any]: return history_repository.health()
    @app.get("/api/v1/history/{run_id}",response_model=HistoryRecord,tags=["history"],dependencies=[Depends(require_identity)])
    def get_history(run_id:int)->dict[str,Any]:
        if run_id<1: raise HTTPException(status_code=422,detail={"code":"invalid_run_id","message":"run_id must be positive"})
        try: record=history_repository.get(run_id)
        except HistoryUnavailable as exc: raise HTTPException(status_code=503,detail={"code":"history_unavailable","message":str(exc)}) from exc
        if record is None: raise HTTPException(status_code=404,detail={"code":"history_not_found","message":"History record was not found."})
        return record
    if settings.allowed_origins:
        from fastapi.middleware.cors import CORSMiddleware
        if settings.is_production and "*" in settings.allowed_origins: raise RuntimeError("Wildcard CORS origins are not allowed in production.")
        app.add_middleware(CORSMiddleware,allow_origins=list(settings.allowed_origins),allow_credentials=True,
            allow_methods=["GET","POST"],allow_headers=["Authorization","Content-Type","X-Correlation-ID"])
    elif settings.is_production: logger.warning("No EOR_ALLOWED_ORIGINS configured; browser cross-origin access is disabled.")
    return app
app=create_app()
