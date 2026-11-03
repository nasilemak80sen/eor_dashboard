from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app


VALID_INPUTS = {
    "depth_ft": 5000,
    "reservoir_pressure": 2500,
    "temperature_c": 95,
    "visc_cp": 2,
    "api": 35,
    "perm_md": 100,
    "porosity_frac": 0.2,
    "porosity_pct": 20,
    "so_pct": 55,
}


class FakeEngine:
    def readiness(self):
        return {"ready": True, "workbook_ready": True, "model_ready": True}

    def new_run_id(self):
        return "test-run-id"

    def screen(self, inputs, formation):
        return {"results": [{"EOR Technique": "Polymer (HPAM)", "Status": "PASS", "Score (%)": 70}]}

    def hybrid(self, inputs, formation):
        return {
            "screening": {"results": [{"EOR Technique": "CO2 Miscible Flood", "Status": "FAIL (critical)", "Score (%)": 0}]},
            "hybrid": {"recommendation": {"EOR Technique": "Polymer (HPAM)"}, "ranking": []},
            "model_info": {"version": "test-model"},
        }


class FakeHistory:
    def list(self, *, limit=50, offset=0):
        return [{"id": 1, "timestamp": None, "formation": "Sandstone", "status": "completed",
                 "recommended_technique": "Polymer", "recommendation_status": "PASS",
                 "recommendation_score": 70.0, "recommendation_mode": "ENGINEERING"}]

    def get(self, run_id):
        return self.list()[0] if run_id == 1 else None


def client():
    return TestClient(create_app(engine=FakeEngine(), history=FakeHistory()))


def test_liveness_and_readiness():
    c = client()
    assert c.get("/api/v1/health/live").json() == {"status": "alive"}
    assert c.get("/api/v1/health/ready").status_code == 200


def test_screening_returns_engine_results_and_does_not_claim_persistence():
    response = client().post("/api/v1/screening/evaluate", json={
        "formation": "Sandstone", "inputs": VALID_INPUTS
    })
    assert response.status_code == 200
    body = response.json()
    assert body["screening"]["results"][0]["Status"] == "PASS"
    assert body["history"]["persisted"] is False


def test_hybrid_response_preserves_gate_result_and_model_metadata():
    response = client().post("/api/v1/intelligence/evaluate", json={
        "formation": "Sandstone", "inputs": VALID_INPUTS
    })
    assert response.status_code == 200
    body = response.json()
    assert body["screening"]["results"][0]["Status"] == "FAIL (critical)"
    assert body["model"]["version"] == "test-model"


def test_invalid_porosity_pair_is_rejected():
    invalid = {**VALID_INPUTS, "porosity_frac": 0.5}
    response = client().post("/api/v1/screening/evaluate", json={
        "formation": "Sandstone", "inputs": invalid
    })
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"


def test_missing_core_input_is_rejected():
    invalid = {k: v for k, v in VALID_INPUTS.items() if k != "api"}
    response = client().post("/api/v1/screening/evaluate", json={
        "formation": "Sandstone", "inputs": invalid
    })
    assert response.status_code == 422


def test_history_contract():
    c = client()
    assert c.get("/api/v1/history?limit=10").status_code == 200
    assert c.get("/api/v1/history/1").json()["id"] == 1
    assert c.get("/api/v1/history/999").status_code == 404
