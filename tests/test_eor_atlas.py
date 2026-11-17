"""Current EOR Atlas production contract tests.

The former tests in this module targeted pre-refactor classes and modules that
are no longer part of the production application. These checks protect the
current app shell, map payload, overview aggregation and CatBoost input adapter.
"""
from __future__ import annotations

import pandas as pd
import pytest

from config.settings import settings
from eor_atlas import _system_state
from hybrid_app import _build_legacy_catboost_input
from pages_ui.overview import _map_summary
from ui.openglobus import _normalise_records


def test_system_state_uses_loaded_workbook_and_model_services(monkeypatch):
    monkeypatch.setattr(settings, "validate_paths", lambda: {"workbook": False})

    assert _system_state(
        {"workbook_sheets": {"PROP_updatedNov25_v2": pd.DataFrame()}, "model_loaded": True}
    ) == {"workbook": True, "model": True}
    assert _system_state({"workbook_sheets": {}, "model_loaded": False}) == {
        "workbook": False,
        "model": False,
    }


def test_system_state_falls_back_to_configured_workbook_path(monkeypatch):
    monkeypatch.setattr(settings, "validate_paths", lambda: {"workbook": True})

    assert _system_state({"workbook_sheets": {}, "model_loaded": False}) == {
        "workbook": True,
        "model": False,
    }


def test_overview_map_summary_aggregates_fields_and_distinct_methods():
    source = pd.DataFrame(
        {
            "Field Name": ["Angsi", "Angsi", "Tapis", "Tapis"],
            "Types of EOR": ["CO2", "WAG", "WAG", "WAG"],
            "Latitude": [4.30, 4.32, 5.60, 5.62],
            "Longitude": [103.10, 103.14, 104.20, 104.24],
        }
    )

    fields, methods = _map_summary(source)

    angsi = fields.loc[fields["Field"] == "Angsi"].iloc[0]
    tapis = fields.loc[fields["Field"] == "Tapis"].iloc[0]
    assert angsi["Methods"] == 2
    assert angsi["EOR Methods"] == "CO2, WAG"
    assert angsi["Latitude"] == pytest.approx(4.31)
    assert tapis["Methods"] == 1
    assert set(methods["EOR Method"]) == {"CO2", "WAG"}


def test_overview_map_summary_returns_empty_views_for_incomplete_schema():
    fields, methods = _map_summary(pd.DataFrame({"Field": ["Angsi"]}))
    assert fields.empty
    assert methods.empty


def test_openglobus_normalizes_valid_records_and_drops_invalid_coordinates():
    source = pd.DataFrame(
        {
            "Field": ["Angsi", "Tapis", "", "Bekok"],
            "Latitude": [4.31, "not-a-number", 1.83, 1.83],
            "Longitude": [103.12, 104.22, 103.95, 103.95],
            "Methods": [3, 2, 1, 1],
            "EOR Methods": ["CO2, WAG, Steam", "WAG, Polymer", "CO2", "CO2"],
        }
    )

    records = _normalise_records(
        source,
        latitude="Latitude",
        longitude="Longitude",
        name="Field",
        value="Methods",
        value_label="Distinct EOR methods",
        detail_columns=(("EOR methods", "EOR Methods"),),
    )

    assert [record["name"] for record in records] == ["Angsi", "Bekok"]
    assert records[0] == {
        "name": "Angsi",
        "latitude": 4.31,
        "longitude": 103.12,
        "value": 3.0,
        "value_label": "Distinct EOR methods",
        "details": {"EOR methods": "CO2, WAG, Steam"},
    }
    # Rows with invalid coordinates or blank names are discarded.
    assert all(record["name"] not in {"Tapis", ""} for record in records)


def test_catboost_input_adapter_maps_formation_and_duplicates_scalar_ranges():
    values = {
        "depth_ft": 5000,
        "porosity_pct": 20,
        "perm_md": 100,
        "api": 35,
        "visc_cp": 2,
        "so_pct": 55,
    }

    result = _build_legacy_catboost_input(values, "Carbonate")

    assert result["formation_category"] == "Carbonates"
    expected_ranges = {
        "depth_min_ft": 5000,
        "depth_max_ft": 5000,
        "porosity_min_pct": 20,
        "porosity_max_pct": 20,
        "perm_min_md": 100,
        "perm_max_md": 100,
        "api_min": 35,
        "api_max": 35,
        "visc_min_cp": 2,
        "visc_max_cp": 2,
        "so_min_pct": 55,
        "so_max_pct": 55,
    }
    for key, expected in expected_ranges.items():
        assert result[key] == expected


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("depth_ft", 0, "depth_ft must be greater than zero"),
        ("perm_md", 0, "perm_md must be greater than zero"),
        ("visc_cp", -1, "visc_cp must be greater than zero"),
    ],
)
def test_catboost_input_adapter_rejects_nonpositive_physical_inputs(field, value, message):
    values = {
        "depth_ft": 5000,
        "porosity_pct": 20,
        "perm_md": 100,
        "api": 35,
        "visc_cp": 2,
        "so_pct": 55,
    }
    values[field] = value
    with pytest.raises(ValueError, match=message):
        _build_legacy_catboost_input(values, "Sandstone")
