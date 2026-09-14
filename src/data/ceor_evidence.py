"""CEOR evidence data access from the repository engineering workbook.

The CEOR pages intentionally use the workbook as the source of truth rather than
hard-coded demonstration values. A few workbook revisions use different sheet
names for the same evidence panel; aliases are handled explicitly and exposed in
metadata so the UI can remain transparent about its source.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from config.settings import settings


WORKBOOK_NAME = "EOR_Screening_Tool_2026.xlsx"

# Requested panel names -> repository workbook aliases observed in current source.
SHEET_ALIASES: dict[str, tuple[str, ...]] = {
    "Vis_Shear": ("Vis_Shear",),
    "PB_2003": ("PB_2003",),
    "PB_2013_A": ("PB_2013_A",),
    "PB_2013_B": ("PB_2013_B", "PB_2013_S"),
    "IFT_sur_F": ("IFT_sur_F",),
    # Page 5's second IFT panel is explicitly Polymer IFT Range.
    "IFT_sur_T": ("IFT_sur_T", "IFT_poly_F"),
    "adsorption": ("adsorption", "Adsorption"),
    "Coreflood": ("Coreflood",),
    "Sor_F": ("Sor_F",),
    # Used only for contextual year / temperature / polymer metadata on adsorption.
    "Thermal": ("Thermal",),
}


def _normalise_sheet(value: str) -> str:
    return "".join(ch.lower() for ch in str(value).strip() if ch.isalnum())


def _resolve_sheet(sheet_names: list[str], requested: str) -> str | None:
    aliases = SHEET_ALIASES.get(requested, (requested,))
    normalised = {_normalise_sheet(name): name for name in sheet_names}
    for alias in aliases:
        found = normalised.get(_normalise_sheet(alias))
        if found:
            return found
    return None


def _clean_columns(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    frame.columns = [str(column).strip() for column in frame.columns]
    return frame


def _first_column(frame: pd.DataFrame, aliases: tuple[str, ...]) -> str | None:
    normalised = {" ".join(str(c).lower().replace("_", " ").split()): c for c in frame.columns}
    for alias in aliases:
        key = " ".join(alias.lower().replace("_", " ").split())
        if key in normalised:
            return normalised[key]
    for column in frame.columns:
        text = " ".join(str(column).lower().replace("_", " ").split())
        if any(alias.lower() in text for alias in aliases):
            return column
    return None


def _empty() -> pd.DataFrame:
    return pd.DataFrame()


def _normalise_vis_shear(frame: pd.DataFrame) -> pd.DataFrame:
    frame = _clean_columns(frame)
    year = _first_column(frame, ("Year",))
    polymer = _first_column(frame, ("Polymer", "Polymer Type"))
    shear = _first_column(frame, ("Shear Rate", "Shear Rate (1/sec)"))
    viscosity = _first_column(frame, ("Apparent Viscosity",))
    out = pd.DataFrame({
        "Year": pd.to_numeric(frame[year], errors="coerce") if year else pd.NA,
        "Polymer": frame[polymer].astype(str).str.strip() if polymer else "Unknown",
        "Shear Rate": pd.to_numeric(frame[shear], errors="coerce") if shear else pd.NA,
        "Apparent Viscosity": pd.to_numeric(frame[viscosity], errors="coerce") if viscosity else pd.NA,
    })
    return out.dropna(subset=["Shear Rate", "Apparent Viscosity"])


def _normalise_phase(frame: pd.DataFrame) -> pd.DataFrame:
    frame = _clean_columns(frame)
    formulation = _first_column(frame, ("Formulation",))
    precip = _first_column(frame, ("Percipitation", "Precipitation"))
    no_precip = _first_column(frame, ("No Percepitation", "No Precipitation"))
    year = _first_column(frame, ("Year",))
    out = pd.DataFrame({
        "Year": pd.to_numeric(frame[year], errors="coerce") if year else pd.NA,
        "Formulation": frame[formulation].astype(str).str.strip() if formulation else "Unknown",
        "Precipitation": pd.to_numeric(frame[precip], errors="coerce") if precip else pd.NA,
        "No Precipitation": pd.to_numeric(frame[no_precip], errors="coerce") if no_precip else pd.NA,
    })
    return out.dropna(subset=["Formulation"])


def _normalise_ift(frame: pd.DataFrame, kind: str) -> pd.DataFrame:
    frame = _clean_columns(frame)
    name = _first_column(frame, ("Surfactant", "Polymer"))
    low = _first_column(frame, ("IFT low", "IFT low dyne/cm"))
    high = _first_column(frame, ("IFT high", "IFT high dyne/cm"))
    year = _first_column(frame, ("Year",))
    out = pd.DataFrame({
        "Year": pd.to_numeric(frame[year], errors="coerce") if year else pd.NA,
        "Material": frame[name].astype(str).str.strip() if name else "Unknown",
        "IFT Low": pd.to_numeric(frame[low], errors="coerce") if low else pd.NA,
        "IFT High": pd.to_numeric(frame[high], errors="coerce") if high else pd.NA,
    })
    out["Material Type"] = kind
    return out.dropna(subset=["Material", "IFT Low", "IFT High"])


def _normalise_adsorption(frame: pd.DataFrame) -> pd.DataFrame:
    frame = _clean_columns(frame)
    year = _first_column(frame, ("Year",))
    field = _first_column(frame, ("Field",))
    surfactant = _first_column(frame, ("Surfactant",))
    days = _first_column(frame, ("Days",))
    adsorption = _first_column(frame, ("Adsorption c/cO", "Adsorption"))
    out = pd.DataFrame({
        "Year": pd.to_numeric(frame[year], errors="coerce") if year else pd.NA,
        "Field": frame[field].astype(str).str.strip() if field else "Unknown",
        "Material": frame[surfactant].astype(str).str.strip() if surfactant else "Unknown",
        "Days": pd.to_numeric(frame[days], errors="coerce") if days else pd.NA,
        "Adsorption c/cO": pd.to_numeric(frame[adsorption], errors="coerce") if adsorption else pd.NA,
    })
    return out.dropna(subset=["Days", "Adsorption c/cO"])


def _normalise_coreflood(frame: pd.DataFrame) -> pd.DataFrame:
    frame = _clean_columns(frame)
    mapping = {
        "Core sample": ("Core sample",),
        "Year": ("Year",),
        "Water Flood": ("Water Flood Recovery, % OOIP",),
        "AS": ("Alkaline- Surfactant (AS) Recovery, % OOIP",),
        "Polymer": ("Polymer (P) Recovery, % OOIP",),
        "Alkaline": ("Alkaline(A) Recovery",),
        "Surfactant": ("Surfactant (S) Recovery",),
        "SP": ("Surfactant +Polymer (SP) Recovery",),
        "ASP": ("Alkali +Surfactant +Polymer (ASP) Recovery",),
        "Sor Reduction AS": ("% Sor Reduction (AS)",),
        "Sor Reduction ASP": ("% Sor Reduction (AS,P)",),
        "Sor Reduction SP": ("% Sor Reduction (SP)",),
    }
    data: dict[str, Any] = {}
    for target, aliases in mapping.items():
        column = _first_column(frame, aliases)
        data[target] = pd.to_numeric(frame[column], errors="coerce") if column and target != "Core sample" else (
            frame[column].astype(str).str.strip() if column else "Unknown"
        )
    out = pd.DataFrame(data)
    out["Year"] = pd.to_numeric(out["Year"], errors="coerce")
    return out.dropna(subset=["Core sample"])


def _derive_sor_from_coreflood(coreflood: pd.DataFrame) -> pd.DataFrame:
    columns = ["Sor Reduction AS", "Sor Reduction ASP", "Sor Reduction SP"]
    available = [column for column in columns if column in coreflood.columns]
    parts = []
    for column in available:
        label = column.replace("Sor Reduction ", "").strip()
        part = coreflood[["Core sample", "Year", column]].copy()
        part = part.rename(columns={column: "Sor Reduction (%)"})
        part["Method"] = label
        parts.append(part)
    if not parts:
        return _empty()
    return pd.concat(parts, ignore_index=True).dropna(subset=["Sor Reduction (%)"])


@st.cache_data(show_spinner=False)
def load_ceor_evidence() -> dict[str, Any]:
    """Load the CEOR evidence panels from the repository workbook."""
    workbook_path = settings.project_root / WORKBOOK_NAME
    if not workbook_path.is_file():
        raise FileNotFoundError(f"Repository CEOR workbook not found: {workbook_path}")

    xlsx = pd.ExcelFile(workbook_path, engine="openpyxl")
    sheets = list(xlsx.sheet_names)
    raw: dict[str, pd.DataFrame] = {}
    source_map: dict[str, str] = {}
    missing: list[str] = []

    for requested, aliases in SHEET_ALIASES.items():
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

    sor = _empty()
    sor_requested_source = source_map.get("Sor_F")
    if sor_requested_source:
        sor_raw = _clean_columns(raw["Sor_F"])
        core = _first_column(sor_raw, ("Core sample", "Core Flood Sample"))
        year = _first_column(sor_raw, ("Year",))
        method = _first_column(sor_raw, ("Method", "Recovery Type", "Sor Reduction Method"))
        value = _first_column(sor_raw, ("Sor Reduction", "Sor Reduction (%)"))
        if core and method and value:
            sor = pd.DataFrame({
                "Core sample": sor_raw[core].astype(str).str.strip(),
                "Year": pd.to_numeric(sor_raw[year], errors="coerce") if year else pd.NA,
                "Method": sor_raw[method].astype(str).str.strip(),
                "Sor Reduction (%)": pd.to_numeric(sor_raw[value], errors="coerce"),
            }).dropna(subset=["Sor Reduction (%)"])

    if sor.empty:
        sor = _derive_sor_from_coreflood(coreflood)

    metadata = {
        "workbook": str(workbook_path),
        "workbook_name": workbook_path.name,
        "sheet_names": sheets,
        "source_map": source_map,
        "missing_requested_sheets": missing,
        "sor_source": sor_requested_source or ("derived from Coreflood" if not sor.empty else None),
        "adsorption_has_temperature": False,
        "adsorption_has_polymer_type": False,
    }

    thermal_source = source_map.get("Thermal")
    if thermal_source:
        thermal = _clean_columns(raw["Thermal"])
        metadata["adsorption_context_years"] = sorted(pd.to_numeric(thermal[_first_column(thermal, ("Year",))], errors="coerce").dropna().unique().tolist()) if _first_column(thermal, ("Year",)) else []
        metadata["adsorption_context_temperatures"] = sorted(pd.to_numeric(thermal[_first_column(thermal, ("Temperature",))], errors="coerce").dropna().unique().tolist()) if _first_column(thermal, ("Temperature",)) else []
        polymer_col = _first_column(thermal, ("Polymer Type", "Polymer"))
        metadata["adsorption_context_polymer_types"] = sorted(thermal[polymer_col].dropna().astype(str).str.strip().unique().tolist()) if polymer_col else []

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
