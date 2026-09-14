"""Historical EOR study data access for the Historical EOR workspace.

The production dashboard reference page is driven by a historical workbook sheet
named ``Screening_Parameters``. The source workbook stores the primary successful
EOR method in ``MOST SUITABLE PROCESS`` and additional passing alternatives in
``OTHERS PASS METHOD``. This module normalises those source fields without
artificially duplicating Incremental EUR across alternative methods.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import pandas as pd
import streamlit as st

from config.settings import settings

SHEET_NAME = "Screening_Parameters"
_FIELD_ALIASES = {"field", "field name", "field_name", "oil field"}
_RESERVOIR_ALIASES = {"reservoir", "reservoir name", "reservoir_name", "res"}
_STUDY_ALIASES = {"eor study", "eor studies", "eor method", "eor methods", "eor type", "types of eor", "study type", "eor study / method", "eor_study", "most suitable process", "most suitable eor process", "recommended eor process", "successful eor method", "successful eor process"}
_OTHER_STUDY_ALIASES = {"others pass method", "other pass method", "other passing method", "others passing method", "others pass methods", "other eor methods"}
_EUR_ALIASES = {"incremental eur", "incremental eur mmstb", "incremental eur (mmstb)", "incremental eur value", "incremental eur value (mmstb)", "incremental cr", "incremental cr (mmstb)", "cr volume potential", "cr volume potential (mmstb)", "eur incremental"}
_STATUS_ALIASES = {"status", "result", "eor pass/fail", "pass/fail", "success", "success flag", "screening result"}


def _normalise_column(value: Any) -> str:
    text = str(value or "").strip().lower()
    for token in ["_", "-", "/", "(", ")"]:
        text = text.replace(token, " ")
    return " ".join(text.split())


def _candidate_workbooks() -> Iterable[Path]:
    candidates = [settings.workbook_path, settings.project_root / "EOR_Screening_Tool_2026_v3.0.xlsx", settings.data_dir / "screening_parameters_Y2K Report.xlsx", settings.data_dir / "screening_parameters.xlsx", settings.data_dir / "Screening_Parameters.xlsx"]
    seen: set[Path] = set()
    for candidate in candidates:
        candidate = candidate.resolve()
        if candidate in seen:
            continue
        seen.add(candidate)
        if candidate.is_file():
            yield candidate
    if settings.data_dir.is_dir():
        for candidate in sorted(settings.data_dir.glob("*.xlsx")):
            candidate = candidate.resolve()
            if candidate in seen:
                continue
            seen.add(candidate)
            yield candidate


def _find_column(columns: list[str], aliases: set[str]) -> Optional[str]:
    normalised = {_normalise_column(column): column for column in columns}
    for alias in aliases:
        if _normalise_column(alias) in normalised:
            return normalised[_normalise_column(alias)]
    for column in columns:
        normalized = _normalise_column(column)
        if any(_normalise_column(alias) in normalized for alias in aliases):
            return column
    return None


def _status_is_success(value: Any) -> bool:
    if value is None or pd.isna(value):
        return True
    text = _normalise_column(value)
    return text in {"pass", "passed", "success", "successful", "yes", "eligible", "candidate"}


def _clean_method(value: Any) -> Optional[str]:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "n/a", "na", "-"}:
        return None
    return text


def _prepare_frame(frame: pd.DataFrame, source_path: Path) -> tuple[pd.DataFrame, Dict[str, Any]]:
    frame = frame.copy().dropna(how="all")
    frame.columns = [str(column).strip() for column in frame.columns]
    columns = list(frame.columns)
    field_col = _find_column(columns, _FIELD_ALIASES)
    reservoir_col = _find_column(columns, _RESERVOIR_ALIASES)
    study_col = _find_column(columns, _STUDY_ALIASES)
    other_study_col = _find_column(columns, _OTHER_STUDY_ALIASES)
    eur_col = _find_column(columns, _EUR_ALIASES)
    status_col = _find_column(columns, _STATUS_ALIASES)
    required = {"Field": field_col, "Reservoir": reservoir_col, "EOR Study / Most Suitable Process": study_col, "Incremental EUR": eur_col}
    missing = [label for label, column in required.items() if column is None]
    if missing:
        raise ValueError(f"Historical workbook '{source_path.name}' contains '{SHEET_NAME}' but could not resolve required columns: {', '.join(missing)}. Available columns: {columns}")

    output = pd.DataFrame({
        "Field": frame[field_col].astype(str).str.strip(),
        "Reservoir": frame[reservoir_col].astype(str).str.strip(),
        "EOR Study": frame[study_col].map(_clean_method),
        "Other Passing Methods": frame[other_study_col].map(_clean_method) if other_study_col else None,
        "Incremental EUR (MMstb)": pd.to_numeric(frame[eur_col], errors="coerce"),
    })
    output["Status"] = frame[status_col] if status_col else "Historical study"
    output = output.replace({"nan": None, "None": None, "": None})
    output = output.dropna(subset=["Field", "EOR Study", "Incremental EUR (MMstb)"])
    output = output[output["Field"].str.strip().ne("")]
    if status_col:
        output = output[output["Status"].map(_status_is_success)]
    output["EOR Study"] = output["EOR Study"].map(_clean_method)
    output["Other Passing Methods"] = output["Other Passing Methods"].map(_clean_method)
    output["Incremental EUR (MMstb)"] = output["Incremental EUR (MMstb)"].astype(float)
    output = output.drop_duplicates().reset_index(drop=True)
    metadata = {"source_path": str(source_path), "source_name": source_path.name, "sheet_name": SHEET_NAME, "rows": int(len(output)), "status_column": status_col, "primary_method_column": study_col, "alternative_method_column": other_study_col}
    return output, metadata


@st.cache_data(show_spinner=False)
def load_historical_studies() -> tuple[pd.DataFrame, Dict[str, Any]]:
    errors: list[str] = []
    for path in _candidate_workbooks():
        try:
            workbook = pd.ExcelFile(path, engine="openpyxl")
            if SHEET_NAME not in workbook.sheet_names:
                continue
            frame = pd.read_excel(path, sheet_name=SHEET_NAME, engine="openpyxl")
            prepared, metadata = _prepare_frame(frame, path)
            if prepared.empty:
                raise ValueError("The resolved historical sheet contains no usable records.")
            return prepared, metadata
        except Exception as exc:
            errors.append(f"{path.name}: {exc}")
    raise FileNotFoundError("Could not load the historical EOR data. Expected a workbook sheet named 'Screening_Parameters'. Checked known workbook locations. " + (" | ".join(errors) if errors else "No candidate workbook was found."))


def merge_manual_studies(frame: pd.DataFrame, manual_rows: list[dict[str, Any]]) -> pd.DataFrame:
    """Append session-level records, de-duplicated by study identity rather than display status."""
    if not manual_rows:
        return frame.copy()
    manual = pd.DataFrame(manual_rows)
    expected = ["Field", "Reservoir", "EOR Study", "Other Passing Methods", "Incremental EUR (MMstb)", "Status"]
    for column in expected:
        if column not in manual.columns:
            manual[column] = "Historical study" if column == "Status" else None
    manual = manual[expected].copy()
    manual["Incremental EUR (MMstb)"] = pd.to_numeric(manual["Incremental EUR (MMstb)"], errors="coerce")
    manual = manual.dropna(subset=["Field", "EOR Study", "Incremental EUR (MMstb)"])
    merged = pd.concat([frame, manual], ignore_index=True)
    identity = ["Field", "Reservoir", "EOR Study", "Incremental EUR (MMstb)"]
    return merged.drop_duplicates(subset=identity, keep="first").reset_index(drop=True)
