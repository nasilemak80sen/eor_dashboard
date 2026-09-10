from __future__ import annotations

from ml.hybrid_feature_builder import FEATURE_NAMES, build_hybrid_features
from ml.hybrid_intelligence import HybridDecisionService, HybridWeights, build_opportunity_context


def _screening_result(status="PASS", score=90.0):
    return {
        "results": [
            {
                "EOR Technique": "CO2 Miscible Flood",
                "Status": status,
                "Score (%)": score,
                "Cause of Fail/Pass": "test",
            },
            {
                "EOR Technique": "Polymer (HPAM)",
                "Status": "PASS",
                "Score (%)": 70.0,
                "Cause of Fail/Pass": "test",
            },
        ]
    }


def test_hybrid_weights():
    weights = HybridWeights()
    weights.validate()
    assert weights.ml + weights.engineering == 1.0


def test_v3_opportunity_context():
    context = build_opportunity_context(
        {
            "so_pct": 65.0,
            "sorw_pct": 35.0,
            "produced_gor_scf_stb": 735.0,
        }
    )
    assert context["movable_oil_saturation_pct"] == 30.0
    assert context["gor_category"] == "Moderate"


def test_hybrid_rejects_hard_gate_failure():
    result = HybridDecisionService().fuse(
        _screening_result(status="FAIL (critical)", score=0.0),
        {"Miscible CO2": 0.95, "Polymer": 0.05},
    )
    recommendation = result["recommendation"]
    assert recommendation is not None
    assert recommendation["EOR Technique"] != "CO2 Miscible Flood"


def test_hybrid_prefers_stronger_combination():
    result = HybridDecisionService().fuse(
        _screening_result(status="PASS", score=95.0),
        {"Miscible CO2": 0.80, "Polymer": 0.20},
    )
    assert result["recommendation"]["EOR Technique"] == "CO2 Miscible Flood"
    assert abs(sum(row["Hybrid Score"] for row in result["ranking"]) - 1.0) < 1e-9


def test_hybrid_feature_schema_is_stable():
    df = build_hybrid_features(
        {
            "depth_ft": 5000,
            "temperature_c": 95,
            "reservoir_pressure": 2500,
            "porosity_pct": 20,
            "perm_md": 100,
            "api": 35,
            "visc_cp": 2,
            "so_pct": 55,
            "sorw_pct": None,
            "produced_gor_scf_stb": 574,
        },
        "Sandstone",
    )
    assert list(df.columns) == FEATURE_NAMES
    assert df.shape == (1, len(FEATURE_NAMES))
