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
    "field_map": ("map",),
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
    """Normalize primary rheology data without collapsing distinct conditions."""
    frame = _clean_columns(frame)
    out = pd.DataFrame(
        {
            "Year": _numeric(frame, _first_column(frame, ("Year",))),
            "Polymer": _text(frame, _first_column(frame, ("Polymer", "Polymer Type"))),
            "Salinity (mg/L TDS)": _numeric(frame, _first_column(frame, ("Salinity", "Salinity (mg/L TDS)"))),
            "Concentration (ppm)": _numeric(frame, _first_column(frame, ("Concentration", "Concentration (ppm)"))),
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
    """Keep IFT values under their original source labels, including reversed bounds."""
    frame = _clean_columns(frame)
    name = _first_column(frame, ("Surfactant", "Polymer", "Material"))
    low = _first_column(frame, ("IFT low", "IFT low dyne/cm", "IFT low dyne/cm "))
    high = _first_column(frame, ("IFT high", "IFT high dyne/cm", "IFT high dyne/cm "))
    low_raw = (
        frame[low].astype("string").str.strip()
        if low is not None
        else pd.Series(pd.NA, index=frame.index, dtype="string")
    )
    high_raw = (
        frame[high].astype("string").str.strip()
        if high is not None
        else pd.Series(pd.NA, index=frame.index, dtype="string")
    )
    low_values = pd.to_numeric(low_raw, errors="coerce")
    high_values = pd.to_numeric(high_raw.str.replace("<", "", regex=False), errors="coerce")
    out = pd.DataFrame(
        {
            "Year": _numeric(frame, _first_column(frame, ("Year",))),
            "Material": _text(frame, name),
            "IFT Low": low_values,
            "IFT High": high_values,
            "IFT Low raw": low_raw,
            "IFT High raw": high_raw,
            "IFT bounds reversed": low_values.gt(high_values).fillna(False),
            "Material Type": kind,
        }
    )
    # Keep source rows with a material label even when one bound is missing.
    return out.dropna(subset=["Material"]).reset_index(drop=True)


def _canonical_field_name(value: Any) -> str:
    if pd.isna(value):
        return ""
    field = str(value).strip()
    if field.casefold().replace(".", "").strip() == "st joseph":
        return "St. Joseph"
    return field


def _normalise_field_map(frame: pd.DataFrame) -> pd.DataFrame:
    """Read the workbook's field/EOR register without using it to infer lab rows."""
    frame = _clean_columns(frame)
    out = pd.DataFrame(
        {
            "Field": _text(frame, _first_column(frame, ("Field",)), default=""),
            "EOR type": _text(frame, _first_column(frame, ("Types of EOR", "Type of EOR")), default=""),
            "Year": _numeric(frame, _first_column(frame, ("Year",))),
            "Study type": _text(frame, _first_column(frame, ("Type of Study", "Study type")), default=""),
            "Latitude": _numeric(frame, _first_column(frame, ("Latitude",))),
            "Longitude": _numeric(frame, _first_column(frame, ("Longitude",))),
        }
    )
    out["Field"] = out["Field"].map(_canonical_field_name)
    out["EOR type"] = out["EOR type"].astype("string").str.strip()
    # This register also contains WAG, MEOR and other methods. Only CEOR entries
    # belong in the CEOR field selector.
    return (
        out.loc[
            out["Field"].ne("")
            & out["EOR type"].str.contains(r"\bCEOR\b", case=False, na=False)
        ]
        .drop_duplicates()
        .reset_index(drop=True)
    )


def _normalise_thermal(frame: pd.DataFrame) -> pd.DataFrame:
    """Normalize thermal/polymer observations only where the source names a field."""
    frame = _clean_columns(frame)
    field_col = _first_column(frame, ("Field",))
    if field_col is None:
        return pd.DataFrame(
            columns=[
                "Test", "Year", "Field", "Polymer", "Analog", "Viscosity (cP)",
                "Viscosity reduction (%)", "Time (days)",
                "Polymer concentration (ppm)", "Temperature (°C)",
            ]
        )
    out = pd.DataFrame(
        {
            "Test": _text(frame, _first_column(frame, ("No", "Test")), default=""),
            "Year": _numeric(frame, _first_column(frame, ("Year",))),
            "Field": _text(frame, field_col, default="").map(_canonical_field_name),
            "Polymer": _text(frame, _first_column(frame, ("Polymer Type", "Polymer")), default=""),
            "Analog": _text(frame, _first_column(frame, ("Analog",)), default=""),
            "Viscosity (cP)": _numeric(frame, _first_column(frame, ("Viscosity",))),
            "Viscosity reduction (%)": _numeric(frame, _first_column(frame, ("Viscosity reduction",))),
            "Time (days)": _numeric(frame, _first_column(frame, ("Time",))),
            "Polymer concentration (ppm)": _numeric(frame, _first_column(frame, ("Polymer Concentration", "Concentration"))),
            "Temperature (°C)": _numeric(frame, _first_column(frame, ("Temperature",))),
        }
    )
    return out.dropna(subset=["Field"]).loc[lambda data: data["Field"].ne("")].reset_index(drop=True)

def _normalise_adsorption(frame: pd.DataFrame) -> pd.DataFrame:
    frame = _clean_columns(frame)
    temperature_col = _first_column(frame, ("Temperature", "Temperature C", "Temperature (C)", "Temp"))
    polymer_col = _first_column(frame, ("Polymer Type", "Polymer", "Polymer Name"))
    surfactant_col = _first_column(frame, ("Surfactant", "Formulation", "Chemical"))
    out = pd.DataFrame(
        {
            "Year": _numeric(frame, _first_column(frame, ("Year",))),
            "Field": _text(frame, _first_column(frame, ("Field",)), default="").map(_canonical_field_name),
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
        # Support deployments that retain the laboratory workbook in data/.
        fallback = project_root / "data" / WORKBOOK_NAME
        if fallback.is_file():
            workbook_path = fallback
        else:
            raise FileNotFoundError(
                f"Repository CEOR workbook not found at {workbook_path} "
                f"or fallback {fallback}"
            )

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

    field_map = _normalise_field_map(raw.get("field_map", _empty()))
    thermal = _normalise_thermal(raw.get("Thermal", _empty()))

    # The workbook's map sheet is a field/EOR register, not a key that links
    # every laboratory measurement to a field. Only Thermal and Adsorption
    # rows carry explicit field attribution in their own source records.
    mapped_fields = set(field_map["Field"].dropna().astype(str).str.strip())
    thermal_fields = set(thermal["Field"].dropna().astype(str).str.strip())
    adsorption_fields = set(adsorption["Field"].dropna().astype(str).str.strip())
    tagged_fields = thermal_fields | adsorption_fields
    fields = sorted(
        {field for field in mapped_fields | tagged_fields if field},
        key=str.casefold,
    )

    reversed_surf = int(ift_sur["IFT bounds reversed"].sum()) if not ift_sur.empty else 0
    reversed_poly = int(ift_poly["IFT bounds reversed"].sum()) if not ift_poly.empty else 0
    metadata: dict[str, Any] = {
        "workbook": str(workbook_path),
        "workbook_name": workbook_path.name,
        "sheet_names": sheets,
        "source_map": source_map,
        "missing_requested_sheets": missing,
        "sor_source": sor_source,
        "fields": fields,
        "field_map_rows": len(field_map),
        "thermal_rows": len(thermal),
        "thermal_fields": sorted(thermal_fields, key=str.casefold),
        "adsorption_fields": sorted(adsorption_fields, key=str.casefold),
        "ift_surfactant_reversed_bounds": reversed_surf,
        "ift_polymer_reversed_bounds": reversed_poly,
        "ift_reversed_bounds": reversed_surf + reversed_poly,
        "unassigned_laboratory_sheets": [
            "Vis_Shear", "PB_2003", "PB_2013_A", "PB_2013_S",
            "IFT_sur_F", "IFT_poly_F", "Coreflood", "Sor_f",
        ],
        "source_attribution_note": (
            "The map sheet registers fields and EOR methods. It does not assign "
            "the field-unlabeled laboratory rows to individual fields."
        ),
    }

    metadata["adsorption_available_years"] = (
        sorted(adsorption["Year"].dropna().astype(int).unique().tolist())
        if not adsorption.empty else []
    )
    metadata["adsorption_available_temperatures"] = (
        sorted(adsorption["Temperature"].dropna().unique().tolist())
        if "Temperature" in adsorption else []
    )
    metadata["adsorption_available_polymer_types"] = (
        sorted(adsorption["Polymer Type"].dropna().astype(str).unique().tolist(), key=str.casefold)
        if "Polymer Type" in adsorption else []
    )

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
        "field_map": field_map,
        "thermal": thermal,
        "metadata": metadata,
    }
