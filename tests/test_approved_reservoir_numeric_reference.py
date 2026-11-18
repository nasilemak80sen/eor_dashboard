"""Numeric integrity checks for approved historical EOR reference snapshots.

These tests intentionally do not force a legacy Power BI snapshot to match the
current Excel Gate / CatBoost / Decision Fusion pipeline when its input schema
and technique-level outputs are incomplete.
"""
import json
from pathlib import Path

import pytest


FIXTURE = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "approved_reservoir_cases.json"
)


def _case() -> dict:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return next(
        case for case in payload["cases"]
        if case["case_id"] == "legacy-sandstone-screening-snapshot"
    )


def test_legacy_reservoir_snapshot_retains_source_inputs_and_units():
    case = _case()

    assert case["source"]["file"] == "eor_latest.pdf"
    assert case["source"]["page"] == 2
    assert case["formation"] == "Sandstone"
    assert case["inputs"]["api_deg"] == pytest.approx(39.40)
    assert case["inputs"]["viscosity_cp"] == pytest.approx(1.0)
    assert case["inputs"]["depth_ft"] == pytest.approx(4271.0)
    assert case["inputs"]["temperature_c"] == pytest.approx(103.0)
    assert case["inputs"]["permeability_md"] == pytest.approx(114.0)
    assert case["inputs"]["porosity_fraction"] == pytest.approx(0.200)
    assert case["inputs"]["reservoir_pressure_psia"] == pytest.approx(2078.0)
    assert case["inputs"]["ooip_mmstb"] == pytest.approx(111.0)
    assert case["inputs"]["base_recovery_factor_pct"] == pytest.approx(35.0)


def test_missing_legacy_inputs_are_not_silently_filled_with_application_defaults():
    inputs = _case()["inputs"]

    # The PDF does not reveal these controls. Null is deliberate and must not
    # be replaced with the current Streamlit form defaults in a parity fixture.
    for key in (
        "salinity_tds_ppm",
        "hardness_ca_mg_ppm",
        "initial_oil_saturation_pct_pv",
        "gas_availability",
        "oxygen_present",
    ):
        assert key in inputs
        assert inputs[key] is None


def test_reported_incremental_cr_is_flagged_when_it_does_not_reconcile_to_ooip_and_incremental_rf():
    case = _case()
    inputs = case["inputs"]
    outputs = case["reported_outputs"]
    comparison = case["comparison"]

    calculated_cr = (
        inputs["ooip_mmstb"]
        * outputs["incremental_recovery_factor_pct"]
        / 100.0
    )
    reported_cr = outputs["incremental_cr_mmstb"]

    assert calculated_cr == pytest.approx(18.315)
    assert reported_cr == pytest.approx(56.84)
    assert reported_cr - calculated_cr == pytest.approx(38.525)
    assert comparison["simple_ooip_times_incremental_rf_mmstb"] == pytest.approx(
        calculated_cr
    )
    assert comparison["reported_cr_minus_simple_calculation_mmstb"] == pytest.approx(
        38.525
    )
    assert comparison["status"] == "REVIEW_REQUIRED"


def test_legacy_snapshot_is_not_misrepresented_as_current_hybrid_parity():
    case = _case()

    assert case["reported_outputs"]["methods_passing"] == 0
    assert case["reported_outputs"]["methods_failing"] == 0
    assert case["reported_outputs"]["total_methods"] == 9
    assert case["reported_outputs"]["recommended_method"] == "No methods pass"
    assert case["comparison"]["current_engine_parity"] == "NOT_COMPARABLE"
    assert len(case["comparison"]["blockers"]) >= 3
