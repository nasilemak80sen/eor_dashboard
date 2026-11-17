from datetime import time
import os

import pandas as pd
import pytest

from data.baronia_wag_evidence import (
    _build_cycle_reconciliation,
    _build_pv_reconciliation,
    _float,
    _quality_issues,
    _restore_serial,
    _restore_column,
    _table,
)


def test_section_table_stops_at_next_section():
    raw = pd.DataFrame([
        ["SECTION 1: EXAMPLE", None, None],
        ["Name", "Value", "Unit"],
        ["A", 10, "PV"],
        ["B", 20, "PV"],
        [None, None, None],
        ["SECTION 2: NEXT", None, None],
        ["Other", "Value", None],
    ])
    result = _table(raw, ["Name", "Value", "Unit"], section="SECTION 1: EXAMPLE")
    assert result.to_dict("records") == [
        {"Name": "A", "Value": 10, "Unit": "PV"},
        {"Name": "B", "Value": 20, "Unit": "PV"},
    ]


def test_time_formatted_ratio_is_restored_to_numeric_serial():
    assert abs(_restore_serial(time(1, 1)) - 0.04236111111111111) < 1e-12


def test_numeric_serial_restore_is_limited_to_named_cells():
    frame = pd.DataFrame([
        {"Parameter": "WAG Ratio", "Value": time(1, 1)},
        {"Parameter": "Experiment Date", "Value": "2014-03-01"},
    ])
    result = _restore_column(frame, "Parameter", "Value", {"wag ratio"})
    assert abs(float(result.iloc[0]["Value"]) - 0.04236111111111111) < 1e-12
    assert result.iloc[1]["Value"] == "2014-03-01"


def test_recovery_conflicts_and_invalid_saturation_are_flagged():
    recovery = pd.DataFrame([
        {"Recovery Stage": "Waterflood Recovery", "Value": 64},
        {"Recovery Stage": "IWAG Recovery (Total)", "Value": 87},
        {"Recovery Stage": "IWAG Incremental Recovery", "Value": 23},
    ])
    iwag = pd.DataFrame([{"Parameter": "IWAG Recovery over Waterflood", "Value": 17}])
    curve = pd.DataFrame([{
        "PV Injected": 0.7, "Oil Recovery (%)": 65,
        "Injection Phase": "End 1st WF / 1st Gas Start",
        "Oil Saturation (%)": -1, "Water Saturation (%)": 101, "Gas Saturation (%)": 0,
    }])
    cycles = pd.DataFrame([
        {"Injection Cycle": "Primary Waterflood", "Incremental Recovery (%)": 65},
        {"Injection Cycle": "1st Gas Cycle", "Incremental Recovery (%)": 4},
        {"Injection Cycle": "1st Water Cycle", "Incremental Recovery (%)": 5},
        {"Injection Cycle": "2nd Gas Cycle", "Incremental Recovery (%)": 1},
        {"Injection Cycle": "2nd Water Cycle", "Incremental Recovery (%)": 7},
        {"Injection Cycle": "3rd Gas Cycle", "Incremental Recovery (%)": 2},
        {"Injection Cycle": "3rd Water Cycle", "Incremental Recovery (%)": 2},
        {"Injection Cycle": "4th Gas Cycle", "Incremental Recovery (%)": 1},
    ])
    design = pd.DataFrame([
        {"Parameter": "WAG Ratio", "Value": 0.04236111111111111},
        {"Parameter": "Gas Slug Size", "Value": 0.2},
        {"Parameter": "Water Slug Size", "Value": 0.2},
    ])
    fluid = pd.DataFrame([{"Parameter": "C12+ Content Range", "Value": 46065}])
    issues = _quality_issues(recovery, iwag, curve, cycles, design, fluid)
    names = set(issues["Issue"])
    assert "IWAG Results sheet conflicts with recovery summary" in names
    assert "Cycle-level increments do not reconcile to summary recovery" in names
    assert "Waterflood recovery differs between summary and coreflood curve" in names
    assert "Coreflood saturation profile contains out-of-range values" in names
    assert "WAG ratio value needs source confirmation" in names
    assert "C12+ composition value is not a valid molar percentage" in names


def test_approximate_numeric_cells_are_parsed_without_losing_the_approximation_source():
    assert _float("~2.0") == pytest.approx(2.0)
    assert _float("1,800") == pytest.approx(1800.0)


def _phase_curve():
    return pd.DataFrame([
        {"PV Injected": 0.7, "Oil Recovery (%)": 65, "Injection Phase": "End 1st WF / 1st Gas Start"},
        {"PV Injected": 0.8, "Oil Recovery (%)": 65, "Injection Phase": "1st Gas Injection"},
        {"PV Injected": 0.9, "Oil Recovery (%)": 69, "Injection Phase": "1st Water Slug"},
        {"PV Injected": 1.1, "Oil Recovery (%)": 74, "Injection Phase": "2nd Water Slug"},
        {"PV Injected": 1.3, "Oil Recovery (%)": 75, "Injection Phase": "3rd Gas Injection"},
        {"PV Injected": 1.5, "Oil Recovery (%)": 82, "Injection Phase": "3rd Water Slug"},
        {"PV Injected": 1.7, "Oil Recovery (%)": 84, "Injection Phase": "4th Water Slug"},
        {"PV Injected": 1.9, "Oil Recovery (%)": 86, "Injection Phase": "4th Water Slug"},
        {"PV Injected": 2.0, "Oil Recovery (%)": 87, "Injection Phase": "Final"},
    ])


