"""Field-specific laboratory evidence loaders for the R&D workspace.

The St. Joseph workbook is kept separate from the legacy EOR screening workbook.
Source values and units are preserved; questionable source values are flagged,
not silently corrected.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

ST_JOS_WORKBOOK = "St_Jos CEOR (Shared) (1).xlsx"


def _root() -> Path:
    return Path(__file__).resolve().parents[2]


def _clean(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result.columns = [str(c).strip() for c in result.columns]
    return result


def _find_column(frame: pd.DataFrame, terms: tuple[str, ...]) -> str | None:
    keyed = {str(c).strip().casefold(): c for c in frame.columns}
    for term in terms:
        found = keyed.get(term.strip().casefold())
        if found is not None:
            return found
    for column in frame.columns:
        key = str(column).strip().casefold()
        if all(term.casefold() in key for term in terms):
            return column
    return None


def _numeric(frame: pd.DataFrame, terms: tuple[str, ...]) -> pd.Series:
    column = _find_column(frame, terms)
    if column is None:
        return pd.Series(pd.NA, index=frame.index, dtype="Float64")
    return pd.to_numeric(frame[column], errors="coerce")


def _text(frame: pd.DataFrame, terms: tuple[str, ...], default: str = "") -> pd.Series:
    column = _find_column(frame, terms)
    if column is None:
        return pd.Series(default, index=frame.index, dtype="string")
    return frame[column].astype("string").str.strip()


def _phase_tests(xlsx: pd.ExcelFile) -> pd.DataFrame:
    parts: list[pd.DataFrame] = []
    for sheet in ("PB_2003", "PB_2013_A", "PB_2013_S"):
        frame = _clean(pd.read_excel(xlsx, sheet_name=sheet))
        part = pd.DataFrame({
            "Year": _numeric(frame, ("Year",)),
            "Test": _text(frame, ("Number",)),
            "Formulation": _text(frame, ("Formulation (A/S/P)",)),
            "Remarks": _text(frame, ("Remarks",)),
            "Precipitation": _numeric(frame, ("Percipitation",)),
            "No Precipitation": _numeric(frame, ("No Percepitation",)),
            "Source sheet": sheet,
        })
        parts.append(part.dropna(subset=["Formulation"]))
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def _ift_sheet(xlsx: pd.ExcelFile, sheet: str, material_kind: str) -> pd.DataFrame:
    frame = _clean(pd.read_excel(xlsx, sheet_name=sheet))
    name_terms = ("Polymer",) if material_kind == "Polymer" else ("Surfactant",)
    raw_low = _find_column(frame, ("IFT low",))
    raw_high = _find_column(frame, ("IFT high",))
    low_raw = frame[raw_low].astype("string").str.strip() if raw_low else pd.Series(pd.NA, index=frame.index, dtype="string")
    high_raw = frame[raw_high].astype("string").str.strip() if raw_high else pd.Series(pd.NA, index=frame.index, dtype="string")
    low = pd.to_numeric(low_raw, errors="coerce")
    high = pd.to_numeric(high_raw.str.replace("<", "", regex=False), errors="coerce")
    censored = high_raw.str.startswith("<", na=False)
    # Keep the reported values exactly as labelled. These fields are not swapped
    # or sorted, even where the source's low value exceeds its high value.
    material = _text(frame, name_terms)
    out = pd.DataFrame({
        "Material": material,
        "Material type": material_kind,
        "IFT low (source)": low,
        "IFT high (source)": high,
        "IFT low raw": low_raw,
        "IFT high raw": high_raw,
        "IFT high is censored": censored,
        "Year": _numeric(frame, ("Year",)),
        "Source sheet": sheet,
    })
    out = out.dropna(subset=["Material"], how="any")
    return out.reset_index(drop=True)


def _adsorption(xlsx: pd.ExcelFile) -> pd.DataFrame:
    frame = _clean(pd.read_excel(xlsx, sheet_name="Adsorption (St_Jos)"))
    note_column = next((c for c in frame.columns if str(c).startswith("Unnamed: 7")), None)
    note = frame[note_column].astype("string").str.strip() if note_column else pd.Series(pd.NA, index=frame.index, dtype="string")
    mg_g = pd.to_numeric(note.str.extract(r"([0-9]+(?:\.[0-9]+)?)\s*mg/g", expand=False), errors="coerce")
    return pd.DataFrame({
        "Sample": _text(frame, ("Sample No",)),
        "Year": _numeric(frame, ("Year",)),
        "Field": _text(frame, ("Field",)),
        "Surfactant": _text(frame, ("Surfactant",)),
        "Days": _numeric(frame, ("Days",)),
        "Adsorption ratio": _numeric(frame, ("Adsorption c/cO",)),
        "Adsorption (%)": _numeric(frame, ("Adsorption c/cO",)) * 100,
        "Adsorption (mg/g, source note)": mg_g,
        "Source note": note,
    }).dropna(subset=["Adsorption ratio"]).reset_index(drop=True)


def _coreflood(xlsx: pd.ExcelFile) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    summary = _clean(pd.read_excel(xlsx, sheet_name="Coreflood Summary (St_Jos)"))
    core = _clean(pd.read_excel(xlsx, sheet_name="Coreflood (St_Jos)"))
    sor_wide = _clean(pd.read_excel(xlsx, sheet_name="Sor_f (StJoseph)"))

    summary = pd.DataFrame({
        "Core sample": _text(summary, ("Core Floof Sample",)),
        "Year": _numeric(summary, ("Year",)),
        "Treatment type": _text(summary, ("Type",)),
        "Alkali": _text(summary, ("Alkali Type",)),
        "Surfactant": _text(summary, ("Surfactant Type",)),
        "Polymer": _text(summary, ("Polymer Type",)),
        "Source": _text(summary, ("Source",)),
    }).dropna(subset=["Core sample"]).reset_index(drop=True)

    water = pd.DataFrame({
        "Core sample": _text(core, ("Core sample",)),
        "Year": _numeric(core, ("Year",)),
        "Water flood recovery (% OOIP)": _numeric(core, ("Water Flood Recovery, % OOIP",)),
    }).dropna(subset=["Core sample"]).reset_index(drop=True)
    water = water.merge(summary[["Core sample", "Treatment type"]], on="Core sample", how="left")

    stage_specs = (
        ("Surfactant (S)", ("Surfactant (S) Recovery, % OOIP",)),
        ("Alkaline–surfactant (AS)", ("Alkaline- Surfactant (AS) Recovery, % OOIP",)),
        ("Polymer (P)", ("Polymer (P) Recovery, % OOIP",)),
    )
    stage_parts: list[pd.DataFrame] = []
    for method, alias in stage_specs:
        values = _numeric(core, alias)
        part = pd.DataFrame({
            "Core sample": _text(core, ("Core sample",)),
            "Year": _numeric(core, ("Year",)),
            "Method": method,
            "Reported chemical-stage recovery (% OOIP)": values,
        }).dropna(subset=["Reported chemical-stage recovery (% OOIP)"])
        stage_parts.append(part)
    stages = pd.concat(stage_parts, ignore_index=True) if stage_parts else pd.DataFrame()

    recovery_factor_specs = (
        ("Surfactant (S)", ("Recovery Factor (S)",)),
        ("Alkaline–surfactant (AS)", ("Recovery Factor (AS)",)),
        ("Alkaline–surfactant–polymer (AS,P)", ("Recovery Factor (AS,P)",)),
    )
    factor_parts: list[pd.DataFrame] = []
    for method, alias in recovery_factor_specs:
        part = pd.DataFrame({
            "Core sample": _text(core, ("Core sample",)),
            "Year": _numeric(core, ("Year",)),
            "Method": method,
            "Recovery factor (%)": _numeric(core, alias),
        }).dropna(subset=["Recovery factor (%)"])
        factor_parts.append(part)
    factors = pd.concat(factor_parts, ignore_index=True) if factor_parts else pd.DataFrame()

    sor_parts: list[pd.DataFrame] = []
    for column in sor_wide.columns:
        key = str(column).casefold()
        if "sor reduction" not in key:
            continue
        if "(as,p)" in key:
            method = "Alkaline–surfactant–polymer (AS,P)"
        elif "(as)" in key:
            method = "Alkaline–surfactant (AS)"
        elif "(sp)" in key:
            method = "Surfactant–polymer (SP)"
        elif "(p)" in key:
            method = "Polymer (P)"
        elif "(s)" in key:
            method = "Surfactant (S)"
        else:
            method = str(column)
        part = pd.DataFrame({
            "Core sample": _text(sor_wide, ("Core sample",)),
            "Year": _numeric(sor_wide, ("Year",)),
            "Method": method,
            "Sor reduction (%)": pd.to_numeric(sor_wide[column], errors="coerce"),
            "Source field": str(column),
        }).dropna(subset=["Sor reduction (%)"])
        sor_parts.append(part)
    sor = pd.concat(sor_parts, ignore_index=True) if sor_parts else pd.DataFrame()
    return water, stages, factors, sor, summary


@st.cache_data(show_spinner=False)
def load_st_jos_ceor() -> dict[str, Any]:
    """Load and normalize St. Joseph's CEOR laboratory workbook."""
    path = _root() / "data" / ST_JOS_WORKBOOK
    if not path.is_file():
        raise FileNotFoundError(f"St. Joseph CEOR workbook not found: {path}")

    xlsx = pd.ExcelFile(path, engine="openpyxl")
    names = set(xlsx.sheet_names)
    required = {
        "Vis_Shear (St_Jos)", "Phase_Points", "PB_2003", "PB_2013_A",
        "PB_2013_S", "IFT_poly_F", "IFT_sur_F (St_Jos)",
        "Adsorption (St_Jos)", "Coreflood Summary (St_Jos)",
        "Coreflood (St_Jos)", "Sor_f (StJoseph)",
    }
    missing = sorted(required - names)

    vis_raw = _clean(pd.read_excel(xlsx, sheet_name="Vis_Shear (St_Jos)"))
    rheology = pd.DataFrame({
        "Year": _numeric(vis_raw, ("Year",)),
        "Polymer": _text(vis_raw, ("Polymer",)),
        "Salinity (mg/L TDS)": _numeric(vis_raw, ("Salinity",)),
        "Concentration (ppm)": _numeric(vis_raw, ("Concentration",)),
        "Shear rate (1/sec)": _numeric(vis_raw, ("Shear Rate",)),
        "Apparent viscosity (cP)": _numeric(vis_raw, ("Apparent Viscosity",)),
    })
    rheology_source_rows = len(rheology)
    rheology_plot = rheology.dropna(subset=["Shear rate (1/sec)", "Apparent viscosity (cP)"]).copy()

    phase_raw = _clean(pd.read_excel(xlsx, sheet_name="Phase_Points"))
    phase_points = pd.DataFrame({
        "Formulation": _text(phase_raw, ("Formulation",)),
        "Figure": _text(phase_raw, ("Figure",)),
        "Page": _numeric(phase_raw, ("Page",)),
        "Validated": _text(phase_raw, ("Validated",)),
        "Phase": _text(phase_raw, ("Phase",)),
        "TDS (wt%)": _numeric(phase_raw, ("TDS_wt_pct",)),
        "Solubilization (cc/cc)": _numeric(phase_raw, ("Solubilization_cc_per_cc",)),
        "Intersection": _numeric(phase_raw, ("Intersection",)),
        "Type III region min": _numeric(phase_raw, ("TypeIIIRegion_Min",)),
        "Type III region max": _numeric(phase_raw, ("TypeIIIRegion_Max",)),
    }).dropna(subset=["Formulation", "Phase", "TDS (wt%)", "Solubilization (cc/cc)"])

    adsorption = _adsorption(xlsx)
    ift_surf = _ift_sheet(xlsx, "IFT_sur_F (St_Jos)", "Surfactant")
    ift_poly = _ift_sheet(xlsx, "IFT_poly_F", "Polymer")
    phase_tests = _phase_tests(xlsx)
    water, stages, factors, sor, core_summary = _coreflood(xlsx)

    meta = {
        "workbook": str(path),
        "workbook_name": path.name,
        "missing_sheets": missing,
        "rheology_source_rows": rheology_source_rows,
        "rheology_plot_rows": len(rheology_plot),
        "rheology_missing_shear_rate_rows": rheology_source_rows - len(rheology_plot),
        "phase_point_rows": len(phase_points),
        "phase_formulations": int(phase_points["Formulation"].nunique()),
        "phase_validated_rows": int((phase_points["Validated"].str.upper() == "Y").sum()),
        "phase_test_rows": len(phase_tests),
        "ift_rows": len(ift_surf) + len(ift_poly),
        "ift_polymer_reversed_bounds": int((ift_poly["IFT low (source)"] > ift_poly["IFT high (source)"]).sum()),
        "adsorption_rows": len(adsorption),
        "coreflood_samples": int(water["Core sample"].nunique()),
        "sor_records": len(sor),
    }
    return {
        "rheology": rheology,
        "rheology_plot": rheology_plot,
        "phase_points": phase_points,
        "phase_tests": phase_tests,
        "ift_surfactant": ift_surf,
        "ift_polymer": ift_poly,
        "adsorption": adsorption,
        "waterflood": water,
        "chemical_stage_recovery": stages,
        "recovery_factors": factors,
        "sor_reduction": sor,
        "coreflood_summary": core_summary,
        "metadata": meta,
    }
