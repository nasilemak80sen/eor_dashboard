"""CEOR evidence access from the repository engineering workbook.

The CEOR page is intentionally workbook-backed. Workbook revisions can rename
some evidence sheets or use slightly different column labels, so this module
normalises those differences explicitly and never lets one missing panel break
the other CEOR tab.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from config.settings import settings

WORKBOOK_NAME = "EOR_Screening_Tool_2026.xlsx"

SHEET_ALIASES: dict[str, tuple[str, ...]] = {
    "Vis_Shear": ("Vis_Shear",),
    "PB_2003": ("PB_2003",),
    "PB_2013_A": ("PB_2013_A",),
    "PB_2013_B": ("PB_2013_B", "PB_2013_S"),
    "IFT_sur_F": ("IFT_sur_F",),
    "IFT_sur_T": ("IFT_sur_T", "IFT_poly_F"),
    "adsorption": ("adsorption", "Adsorption"),
    "Coreflood": ("Coreflood",),
    "Sor_F": ("Sor_F", "SOR_F", "Sor F", "Sor_Reduction", "Sor Reduction"),
    "Thermal": ("Thermal",),
}


def _safe_project_root() -> Path:
    configured = getattr(settings, "project_root", None)
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[2]


def _empty() -> pd.DataFrame:
    return pd.DataFrame()


def _normalise_sheet(value: Any) -> str:
    return "".join(ch.lower() for ch in str(value or "").strip() if ch.isalnum())


def _resolve_sheet(sheet_names: list[str], requested: str) -> str | None:
    aliases = SHEET_ALIASES.get(requested, (requested,))
    normalised = {_normalise_sheet(name): name for name in sheet_names}
    for alias in aliases:
        found = normalised.get(_normalise_sheet(alias))
        if found:
            return found
    return None


def _clean_columns(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result.columns = [str(column).strip() for column in result.columns]
    return result


def _column_key(value: Any) -> str:
    text = str(value or "").strip().lower()
    for token in ["_", "-", "/", "(", ")", ":"]:
        text = text.replace(token, " ")
    return " ".join(text.split())


def _first_column(frame: pd.DataFrame, aliases: tuple[str, ...]) -> str | None:
    if frame.empty:
        return None
    normalised = {_column_key(column): column for column in frame.columns}
    for alias in aliases:
        exact = normalised.get(_column_key(alias))
        if exact is not None:
            return exact
    for column in frame.columns:
        text = _column_key(column)
        for alias in aliases:
            if _column_key(alias) in text:
                return column
    return None


def _numeric(frame: pd.DataFrame, column: str | None) -> pd.Series:
    if column is None:
        return pd.Series(pd.NA, index=frame.index, dtype="Float64")
    return pd.to_numeric(frame[column], errors="coerce")


def _text(frame: pd.DataFrame, column: str | None, default: str = "Unknown") -> pd.Series:
    if column is None:
        return pd.Series(default, index=frame.index, dtype="string")
    return frame[column].astype("string").str.strip()


def _normalise_vis_shear(frame: pd.DataFrame) -> pd.DataFrame:
    frame = _clean_columns(frame)
    out = pd.DataFrame(
        {
            "Year": _numeric(frame, _first_column(frame, ("Year",))),
            "Polymer": _text(frame, _first_column(frame, ("Polymer", "Polymer Type"))),
            "Shear Rate": _numeric(frame, _first_column(frame, ("Shear Rate", "Shear Rate (1/sec)"))),
            "Apparent Viscosity": _numeric(frame, _first_column(frame, ("Apparent Viscosity",))),
        }
    )
    return out.dropna(subset=["Shear Rate", "Apparent Viscosity"]).reset_index(drop=True)


def _normalise_phase(frame: pd.DataFrame) -> pd.DataFrame:
    frame = _clean_columns(frame)
    out = pd.DataFrame(
        {
            "Year": _numeric(frame, _first_column(frame, ("Year",))),
            "Formulation": _text(frame, _first_column(frame, ("Formulation", "Formulation (A/S/P)"))),
            "Precipitation": _numeric(frame, _first_column(frame, ("Percipitation", "Precipitation"))),
            "No Precipitation": _numeric(frame, _first_column(frame, ("No Percepitation", "No Precipitation"))),
        }
    )
    return out.dropna(subset=["Formulation"]).reset_index(drop=True)


def _normalise_ift(frame: pd.DataFrame, kind: str) -> pd.DataFrame:
    frame = _clean_columns(frame)
    name = _first_column(frame, ("Surfactant", "Polymer", "Material"))
    low = _first_column(frame, ("IFT low", "IFT low dyne/cm", "IFT low dyne/cm "))
    high = _first_column(frame, ("IFT high", "IFT high dyne/cm", "IFT high dyne/cm "))
    out = pd.DataFrame(
        {
            "Year": _numeric(frame, _first_column(frame, ("Year",))),
            "Material": _text(frame, name),
            "IFT Low": _numeric(frame, low),
            "IFT High": _numeric(frame, high),
        }
    )
    out["Material Type"] = kind
    return out.dropna(subset=["Material", "IFT Low", "IFT High"]).reset_index(drop=True)


def _normalise_adsorption(frame: pd.DataFrame) -> pd.DataFrame:
    frame = _clean_columns(frame)
    temperature_col = _first_column(frame, ("Temperature", "Temperature C", "Temperature (C)", "Temp"))
    polymer_col = _first_column(frame, ("Polymer Type", "Polymer", "Polymer Name"))
    surfactant_col = _first_column(frame, ("Surfactant", "Formulation", "Chemical"))
    out = pd.DataFrame(
        {
            "Year": _numeric(frame, _first_column(frame, ("Year",))),
            "Field": _text(frame, _first_column(frame, ("Field",))),
            "Material": _text(frame, surfactant_col),
            "Days": _numeric(frame, _first_column(frame, ("Days", "Time", "Time Days"))),
            "Adsorption c/cO": _numeric(frame, _first_column(frame, ("Adsorption c/cO", "Adsorption", "Adsorption ratio"))),
            "Temperature": _numeric(frame, temperature_col),
            "Polymer Type": _text(frame, polymer_col) if polymer_col else pd.Series(pd.NA, index=frame.index, dtype="string"),
        }
    )
    return out.dropna(subset=["Days", "Adsorption c/cO"]).reset_index(drop=True)


def _normalise_coreflood(frame: pd.DataFrame) -> pd.DataFrame:
    frame = _clean_columns(frame)
    aliases: dict[str, tuple[str, ...]] = {
        "Core sample": ("Core sample", "Core Flood Sample", "Core Floof Sample"),
        "Year": ("Year",),
        "Water Flood": ("Water Flood Recovery, % OOIP", "Water Flood Recovery"),
        "AS": ("Alkaline- Surfactant (AS) Recovery, % OOIP", "AS Recovery"),
        "Polymer": ("Polymer (P) Recovery, % OOIP", "Polymer Recovery"),
        "Alkaline": ("Alkaline(A) Recovery", "Alkaline Recovery"),
        "Surfactant": ("Surfactant (S) Recovery", "Surfactant Recovery"),
        "SP": ("Surfactant +Polymer (SP) Recovery", "Surfactant + Polymer (SP) Recovery"),
        "ASP": ("Alkali +Surfactant +Polymer (ASP) Recovery", "ASP Recovery"),
        "Sor Reduction AS": ("% Sor Reduction (AS)",),
        "Sor Reduction ASP": ("% Sor Reduction (AS,P)", "% Sor Reduction (ASP)"),
        "Sor Reduction SP": ("% Sor Reduction (SP)",),
    }
    data: dict[str, Any] = {}
    for target, names in aliases.items():
        column = _first_column(frame, names)
        data[target] = _text(frame, column) if target == "Core sample" else _numeric(frame, column)
    out = pd.DataFrame(data)
    return out.dropna(subset=["Core sample"]).reset_index(drop=True)


def _normalise_sor_sheet(frame: pd.DataFrame) -> pd.DataFrame:
    """Support both long and wide Sor_F workbook layouts."""
    frame = _clean_columns(frame)
    core = _first_column(frame, ("Core sample", "Core Flood Sample", "Core Floof Sample", "Sample"))
    year = _first_column(frame, ("Year",))
    method = _first_column(frame, ("Method", "Recovery Type", "Sor Reduction Method", "Process", "Type"))
    value = _first_column(frame, ("Sor Reduction", "Sor Reduction (%)", "% Sor Reduction", "Sor reduction from core flood"))

    if core is not None and method is not None and value is not None:
        return pd.DataFrame(
            {
                "Core sample": _text(frame, core),
                "Year": _numeric(frame, year),
                "Method": _text(frame, method),
                "Sor Reduction (%)": _numeric(frame, value),
            }
        ).dropna(subset=["Sor Reduction (%)"]).reset_index(drop=True)

    sor_columns = []
    for column in frame.columns:
        key = _column_key(column)
        if "sor reduction" in key and "core" not in key:
            sor_columns.append(column)
    if core is None or not sor_columns:
        return _empty()

    records: list[pd.DataFrame] = []
    for column in sor_columns:
        part = pd.DataFrame(
            {
                "Core sample": _text(frame, core),
                "Year": _numeric(frame, year),
                "Method": str(column).strip(),
                "Sor Reduction (%)": _numeric(frame, column),
            }
        )
        records.append(part.dropna(subset=["Sor Reduction (%)"]))
    return pd.concat(records, ignore_index=True) if records else _empty()


def _derive_sor_from_coreflood(coreflood: pd.DataFrame) -> pd.DataFrame:
    parts: list[pd.DataFrame] = []
    for column in ("Sor Reduction AS", "Sor Reduction ASP", "Sor Reduction SP"):
        if column not in coreflood.columns:
            continue
        method = column.replace("Sor Reduction ", "").strip()
        part = coreflood[["Core sample", "Year", column]].copy()
        part = part.rename(columns={column: "Sor Reduction (%)"})
        part["Method"] = method
        parts.append(part)
    if not parts:
        return _empty()
    return pd.concat(parts, ignore_index=True).dropna(subset=["Sor Reduction (%)"]).reset_index(drop=True)


@st.cache_data(show_spinner=False)
def load_ceor_evidence() -> dict[str, Any]:
    project_root = _safe_project_root()
    workbook_path = project_root / WORKBOOK_NAME
    if not workbook_path.is_file():
        raise FileNotFoundError(f"Repository CEOR workbook not found: {workbook_path}")

    xlsx = pd.ExcelFile(workbook_path, engine="openpyxl")
    sheets = list(xlsx.sheet_names)
    raw: dict[str, pd.DataFrame] = {}
    source_map: dict[str, str] = {}
    missing: list[str] = []

    for requested in SHEET_ALIASES:
        source = _resolve_sheet(sheets, requested)
        if source is None:
            missing.append(requested)
            continue
        raw[requested] = _clean_columns(pd.read_excel(xlsx, sheet_name=source))
        source_map[requested] = source

    vis = _normalise_vis_shear(raw.get("Vis_Shear", _empty()))
    pb_2003 = _normalise_phase(raw.get("PB_2003", _empty()))
    pb_2013_a = _normalise_phase(raw.get("PB_2013_A", _empty()))
    pb_2013_b = _normalise_phase(raw.get("PB_2013_B", _empty()))
    ift_sur = _normalise_ift(raw.get("IFT_sur_F", _empty()), "Surfactant")
    ift_poly = _normalise_ift(raw.get("IFT_sur_T", _empty()), "Polymer")
    adsorption = _normalise_adsorption(raw.get("adsorption", _empty()))
    coreflood = _normalise_coreflood(raw.get("Coreflood", _empty()))

    sor = _normalise_sor_sheet(raw.get("Sor_F", _empty()))
    sor_source = source_map.get("Sor_F")
    if sor.empty:
        sor = _derive_sor_from_coreflood(coreflood)
        sor_source = "derived from Coreflood"

    metadata: dict[str, Any] = {
        "workbook": str(workbook_path),
        "workbook_name": workbook_path.name,
        "sheet_names": sheets,
        "source_map": source_map,
        "missing_requested_sheets": missing,
        "sor_source": sor_source,
    }

    metadata["adsorption_available_years"] = sorted(adsorption["Year"].dropna().astype(int).unique().tolist()) if not adsorption.empty else []
    metadata["adsorption_available_temperatures"] = sorted(adsorption["Temperature"].dropna().unique().tolist()) if "Temperature" in adsorption else []
    metadata["adsorption_available_polymer_types"] = sorted(adsorption["Polymer Type"].dropna().astype(str).unique().tolist(), key=str.casefold) if "Polymer Type" in adsorption else []

    return {
        "Vis_Shear": vis,
        "PB_2003": pb_2003,
        "PB_2013_A": pb_2013_a,
        "PB_2013_B": pb_2013_b,
        "IFT_sur_F": ift_sur,
        "IFT_sur_T": ift_poly,
        "adsorption": adsorption,
        "Coreflood": coreflood,
        "Sor_F": sor,
        "metadata": metadata,
    }