def _cycle_table():
    return pd.DataFrame([
        {"Injection Cycle": "Primary Waterflood", "PV Start": 0.0, "PV End": 0.7, "Recovery at End (%)": 65, "Incremental Recovery (%)": 65},
        {"Injection Cycle": "1st Gas Cycle", "PV Start": 0.7, "PV End": 0.9, "Recovery at End (%)": 69, "Incremental Recovery (%)": 4},
        {"Injection Cycle": "1st Water Cycle", "PV Start": 0.9, "PV End": 1.1, "Recovery at End (%)": 74, "Incremental Recovery (%)": 5},
        {"Injection Cycle": "2nd Gas Cycle", "PV Start": 1.1, "PV End": 1.3, "Recovery at End (%)": 75, "Incremental Recovery (%)": 1},
        {"Injection Cycle": "2nd Water Cycle", "PV Start": 1.3, "PV End": 1.5, "Recovery at End (%)": 82, "Incremental Recovery (%)": 7},
        {"Injection Cycle": "3rd Gas Cycle", "PV Start": 1.5, "PV End": 1.7, "Recovery at End (%)": 84, "Incremental Recovery (%)": 2},
        {"Injection Cycle": "3rd Water Cycle", "PV Start": 1.7, "PV End": 1.9, "Recovery at End (%)": 86, "Incremental Recovery (%)": 2},
        {"Injection Cycle": "4th Gas Cycle", "PV Start": 1.9, "PV End": 2.0, "Recovery at End (%)": 87, "Incremental Recovery (%)": 1},
    ])


def _design_table():
    return pd.DataFrame([
        {"Parameter": "First Waterflood", "Value": 1.0},
        {"Parameter": "Gas Slug Size", "Value": 0.2},
        {"Parameter": "Water Slug Size", "Value": 0.2},
        {"Parameter": "Number of WAG Cycles", "Value": 4},
        {"Parameter": "Total Fluid Injected", "Value": "~2.0"},
    ])


def test_pv_reconciliation_keeps_design_material_balance_and_curve_endpoints_separate():
    recovery = pd.DataFrame([
        {"Recovery Stage": "Total Pore Volumes Injected", "Value": 2.0},
    ])
    production = pd.DataFrame([{"PV Injected": 0.0}, {"PV Injected": 2.0}])
    material = pd.DataFrame([
        {"Parameter": "Total Water Injected", "Value": 1.8},
        {"Parameter": "Total Gas Injected", "Value": 0.8},
    ])

    table, metrics = _build_pv_reconciliation(
        recovery, _phase_curve(), production, _design_table(), material
    )

    assert metrics["expected_wag"] == pytest.approx(1.6)
    assert metrics["expected_total"] == pytest.approx(2.6)
    assert metrics["balance_total"] == pytest.approx(2.6)
    assert metrics["curve_wf_pv"] == pytest.approx(0.7)
    assert metrics["observed_wag_span"] == pytest.approx(1.3)
    values = table.set_index("Measure")["Value"]
    assert values["Field-reported total fluid injected"] == pytest.approx(2.0)
    assert values["Recovery-curve PV endpoint"] == pytest.approx(2.0)
    assert values["Material-balance total injected"] == pytest.approx(2.6)


def test_injection_cycle_reconciliation_detects_missing_stage_and_phase_conflicts():
    result = _build_cycle_reconciliation(_cycle_table(), _design_table(), _phase_curve())

    assert result.loc[result["Expected stage"].eq("4th Water Cycle"), "Presence"].iloc[0] == "Missing"
    assert result.loc[result["Workbook stage"].eq("4th Gas Cycle"), "Phase alignment"].iloc[0] == "Conflict"
    assert result.loc[result["Workbook stage"].eq("3rd Water Cycle"), "Phase alignment"].iloc[0] == "Conflict"
    assert result["Presence"].eq("Present").sum() == 7


