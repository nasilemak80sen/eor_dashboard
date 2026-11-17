"""Streamlit AppTest smoke coverage for the R&D Laboratory navigation and tabs."""

import pandas as pd
import streamlit as st
from streamlit.testing.v1 import AppTest

from pages_ui import rd


def _ceor_data() -> dict:
    return {
        "metadata": {"fields": ["St. Joseph", "Angsi"]},
        "field_map": pd.DataFrame(
            columns=["Field", "EOR type", "Year", "Study type"]
        ),
        "thermal": pd.DataFrame(columns=["Field"]),
        "adsorption": pd.DataFrame(columns=["Field"]),
        "Coreflood": pd.DataFrame(),
        "Sor_F": pd.DataFrame(),
    }


def _panel(calls: list[str], label: str):
    def render(*_args, **_kwargs) -> None:
        calls.append(label)
        st.markdown(f"AppTest rendered: {label}")

    return render


def _install_ceor_fakes(monkeypatch, calls: list[str]) -> None:
    monkeypatch.setattr(rd, "load_ceor_evidence", _ceor_data)
    monkeypatch.setattr(rd, "_load_st_jos_supplement", lambda: None)
    monkeypatch.setattr(
        rd, "_render_primary_fluid_fluid", _panel(calls, "Primary Fluid–Fluid")
    )
    monkeypatch.setattr(
        rd, "_render_primary_adsorption", _panel(calls, "Primary Adsorption")
    )
    monkeypatch.setattr(
        rd, "_render_primary_coreflood", _panel(calls, "Primary Coreflood")
    )
    monkeypatch.setattr(
        rd, "_render_primary_sor", _panel(calls, "Primary Sor")
    )


def _tab_labels(app_test: AppTest) -> list[str]:
    return [tab.label for tab in app_test.tabs]


def test_ceor_all_fields_renders_both_method_tabs(monkeypatch):
    calls: list[str] = []
    _install_ceor_fakes(monkeypatch, calls)

    app = AppTest.from_function(rd.render).run()

    assert not app.exception
    assert app.radio(key="rd_method").value == "CEOR"
    assert _tab_labels(app) == ["Fluid–Fluid", "Fluid–Rock"]
    assert calls == [
        "Primary Fluid–Fluid",
        "Primary Adsorption",
        "Primary Coreflood",
        "Primary Sor",
    ]


def test_ceor_st_joseph_field_selection_renders_supplemental_evidence(monkeypatch):
    calls: list[str] = []
    _install_ceor_fakes(monkeypatch, calls)
    monkeypatch.setattr(
        rd, "_load_st_jos_supplement", lambda: {"source": "approved St. Joseph source"}
    )
    monkeypatch.setattr(
        rd, "_render_fluid_fluid", _panel(calls, "St. Joseph supplemental Fluid–Fluid")
    )
    monkeypatch.setattr(
        rd, "_render_fluid_rock", _panel(calls, "St. Joseph supplemental Fluid–Rock")
    )

    app = AppTest.from_function(rd.render).run()
    calls.clear()
    app.selectbox(key="rd_ceor_field").select("St. Joseph").run()

    assert not app.exception
    assert _tab_labels(app) == ["Fluid–Fluid", "Fluid–Rock"]
    assert calls == [
        "St. Joseph supplemental Fluid–Fluid",
        "Primary Fluid–Fluid",
        "St. Joseph supplemental Fluid–Rock",
        "Primary Coreflood",
        "Primary Sor",
    ]


def test_wag_method_renders_all_four_workspace_tabs(monkeypatch):
    calls: list[str] = []
    _install_ceor_fakes(monkeypatch, calls)

    wag_data = {
        "summary_field": pd.DataFrame(
            [{"Item": "Field Name", "Value": "Baronia"}]
        ),
        "summary_metrics": pd.DataFrame([
            {"Metric": "Target Reservoir", "Value": "RV2"},
            {"Metric": "STOIIP (RV2)", "Value": "3.38 MMSTB"},
        ]),
        "recovery_summary": pd.DataFrame([
            {"Recovery Stage": "Waterflood Recovery", "Value": 64},
            {"Recovery Stage": "IWAG Recovery (Total)", "Value": 87},
            {"Recovery Stage": "IWAG Incremental Recovery", "Value": 23},
        ]),
        "quality_issues": pd.DataFrame(columns=["Severity", "Issue"]),
        "metadata": {
            "source_report": "Synthetic acceptance fixture",
            "workbook_source_kind": "local-file",
            "workbook_sha256": "a" * 64,
            "core_samples": 4,
            "quality_issue_count": 0,
        },
    }
    monkeypatch.setattr(rd, "load_baronia_wag", lambda: wag_data)
    monkeypatch.setattr(
        rd, "_render_wag_performance", _panel(calls, "IWAG Performance")
    )
    monkeypatch.setattr(
        rd, "_render_wag_injection_model", _panel(calls, "Injection & Model")
    )
    monkeypatch.setattr(
        rd, "_render_wag_field_core", _panel(calls, "Field & Core")
    )
    monkeypatch.setattr(
        rd, "_render_wag_quality", _panel(calls, "Data Quality")
    )

    app = AppTest.from_function(rd.render).run()
    calls.clear()
    app.radio(key="rd_method").set_value("WAG").run()

    assert not app.exception
    assert app.radio(key="rd_method").value == "WAG"
    assert _tab_labels(app) == [
        "IWAG Performance",
        "Injection & Model",
        "Field & Core",
        "Data Quality",
    ]
    assert calls == [
        "IWAG Performance",
        "Injection & Model",
        "Field & Core",
        "Data Quality",
    ]
