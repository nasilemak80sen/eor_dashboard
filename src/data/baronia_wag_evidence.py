"""Baronia IWAG evidence loader for the R&D workspace.

Raw workbook values are preserved. Reconciliation and invalid-cell issues are
flagged for review rather than silently corrected.
"""
from __future__ import annotations

from datetime import date, datetime, time
from io import BytesIO
import os
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
from openpyxl.utils.datetime import to_excel

BARONIA_WORKBOOK = "WAG_Copy.xlsx"
REQUIRED_SHEETS = {
    "EOR ATLAS Summary",
    "Coreflood Recovery Data",
    "Field Information",
    "IWAG Results",
    "Core Analysis",
}


def _norm(value: Any) -> str:
    if pd.isna(value):
        return ""
    return " ".join(str(value).strip().casefold().split())


def _table(
    raw: pd.DataFrame,
    headers: list[str],
    *,
    section: str | None = None,
    start_col: int = 0,
    start_row: int = 0,
) -> pd.DataFrame:
    """Extract a named section table by matching its header row."""
    if section:
        section_row = next(
            (i for i in range(len(raw)) if _norm(raw.iat[i, start_col]) == _norm(section)),
            None,
        )
        if section_row is None:
            return pd.DataFrame(columns=headers)
        start_row = section_row + 1

    wanted = [_norm(item) for item in headers]
    header_row = None
    for i in range(start_row, len(raw)):
        actual = [
            _norm(v)
            for v in raw.iloc[i, start_col : start_col + len(headers)].tolist()
        ]
        if actual == wanted:
            header_row = i
            break
    if header_row is None:
        return pd.DataFrame(columns=headers)

    rows = []
    for i in range(header_row + 1, len(raw)):
        values = raw.iloc[i, start_col : start_col + len(headers)].tolist()
        if all(pd.isna(v) for v in values):
            if rows:
                break
            continue
        if _norm(values[0]).startswith("section "):
            break
        rows.append(values)
    return pd.DataFrame(rows, columns=headers)


