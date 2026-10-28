from __future__ import annotations
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "src"))
from fastapi.testclient import TestClient
from app.main import create_app
from app.services import EORAtlasEngine
from services.engineering_screening import ExcelScreeningService
from services.hybrid_evaluation import EORAtlasExecutionService
# Existing UI defaults: migration smoke case only, NOT an approved real case.
CASE_INPUTS = {
 "depth_ft":5000.0,"reservoir_pressure":2500.0,"temperature_c":95.0,"visc_cp":2.0,
 "api":35.0,"perm_md":100.0,"porosity_frac":0.20,"porosity_pct":20.0,"so_pct":55.0,
 "salinity_ppm":50000.0,"hardness_ppm":300.0,"rock_type":"Sandstone","net_pay_m":30.0,
 "heterogeneity":"Moderate","gas_availability":"Yes","oxygen_present":"No","ooip_mmstb":100.0,
 "base_rf_pct":35.0,"drive_mechanism":"Waterflood","drive_multiplier":1.0,"co2_availability":"Yes",
 "mmp_satisfied":"Yes","waterflood_history":"Yes","water_cut_pct":60.0,"field_maturity":"Mature",
 "maturity_factor":1.0,"mobility_ratio":"Favorable","adsorption_risk":"Low","water_handling":"Low",
 "offshore":"No","water_injection_facilities":"Yes","gas_injection_facilities":"Yes","wag_ratio":"1:1",
 "gas_injectivity":"Good","water_injectivity":"Good","gravity_override_risk":"Low",
 "hc_gas_availability":"No","produced_gor_category":"Moderate","gas_reinjectable":"Yes",
 "produced_gor_scf_stb":574.0}
class FakeHistory:
 def list(self, *, limit=50, offset=0): return []
 def get(self, run_id): return None
def test_default_ui_smoke_case_screening_matches_fastapi():
 execution=EORAtlasExecutionService()
 direct=ExcelScreeningService().screen(CASE_INPUTS,"Sandstone")
 api=TestClient(create_app(engine=EORAtlasEngine(execution),history=FakeHistory()))
 response=api.post("/api/v1/screening/evaluate",json={"formation":"Sandstone","inputs":CASE_INPUTS})
 assert response.status_code==200,response.text
 assert response.json()["screening"]==direct
def test_default_ui_smoke_case_hybrid_matches_fastapi():
 execution=EORAtlasExecutionService()
 direct=execution.hybrid(CASE_INPUTS,"Sandstone")
 api=TestClient(create_app(engine=EORAtlasEngine(execution),history=FakeHistory()))
 response=api.post("/api/v1/intelligence/evaluate",json={"formation":"Sandstone","inputs":CASE_INPUTS})
 assert response.status_code==200,response.text
 body=response.json()
 assert body["screening"]==direct["screening"]
 assert body["hybrid"]==direct["hybrid"]
 assert body["model"]==direct["model_info"]

import json
import pytest

def test_approved_real_reservoir_cases_match_direct_service_and_fastapi():
    fixture = ROOT / "tests" / "fixtures" / "approved_reservoir_cases.json"
    if not fixture.is_file():
        pytest.skip("Approved real-reservoir fixture not supplied; real-case parity gate remains BLOCKED.")
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    cases = payload.get("cases", [])
    assert cases, "Approved-case fixture must contain at least one approved case."
    for case in cases:
        assert case.get("approved_by"), f"{case.get('id', '<unnamed>')}: missing approval owner"
        assert case.get("approved_on"), f"{case.get('id', '<unnamed>')}: missing approval date"
        assert case.get("source"), f"{case.get('id', '<unnamed>')}: missing source/provenance"
        formation = case["formation"]
        inputs = case["inputs"]
        execution = EORAtlasExecutionService()
        direct_screen = execution.screen(inputs, formation)
        direct_hybrid = execution.hybrid(inputs, formation)
        api = TestClient(create_app(engine=EORAtlasEngine(execution), history=FakeHistory()))
        screening_response = api.post("/api/v1/screening/evaluate", json={
            "field_id": case.get("field_id"), "formation": formation, "inputs": inputs
        })
        hybrid_response = api.post("/api/v1/intelligence/evaluate", json={
            "field_id": case.get("field_id"), "formation": formation, "inputs": inputs
        })
        assert screening_response.status_code == 200, f"{case['id']}: {screening_response.text}"
        assert hybrid_response.status_code == 200, f"{case['id']}: {hybrid_response.text}"
        assert screening_response.json()["screening"] == direct_screen, case["id"]
        assert hybrid_response.json()["screening"] == direct_hybrid["screening"], case["id"]
        assert hybrid_response.json()["hybrid"] == direct_hybrid["hybrid"], case["id"]
        assert hybrid_response.json()["model"] == direct_hybrid["model_info"], case["id"]
