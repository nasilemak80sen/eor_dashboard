from __future__ import annotations

from datetime import datetime

from data.screening_history import _engineering_map, _json_safe, run_reference


def test_run_reference_is_stable():
    assert run_reference(127, datetime(2026, 9, 14, 14, 30)) == "EOR-2026-000127"


def test_json_safe_handles_nested_values():
    payload = _json_safe({"a": (1, 2), "b": {"c": 3}})
    assert payload == {"a": [1, 2], "b": {"c": 3}}


def test_engineering_map_preserves_each_technique():
    result = {
        "results": [
            {"EOR Technique": "CO2 Miscible Flood", "Status": "PASS", "Score (%)": 100},
            {"EOR Technique": "Polymer (ATBS)", "Status": "CONDITIONAL", "Score (%)": 71.4},
        ]
    }
    mapped = _engineering_map(result)
    assert mapped["CO2 Miscible Flood"]["status"] == "PASS"
    assert mapped["Polymer (ATBS)"]["status"] == "CONDITIONAL"
    assert mapped["Polymer (ATBS)"]["details"]["Score (%)"] == 71.4