def test_quality_issues_cover_recovery_pv_and_cycle_conflicts():
    recovery = pd.DataFrame([
        {"Recovery Stage": "Waterflood Recovery", "Value": 64},
        {"Recovery Stage": "IWAG Recovery (Total)", "Value": 87},
        {"Recovery Stage": "IWAG Incremental Recovery", "Value": 23},
        {"Recovery Stage": "Total Pore Volumes Injected", "Value": 2.0},
    ])
    iwag = pd.DataFrame([
        {"Parameter": "IWAG Recovery over Waterflood", "Value": 17},
        {"Parameter": "Recovery from Hysteresis Effects", "Value": 12},
        {"Parameter": "Recovery from Gas Displacement", "Value": 5},
    ])
    material = pd.DataFrame([
        {"Parameter": "Total Water Injected", "Value": 1.8},
        {"Parameter": "Total Gas Injected", "Value": 0.8},
    ])
    production = pd.DataFrame([{"PV Injected": 0.0}, {"PV Injected": 2.0}])
    cycles = _cycle_table()
    design = _design_table()
    fluid = pd.DataFrame(columns=["Parameter", "Value"])

    issues = _quality_issues(
        recovery, iwag, _phase_curve(), cycles, design, fluid,
        material_balance=material, production_curve=production,
    )
    names = set(issues["Issue"])

    assert "IWAG Results sheet conflicts with recovery summary" in names
    assert "Cycle-level increments do not reconcile to summary recovery" in names
    assert "Waterflood recovery differs between summary and coreflood curve" in names
    assert "Reported total injected PV conflicts with the design schedule" in names
    assert "Coreflood PV endpoints conflict with the injection design" in names
    assert "Initial waterflood PV differs between design and recovery curve" in names
    assert "Observed post-waterflood PV span differs from the WAG slug schedule" in names
    assert "Injection-cycle sequence is incomplete" in names
    assert "Injection-cycle labels conflict with recovery-curve phase labels" in names


LIBRARY_BARONIA_SHA256 = "055252fc59121b32992cfd464cd50ec4ab166b2740501abe9e2b708d0b0af8d9"


@pytest.mark.skipif(
    not os.environ.get("BARONIA_WAG_WORKBOOK"),
    reason="Set BARONIA_WAG_WORKBOOK to the approved Library copy for local end-to-end validation.",
)
def test_approved_library_baronia_workbook_end_to_end():
    from data.baronia_wag_evidence import load_baronia_wag

    load_baronia_wag.clear()
    data = load_baronia_wag(workbook_path=os.environ["BARONIA_WAG_WORKBOOK"])

    assert data["metadata"]["workbook_sha256"] == LIBRARY_BARONIA_SHA256
    assert data["metadata"]["workbook_source_kind"] == "local-file"
    assert data["metadata"]["sheets"] == sorted({
        "EOR ATLAS Summary", "Coreflood Recovery Data", "Field Information",
        "IWAG Results", "Core Analysis",
    })
    pv = data["pv_reconciliation"].set_index("Measure")["Value"]
    assert pv["Expected total injection"] == pytest.approx(2.6)
    assert pv["Material-balance total injected"] == pytest.approx(2.6)
    assert pv["Field-reported total fluid injected"] == pytest.approx(2.0)
    assert pv["Coreflood-summary total injected"] == pytest.approx(2.0)
    assert pv["Recovery-curve PV endpoint"] == pytest.approx(2.0)
    assert pv["Observed post-waterflood PV span"] == pytest.approx(1.3)

    recovery = data["recovery_reconciliation"].set_index("Measure")["Value"]
    assert recovery["IWAG incremental recovery"] == pytest.approx(23)
    assert recovery["IWAG Results increment"] == pytest.approx(17)
    assert recovery["Cycle increments summed"] == pytest.approx(22)
    assert recovery["Recovery-curve increment"] == pytest.approx(22)

    cycle = data["cycle_reconciliation"]
    assert cycle.loc[cycle["Expected stage"].eq("4th Water Cycle"), "Presence"].iloc[0] == "Missing"
    assert cycle["Presence"].eq("Present").sum() == 7
    assert cycle["Phase alignment"].eq("Conflict").sum() == 5

    issue_names = set(data["quality_issues"]["Issue"])
    assert "Injection-cycle sequence is incomplete" in issue_names
    assert "Coreflood PV endpoints conflict with the injection design" in issue_names
    assert "Injection-cycle labels conflict with recovery-curve phase labels" in issue_names
    assert "Injection-cycle PV intervals are not contiguous" not in issue_names


def test_cycle_order_and_interval_gaps_are_flagged():
    from data.baronia_wag_evidence import _quality_issues

    recovery = pd.DataFrame(columns=["Recovery Stage", "Value"])
    iwag = pd.DataFrame(columns=["Parameter", "Value"])
    fluid = pd.DataFrame(columns=["Parameter", "Value"])
    design = _design_table()
    curve = _phase_curve()
    cycles = _cycle_table()
    # Preserve all labels but swap two adjacent source rows.
    cycles.loc[[2, 3], :] = cycles.loc[[3, 2], :].to_numpy()
    cycles.loc[cycles["Injection Cycle"].eq("2nd Gas Cycle"), "PV Start"] = 1.15

    issues = _quality_issues(
        recovery, iwag, curve, cycles, design, fluid,
        material_balance=pd.DataFrame(columns=["Parameter", "Value"]),
        production_curve=pd.DataFrame(columns=["PV Injected"]),
    )
    names = set(issues["Issue"])

    assert "Injection-cycle rows are not in the expected gas/water order" in names
    assert "Injection-cycle PV intervals are not contiguous" in names
