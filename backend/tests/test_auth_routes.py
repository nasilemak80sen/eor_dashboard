from __future__ import annotations
from fastapi.testclient import TestClient
from app.auth import AuthenticationError
from app.main import create_app

VALID_INPUTS = {
    "depth_ft": 5000, "reservoir_pressure": 2500, "temperature_c": 95, "visc_cp": 2,
    "api": 35, "perm_md": 100, "porosity_frac": 0.2, "porosity_pct": 20, "so_pct": 55,
}
class FakeEngine:
    def readiness(self): return {"ready": True}
    def new_run_id(self): return "test-run"
    def screen(self, inputs, formation): return {"results": []}
    def hybrid(self, inputs, formation): return {"screening": {}, "hybrid": {}, "model_info": {}}
class FakeHistory:
    def health(self): return {"configured": False, "readable": False, "schema_valid": False, "record_count": None}
    def list(self, *, limit=50, offset=0): return []
    def get(self, run_id): return None
class EnforcedAuthenticator:
    def authenticate(self, authorization):
        if authorization != "Bearer valid-test-token": raise AuthenticationError()
        return {"sub": "test-user"}

def test_evaluation_route_requires_bearer_identity():
    client = TestClient(create_app(engine=FakeEngine(), history=FakeHistory(), authenticator=EnforcedAuthenticator()))
    payload = {"formation": "Sandstone", "inputs": VALID_INPUTS}
    denied = client.post("/api/v1/screening/evaluate", json=payload)
    assert denied.status_code == 401
    assert denied.headers["www-authenticate"] == "Bearer"
    allowed = client.post("/api/v1/screening/evaluate", headers={"Authorization": "Bearer valid-test-token"}, json=payload)
    assert allowed.status_code == 200

def test_history_route_requires_bearer_identity():
    client = TestClient(create_app(engine=FakeEngine(), history=FakeHistory(), authenticator=EnforcedAuthenticator()))
    assert client.get("/api/v1/history").status_code == 401
    assert client.get("/api/v1/history", headers={"Authorization": "Bearer valid-test-token"}).status_code == 200

def test_api_responses_include_safety_headers_and_correlation_id():
    client = TestClient(create_app(engine=FakeEngine(), history=FakeHistory(), authenticator=EnforcedAuthenticator()))
    response = client.get("/api/v1/health/live", headers={"X-Correlation-ID": "phase3-test"})
    assert response.headers["x-correlation-id"] == "phase3-test"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["cache-control"] == "no-store"