def _numeric(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    out = frame.copy()
    for column in columns:
        if column in out:
            out[column] = pd.to_numeric(out[column], errors="coerce")
    return out


def _lookup(
    frame: pd.DataFrame,
    label: str,
    *,
    label_col: str,
    value_col: str,
) -> Any:
    if frame.empty or label_col not in frame or value_col not in frame:
        return None
    mask = frame[label_col].astype(str).str.strip().str.casefold().eq(label.casefold())
    return frame.loc[mask, value_col].iloc[0] if mask.any() else None


def _float(value: Any) -> float | None:
    try:
        result = float(value)
        return result if pd.notna(result) else None
    except (TypeError, ValueError):
        return None


def _restore_serial(value: Any) -> Any:
    """Undo Excel date/time formatting for cells known to contain numeric ratios."""
    if isinstance(value, datetime):
        return float(to_excel(value))
    if isinstance(value, date):
        return float(to_excel(datetime.combine(value, time.min)))
    if isinstance(value, time):
        return (value.hour * 3600 + value.minute * 60 + value.second) / 86400
    return value


def _restore_column(
    frame: pd.DataFrame, key_col: str, value_col: str, labels: set[str]
) -> pd.DataFrame:
    out = frame.copy()
    for idx, row in out.iterrows():
        if str(row.get(key_col, "")).strip().casefold() in labels:
            out.at[idx, value_col] = _restore_serial(row.get(value_col))
    return out


def _quality_issues(
    recovery_summary: pd.DataFrame,
    iwag_results: pd.DataFrame,
    recovery_curve: pd.DataFrame,
    cycles: pd.DataFrame,
    design: pd.DataFrame,
    fluid: pd.DataFrame,
) -> pd.DataFrame:
    issues: list[dict[str, str]] = []

    wf = _float(_lookup(recovery_summary, "Waterflood Recovery", label_col="Recovery Stage", value_col="Value"))
    total = _float(_lookup(recovery_summary, "IWAG Recovery (Total)", label_col="Recovery Stage", value_col="Value"))
    increment = _float(_lookup(recovery_summary, "IWAG Incremental Recovery", label_col="Recovery Stage", value_col="Value"))
    iwag_increment = _float(_lookup(iwag_results, "IWAG Recovery over Waterflood", label_col="Parameter", value_col="Value"))
    delta = total - wf if total is not None and wf is not None else None

    def add(severity: str, issue: str, evidence: str, handling: str) -> None:
        issues.append({
            "Severity": severity,
            "Issue": issue,
            "Evidence": evidence,
            "Dashboard handling": handling,
        })

    if delta is not None and increment is not None and abs(delta - increment) > 1:
        add(
            "Review", "Recovery increment does not reconcile",
            f"Summary total ({total:g}%) minus waterflood ({wf:g}%) equals {delta:g} points; the workbook reports {increment:g}.",
            "Show each source value separately; do not select a preferred figure.",
        )
    if iwag_increment is not None and delta is not None and abs(iwag_increment - delta) > 1:
        add(
            "High", "IWAG Results sheet conflicts with recovery summary",
            f"IWAG Results reports {iwag_increment:g}% incremental recovery; summary arithmetic gives {delta:g} points.",
            "Keep both source figures visible pending source adjudication.",
        )
    if not cycles.empty and delta is not None:
        post_wf = cycles.loc[~cycles["Injection Cycle"].astype(str).str.casefold().eq("primary waterflood")]
        cycle_sum = pd.to_numeric(post_wf["Incremental Recovery (%)"], errors="coerce").sum()
        if abs(cycle_sum - delta) > 0.5:
            add(
                "Review", "Cycle-level increments do not reconcile to summary recovery",
                f"Post-waterflood cycle increments sum to {cycle_sum:g} points versus {delta:g} points from the summary.",
                "Show cycle values as recorded; do not rebalance individual stages.",
            )
    if not recovery_curve.empty:
        first_wf = recovery_curve.loc[
            recovery_curve["Injection Phase"].astype(str).str.contains("End 1st WF", case=False, na=False)
        ]
        if not first_wf.empty and wf is not None:
            curve_wf = _float(first_wf.iloc[-1]["Oil Recovery (%)"])
            if curve_wf is not None and abs(curve_wf - wf) > 0.5:
                add(
                    "Review", "Waterflood recovery differs between summary and coreflood curve",
                    f"Summary reports {wf:g}% while the curve marks {curve_wf:g}% at the end of first waterflood.",
                    "Keep the summary KPI and curve distinct and show the discrepancy.",
                )
        saturation_cols = ["Oil Saturation (%)", "Water Saturation (%)", "Gas Saturation (%)"]
        invalid = pd.Series(False, index=recovery_curve.index)
        for column in saturation_cols:
            values = pd.to_numeric(recovery_curve[column], errors="coerce")
            invalid |= values.lt(0) | values.gt(100)
        if invalid.any():
            add(
                "High", "Coreflood saturation profile contains out-of-range values",
                f"{int(invalid.sum())} of {len(recovery_curve)} rows contain a saturation outside 0–100%.",
                "Do not plot this as physical saturation evolution; retain raw records for review.",
            )

    ratio = _float(_lookup(design, "WAG Ratio", label_col="Parameter", value_col="Value"))
    gas_slug = _float(_lookup(design, "Gas Slug Size", label_col="Parameter", value_col="Value"))
    water_slug = _float(_lookup(design, "Water Slug Size", label_col="Parameter", value_col="Value"))
    if ratio is not None and gas_slug is not None and water_slug not in (None, 0):
        add(
            "Review", "WAG ratio value needs source confirmation",
            f"Ratio cell is stored as {ratio:.8f} of an Excel day (time-formatted); equal slug sizes ({gas_slug:g} and {water_slug:g} PV) imply 1:1.",
            "Do not display the malformed ratio as valid; show gas and water slug sizes separately.",
        )

    c12 = _float(_lookup(fluid, "C12+ Content Range", label_col="Parameter", value_col="Value"))
    if c12 is not None and c12 > 100:
        add(
            "High", "C12+ composition value is not a valid molar percentage",
            f"C12+ is stored as Excel serial {c12:g} in a date-formatted cell.",
            "Exclude this value from composition charts until the source range is confirmed.",
        )

    return pd.DataFrame(issues, columns=["Severity", "Issue", "Evidence", "Dashboard handling"])


@st.cache_data(show_spinner=False)
def load_baronia_wag(
    workbook_path: str | None = None,
    workbook_bytes: bytes | None = None,
    workbook_name: str | None = None,
) -> dict[str, Any]:
    """Load Baronia IWAG evidence from a local workbook or uploaded file."""
    if workbook_bytes is not None:
        source: Any = BytesIO(workbook_bytes)
        source_name = workbook_name or BARONIA_WORKBOOK
        source_path = source_name
    else:
        if workbook_path:
            path = Path(workbook_path)
        else:
            configured = os.environ.get("BARONIA_WAG_WORKBOOK")
            candidates = ([Path(configured)] if configured else []) + [
                Path(__file__).resolve().parents[2] / "data" / BARONIA_WORKBOOK,
                Path(__file__).resolve().parents[2] / "data" / "Baronia_WAG_Data_EOR_ATLAS_unencrypted.xlsx",
            ]
            path = next((item for item in candidates if item.is_file()), candidates[-1])
        if not path.is_file():
            raise FileNotFoundError(
                "Upload the unlocked Baronia .xlsx file in the WAG tab, "
                f"place it at {Path(__file__).resolve().parents[2] / 'data' / BARONIA_WORKBOOK}, "
                "or set BARONIA_WAG_WORKBOOK."
            )
        source = path
        source_name = path.name
        source_path = str(path)

    xlsx = pd.ExcelFile(source, engine="openpyxl")
    sheet_names = set(xlsx.sheet_names)
    missing = sorted(REQUIRED_SHEETS - sheet_names)
    if missing:
        raise ValueError("Baronia workbook is missing sheets: " + ", ".join(missing))

    summary_raw = pd.read_excel(xlsx, sheet_name="EOR ATLAS Summary", header=None)
    coreflood_raw = pd.read_excel(xlsx, sheet_name="Coreflood Recovery Data", header=None)
    field_raw = pd.read_excel(xlsx, sheet_name="Field Information", header=None)
    iwag_raw = pd.read_excel(xlsx, sheet_name="IWAG Results", header=None)
    core_raw = pd.read_excel(xlsx, sheet_name="Core Analysis", header=None)

    summary_metrics = _table(summary_raw, ["Metric", "Value"])
    summary_field = _table(summary_raw, ["Item", "Value"], start_col=3)
    hysteresis_summary = _table(summary_raw, ["Parameter", "Value"], start_row=17)
    saturation_endpoints = _table(summary_raw, ["Parameter", "Value"], start_col=3, start_row=17)

    recovery_summary = _numeric(_table(
        coreflood_raw, ["Recovery Stage", "Value", "Unit"],
        section="SECTION 1: COREFLOOD RECOVERY SUMMARY",
    ), ["Value"])
    recovery_curve = _numeric(_table(
        coreflood_raw,
        ["PV Injected", "Oil Recovery (Fraction)", "Oil Recovery (%)", "Injection Phase",
         "Oil Saturation (%)", "Water Saturation (%)", "Gas Saturation (%)"],
        section="SECTION 2: OIL RECOVERY VS PORE VOLUME INJECTED",
    ), ["PV Injected", "Oil Recovery (Fraction)", "Oil Recovery (%)",
        "Oil Saturation (%)", "Water Saturation (%)", "Gas Saturation (%)"])
    recovery_curve = recovery_curve.dropna(subset=["PV Injected", "Oil Recovery (%)"]).reset_index(drop=True)

    production_curve = _numeric(_table(
        coreflood_raw,
        ["PV Injected", "Cumulative Oil (cc)", "Cumulative Gas (cc)", "Cumulative Water (cc)", "Injection Phase"],
        section="SECTION 3: CUMULATIVE PRODUCTION DATA",
    ), ["PV Injected", "Cumulative Oil (cc)", "Cumulative Gas (cc)", "Cumulative Water (cc)"])
    production_curve = production_curve.dropna(subset=["PV Injected"]).reset_index(drop=True)

    saturation_endpoints_core = _table(
        coreflood_raw, ["Parameter", "Value", "Notes"],
        section="SECTION 4: SATURATION END POINTS",
    )
    cycles = _numeric(_table(
        coreflood_raw,
        ["Injection Cycle", "PV Start", "PV End", "Recovery at End (%)", "Incremental Recovery (%)"],
        section="SECTION 5: RECOVERY BY INJECTION CYCLE",
    ), ["PV Start", "PV End", "Recovery at End (%)", "Incremental Recovery (%)"])
    cycles = cycles.dropna(subset=["Injection Cycle"]).reset_index(drop=True)
    material_balance = _table(
        coreflood_raw, ["Parameter", "Value", "Unit"],
        section="SECTION 6: COREFLOOD MATERIAL BALANCE",
    )

    field_info = _table(field_raw, ["Parameter", "Value", "Unit", "Notes"], section="SECTION 1: FIELD INFORMATION")
    reservoir_properties = _table(field_raw, ["Parameter", "Value", "Unit", "Notes"], section="SECTION 2: RESERVOIR PROPERTIES (RV2)")
    fluid_properties = _table(field_raw, ["Parameter", "Value", "Unit", "Notes"], section="SECTION 3: FLUID PROPERTIES (RV2)")
    design_parameters = _table(field_raw, ["Parameter", "Value", "Unit", "Notes"], section="SECTION 4: IWAG DESIGN PARAMETERS")
    design_parameters = _restore_column(design_parameters, "Parameter", "Value", {"wag ratio"})
    fluid_properties = _restore_column(fluid_properties, "Parameter", "Value", {"c12+ content range"})
    gas_composition = _table(
        field_raw, ["Component", "Mol%", "Notes"],
        section="SECTION 5: INJECTION GAS COMPOSITION (Baronia Export Gas)",
    )
    gas_composition = _numeric(gas_composition, ["Mol%"])
    gas_composition = gas_composition.loc[
        gas_composition["Component"].notna()
        & gas_composition["Component"].astype(str).str.strip().str.casefold().ne("total")
    ].reset_index(drop=True)

    iwag_results = _table(
        iwag_raw, ["Parameter", "Value", "Unit", "Notes"],
        section="SECTION 1: IWAG RECOVERY RESULTS",
    )
    iwag_results = _numeric(iwag_results, ["Value"])
    hysteresis_model = _numeric(_table(
        iwag_raw, ["Parameter", "Symbol", "Value", "Description"],
        section="SECTION 2: HYSTERESIS MODEL PARAMETERS (WAGHYSTR - Eclipse 100)",
    ), ["Value"])
    corey_parameters = _table(
        iwag_raw, ["Parameter", "Symbol", "Water-Oil", "Gas-Oil", "Unit", "Source"],
        section="SECTION 3: COREY RELATIVE PERMEABILITY PARAMETERS",
    )
    trapped_gas = _table(
        iwag_raw, ["Parameter", "Value", "Unit", "Description"],
        section="SECTION 4: TRAPPED GAS CORRELATION (Land's Equation)",
    )
    simulation_properties = _table(
        iwag_raw, ["Parameter", "Value", "Unit", "Notes"],
        section="SECTION 5: SIMULATION MODEL PROPERTIES",
    )

    core_samples = _numeric(_table(
        core_raw,
        ["Sample", "Depth (ft)", "Porosity (%)", "Kh (md)", "Kv (md)", "Kv/Kh", "Facies", "Selected"],
        section="SECTION 1: CORE SAMPLE DATA (BN-69 RV2)",
    ), ["Sample", "Depth (ft)", "Porosity (%)", "Kh (md)", "Kv (md)", "Kv/Kh"])
    core_samples = core_samples.dropna(subset=["Sample"]).reset_index(drop=True)
    composite_core = _table(
        core_raw, ["Property", "Value", "Unit", "Notes"],
        section="SECTION 2: COMPOSITE CORE PROPERTIES (4 PLUGS USED IN EXPERIMENT)",
    )
    facies = _table(core_raw, ["Facies Code", "Description", "Quality"], section="SECTION 3: FACIES DESCRIPTION")
    scal_summary = _table(
        core_raw, ["Test", "Parameter", "Value Range", "Unit"],
        section="SECTION 4: SPECIAL CORE ANALYSIS (SCAL) RESULTS SUMMARY",
    )

    issues = _quality_issues(recovery_summary, iwag_results, recovery_curve, cycles, design_parameters, fluid_properties)
    gas_total = float(gas_composition["Mol%"].sum()) if not gas_composition.empty else None
    metadata = {
        "workbook_name": source_name,
        "workbook_path": source_path,
        "source_report": "T2 Advanced Gas EOR for Baronia - Final Report (PRSB-EOR-14-25, July 2014)",
        "sheets": sorted(sheet_names),
        "missing_sheets": missing,
        "recovery_curve_rows": len(recovery_curve),
        "production_curve_rows": len(production_curve),
        "cycle_rows": len(cycles),
        "core_samples": len(core_samples),
        "selected_core_samples": int(core_samples["Selected"].astype(str).str.strip().str.casefold().eq("yes").sum()) if not core_samples.empty else 0,
        "gas_components": len(gas_composition),
        "gas_composition_total_mol_pct": gas_total,
        "quality_issue_count": len(issues),
    }
    return {
        "summary_metrics": summary_metrics,
        "summary_field": summary_field,
        "hysteresis_summary": hysteresis_summary,
        "saturation_endpoints": saturation_endpoints,
        "recovery_summary": recovery_summary,
        "iwag_recovery": iwag_results,
        "recovery_curve": recovery_curve,
        "production_curve": production_curve,
        "saturation_endpoints_core": saturation_endpoints_core,
        "cycle_recovery": cycles,
        "material_balance": material_balance,
        "field_info": field_info,
        "reservoir_properties": reservoir_properties,
        "fluid_properties": fluid_properties,
        "design_parameters": design_parameters,
        "gas_composition": gas_composition,
        "hysteresis_model": hysteresis_model,
        "corey_parameters": corey_parameters,
        "trapped_gas": trapped_gas,
        "simulation_properties": simulation_properties,
        "core_samples": core_samples,
        "composite_core": composite_core,
        "facies": facies,
        "scal_summary": scal_summary,
        "quality_issues": issues,
        "metadata": metadata,
    }
