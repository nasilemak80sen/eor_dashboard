from datetime import time

import pandas as pd

from data.baronia_wag_evidence import (
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
