"""Regression tests for the repository-pinned St. Joseph R&D evidence source."""

from io import BytesIO
import re

import pandas as pd
import pytest

from data.rd_lab_evidence import (
    ST_JOS_REQUIRED_SHEETS,
    ST_JOS_SOURCE_BLOB_SHA,
    ST_JOS_SOURCE_COMMIT,
    ST_JOS_SOURCE_REF,
    load_st_jos_ceor,
)
from pages_ui import rd


def _xlsx_bytes(sheets: dict[str, list[str]]) -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for sheet_name, columns in sheets.items():
            pd.DataFrame(columns=columns).to_excel(
                writer, sheet_name=sheet_name, index=False
            )
    return buffer.getvalue()


def test_loader_rejects_missing_required_sheets_before_reading_them():
    payload = _xlsx_bytes({"Vis_Shear (St_Jos)": ["Year", "Polymer"]})

    with pytest.raises(ValueError, match="missing required worksheets") as error:
        load_st_jos_ceor(workbook_bytes=payload)

    assert "Sor_f (StJoseph)" in str(error.value)


def test_loader_reports_missing_required_columns():
    payload = _xlsx_bytes({name: [] for name in sorted(ST_JOS_REQUIRED_SHEETS)})

    with pytest.raises(ValueError, match="incompatible worksheet schema") as error:
        load_st_jos_ceor(workbook_bytes=payload)

    assert "Vis_Shear (St_Jos): expected a column containing Year" in str(error.value)
    assert "Adsorption (St_Jos): expected a column containing Field" in str(error.value)


def test_repository_pinned_st_joseph_workbook_loads_with_provenance():
    load_st_jos_ceor.clear()
    data = load_st_jos_ceor()
    meta = data["metadata"]

    assert meta["workbook_name"] == "St_Jos CEOR (Shared) (1).xlsx"
    assert meta["workbook_source_kind"] == "repository"
    assert meta["source_repository_ref"] == ST_JOS_SOURCE_REF
    assert meta["source_repository_commit"] == ST_JOS_SOURCE_COMMIT
    assert meta["source_git_blob_sha"] == ST_JOS_SOURCE_BLOB_SHA
    assert re.fullmatch(r"[0-9a-f]{64}", meta["workbook_sha256"])
    assert ST_JOS_REQUIRED_SHEETS.issubset(set(meta["source_sheet_names"]))
    assert meta["missing_sheets"] == []
    assert not data["rheology_plot"].empty
    assert meta["normalized_record_counts"]["rheology_plot"] == len(data["rheology_plot"])
    assert meta["normalized_record_counts"]["sor_reduction"] == len(data["sor_reduction"])


def test_rheology_figure_keeps_polymer_experiments_in_separate_traces():
    work = pd.DataFrame(
        {
            "Year": [2013, 2013, 2013, 2013],
            "Polymer": ["Polymer A", "Polymer A", "Polymer B", "Polymer B"],
            "Salinity (mg/L TDS)": [10000, 10000, 10000, 10000],
            "Concentration (ppm)": [1000, 1000, 1000, 1000],
            "Shear rate (1/sec)": [1, 10, 1, 10],
            "Apparent viscosity (cP)": [40, 25, 60, 35],
        }
    )

    figure = rd._build_rheology_figure(work, 2013)

    assert len(figure.data) == 2
    assert {trace.name for trace in figure.data} == {"Polymer A, 1000", "Polymer B, 1000"}


def test_censored_ift_is_displayed_as_an_open_detection_limit_marker(monkeypatch):
    captured = []
    monkeypatch.setattr(rd.st, "plotly_chart", lambda figure, **kwargs: captured.append(figure))
    frame = pd.DataFrame(
        {
            "Material": ["Surfactant A", "Surfactant B"],
            "IFT low (source)": [0.02, 0.03],
            "IFT high (source)": [0.01, 0.001],
            "IFT low raw": ["0.02", "0.03"],
            "IFT high raw": ["0.01", "<0.001"],
            "IFT high is censored": [False, True],
        }
    )

    rd._render_ift_chart(frame, "Surfactant IFT")

    assert len(captured) == 1
    limit_trace = next(trace for trace in captured[0].data if "detection limit" in trace.name)
    assert limit_trace.marker.symbol == "triangle-up-open"
    assert list(limit_trace.x) == [0.001]
