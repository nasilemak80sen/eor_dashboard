"""Baronia IWAG evidence loader for the R&D workspace.

Raw workbook values are preserved. Reconciliation and invalid-cell issues are
flagged for review rather than silently corrected.
"""
from __future__ import annotations

from datetime import date, datetime, time
from hashlib import sha256
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
    """Parse numeric cells, preserving an approximate value such as '~2.0' numerically."""
    try:
        result = float(value)
    except (TypeError, ValueError):
        text = str(value).strip().replace(",", "")
        if text.startswith("~"):
            text = text[1:].strip()
        try:
            result = float(text)
        except (TypeError, ValueError):
            return None
    return result if pd.notna(result) else None


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



def _ordinal_label(number: int) -> str:
    if number % 100 in (11, 12, 13):
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")
    return f"{number}{suffix}"


def _curve_waterflood_point(recovery_curve: pd.DataFrame) -> tuple[float | None, float | None]:
    if recovery_curve.empty or "Injection Phase" not in recovery_curve:
        return None, None
    first_wf = recovery_curve.loc[
        recovery_curve["Injection Phase"].astype(str).str.contains(
            "End 1st WF", case=False, na=False
        )
    ]
    if first_wf.empty:
        return None, None
    row = first_wf.sort_values("PV Injected").iloc[-1]
    return _float(row.get("PV Injected")), _float(row.get("Oil Recovery (%)"))


def _build_cycle_reconciliation(
    cycles: pd.DataFrame,
    design: pd.DataFrame,
    recovery_curve: pd.DataFrame,
) -> pd.DataFrame:
    """Compare expected gas/water stages with reported cycle rows and curve phase labels."""
    count = _float(_lookup(
        design, "Number of WAG Cycles", label_col="Parameter", value_col="Value"
    ))
    expected_labels: list[str] = []
    if count is not None and count >= 1 and count.is_integer():
        for number in range(1, int(count) + 1):
            ordinal = _ordinal_label(number)
            expected_labels.extend([f"{ordinal} Gas Cycle", f"{ordinal} Water Cycle"])

    actual = cycles.copy()
    if not actual.empty and "Injection Cycle" in actual:
        actual = actual.loc[
            ~actual["Injection Cycle"].astype(str).str.strip().str.casefold().eq("primary waterflood")
        ]
    else:
        actual = pd.DataFrame(columns=cycles.columns)

    actual_by_label = {_norm(row.get("Injection Cycle")): row for _, row in actual.iterrows()}
    curve = recovery_curve.copy()
    if not curve.empty and "PV Injected" in curve:
        curve["PV Injected"] = pd.to_numeric(curve["PV Injected"], errors="coerce")
        curve = curve.dropna(subset=["PV Injected"]).sort_values("PV Injected")

    rows: list[dict[str, Any]] = []
    for expected in expected_labels:
        found = actual_by_label.get(_norm(expected))
        pv_start = _float(found.get("PV Start")) if found is not None else None
        pv_end = _float(found.get("PV End")) if found is not None else None
        increment = _float(found.get("Incremental Recovery (%)")) if found is not None else None
        phase = None
        alignment = "Not checked"
        if found is not None and pv_start is not None and not curve.empty:
            at_start = curve.loc[(curve["PV Injected"] - pv_start).abs() <= 0.0100001]
            selected = at_start.iloc[0] if not at_start.empty else None
            if selected is None:
                after_start = curve.loc[curve["PV Injected"] >= pv_start]
                selected = after_start.iloc[0] if not after_start.empty else None
            if selected is not None:
                phase = str(selected.get("Injection Phase", "")).strip()
                expected_ordinal, expected_name = expected.casefold().split(maxsplit=1)
                expected_kind = "gas" if "gas" in expected_name else "water"
                phase_text = phase.casefold()
                if expected_kind in phase_text and expected_ordinal in phase_text:
                    alignment = "Aligned"
                elif "gas" in phase_text or "water" in phase_text:
                    alignment = "Conflict"

        rows.append({
            "Expected stage": expected,
            "Workbook stage": str(found.get("Injection Cycle")) if found is not None else None,
            "PV Start": pv_start,
            "PV End": pv_end,
            "Incremental Recovery (pp)": increment,
            "Recovery-curve phase at PV start": phase,
            "Presence": "Present" if found is not None else "Missing",
            "Phase alignment": alignment,
        })

    expected_set = {_norm(label) for label in expected_labels}
    for _, row in actual.iterrows():
        label = str(row.get("Injection Cycle", "")).strip()
        if _norm(label) not in expected_set:
            rows.append({
                "Expected stage": None,
                "Workbook stage": label,
                "PV Start": _float(row.get("PV Start")),
                "PV End": _float(row.get("PV End")),
                "Incremental Recovery (pp)": _float(row.get("Incremental Recovery (%)")),
                "Recovery-curve phase at PV start": None,
                "Presence": "Unexpected",
                "Phase alignment": "Not checked",
            })

    return pd.DataFrame(rows, columns=[
        "Expected stage", "Workbook stage", "PV Start", "PV End",
        "Incremental Recovery (pp)", "Recovery-curve phase at PV start",
        "Presence", "Phase alignment",
    ])


def _build_pv_reconciliation(
    recovery_summary: pd.DataFrame,
    recovery_curve: pd.DataFrame,
    production_curve: pd.DataFrame,
    design: pd.DataFrame,
    material_balance: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, float | None]]:
    """Calculate injection-design PV and compare it with all reported PV evidence."""
    first_wf = _float(_lookup(design, "First Waterflood", label_col="Parameter", value_col="Value"))
    gas_slug = _float(_lookup(design, "Gas Slug Size", label_col="Parameter", value_col="Value"))
    water_slug = _float(_lookup(design, "Water Slug Size", label_col="Parameter", value_col="Value"))
    cycle_count = _float(_lookup(design, "Number of WAG Cycles", label_col="Parameter", value_col="Value"))
    reported_total = _float(_lookup(design, "Total Fluid Injected", label_col="Parameter", value_col="Value"))

    wag_expected = cycle_count * (gas_slug + water_slug) if (
        cycle_count is not None and gas_slug is not None and water_slug is not None
    ) else None
    total_expected = first_wf + wag_expected if (
        first_wf is not None and wag_expected is not None
    ) else None
    water_expected = first_wf + cycle_count * water_slug if (
        first_wf is not None and cycle_count is not None and water_slug is not None
    ) else None
    gas_expected = cycle_count * gas_slug if (
        cycle_count is not None and gas_slug is not None
    ) else None

    balance_water = _float(_lookup(material_balance, "Total Water Injected", label_col="Parameter", value_col="Value"))
    balance_gas = _float(_lookup(material_balance, "Total Gas Injected", label_col="Parameter", value_col="Value"))
    balance_total = balance_water + balance_gas if (
        balance_water is not None and balance_gas is not None
    ) else None
    summary_total = _float(_lookup(
        recovery_summary, "Total Pore Volumes Injected",
        label_col="Recovery Stage", value_col="Value",
    ))
    curve_end = (
        _float(pd.to_numeric(recovery_curve["PV Injected"], errors="coerce").max())
        if not recovery_curve.empty and "PV Injected" in recovery_curve else None
    )
    production_end = (
        _float(pd.to_numeric(production_curve["PV Injected"], errors="coerce").max())
        if not production_curve.empty and "PV Injected" in production_curve else None
    )
    curve_wf_pv, _ = _curve_waterflood_point(recovery_curve)
    observed_wag_span = curve_end - curve_wf_pv if (
        curve_end is not None and curve_wf_pv is not None
    ) else None

    def status(value: float | None, reference: float | None) -> str:
        if value is None or reference is None:
            return "Not available"
        return "Reconciles" if abs(value - reference) <= 0.05 else "Conflict"

    rows = [
        {"Measure": "Initial waterflood design", "Value": first_wf, "Unit": "PV", "Source": "Field Information · IWAG design", "Comparison": "Design input"},
        {"Measure": "Observed waterflood endpoint", "Value": curve_wf_pv, "Unit": "PV", "Source": "Coreflood Recovery Data · recovery curve", "Comparison": status(curve_wf_pv, first_wf)},
        {"Measure": "Expected WAG slug volume", "Value": wag_expected, "Unit": "PV", "Source": "Derived: cycles × (gas slug + water slug)", "Comparison": "Design arithmetic"},
        {"Measure": "Expected total injection", "Value": total_expected, "Unit": "PV", "Source": "Derived: initial waterflood + all WAG slugs", "Comparison": "Design arithmetic"},
        {"Measure": "Field-reported total fluid injected", "Value": reported_total, "Unit": "PV", "Source": "Field Information · IWAG design", "Comparison": status(reported_total, total_expected)},
        {"Measure": "Material-balance water injected", "Value": balance_water, "Unit": "PV", "Source": "Coreflood Recovery Data · material balance", "Comparison": status(balance_water, water_expected)},
        {"Measure": "Material-balance gas injected", "Value": balance_gas, "Unit": "PV", "Source": "Coreflood Recovery Data · material balance", "Comparison": status(balance_gas, gas_expected)},
        {"Measure": "Material-balance total injected", "Value": balance_total, "Unit": "PV", "Source": "Derived: material-balance water + gas", "Comparison": status(balance_total, total_expected)},
        {"Measure": "Coreflood-summary total injected", "Value": summary_total, "Unit": "PV", "Source": "Coreflood Recovery Data · recovery summary", "Comparison": status(summary_total, total_expected)},
        {"Measure": "Recovery-curve PV endpoint", "Value": curve_end, "Unit": "PV", "Source": "Coreflood Recovery Data · recovery curve", "Comparison": status(curve_end, total_expected)},
        {"Measure": "Production-curve PV endpoint", "Value": production_end, "Unit": "PV", "Source": "Coreflood Recovery Data · production curve", "Comparison": status(production_end, total_expected)},
        {"Measure": "Observed post-waterflood PV span", "Value": observed_wag_span, "Unit": "PV", "Source": "Derived: recovery-curve endpoint − waterflood endpoint", "Comparison": status(observed_wag_span, wag_expected)},
    ]
    metrics = {
        "first_wf_design": first_wf,
        "gas_slug": gas_slug,
        "water_slug": water_slug,
        "cycle_count": cycle_count,
        "expected_wag": wag_expected,
        "expected_total": total_expected,
        "expected_water": water_expected,
        "expected_gas": gas_expected,
        "reported_total_design": reported_total,
        "balance_water": balance_water,
        "balance_gas": balance_gas,
        "balance_total": balance_total,
        "summary_total": summary_total,
        "curve_end": curve_end,
        "production_end": production_end,
        "curve_wf_pv": curve_wf_pv,
        "observed_wag_span": observed_wag_span,
    }
    return pd.DataFrame(rows), metrics


def _build_recovery_reconciliation(
    recovery_summary: pd.DataFrame,
    iwag_results: pd.DataFrame,
    recovery_curve: pd.DataFrame,
    cycles: pd.DataFrame,
) -> pd.DataFrame:
    """Show source claims and arithmetic-derived recovery values side by side."""
    wf = _float(_lookup(recovery_summary, "Waterflood Recovery", label_col="Recovery Stage", value_col="Value"))
    total = _float(_lookup(recovery_summary, "IWAG Recovery (Total)", label_col="Recovery Stage", value_col="Value"))
    increment = _float(_lookup(recovery_summary, "IWAG Incremental Recovery", label_col="Recovery Stage", value_col="Value"))
    iwag_increment = _float(_lookup(iwag_results, "IWAG Recovery over Waterflood", label_col="Parameter", value_col="Value"))
    hyst = _float(_lookup(iwag_results, "Recovery from Hysteresis Effects", label_col="Parameter", value_col="Value"))
    displacement = _float(_lookup(iwag_results, "Recovery from Gas Displacement", label_col="Parameter", value_col="Value"))
    curve = recovery_curve.sort_values("PV Injected") if not recovery_curve.empty else recovery_curve
    curve_wf_pv, curve_wf = _curve_waterflood_point(curve)
    curve_final = _float(curve.iloc[-1]["Oil Recovery (%)"]) if (
        not curve.empty and "Oil Recovery (%)" in curve
    ) else None
    curve_increment = curve_final - curve_wf if (
        curve_final is not None and curve_wf is not None
    ) else None
    cycle_increment = None
    if not cycles.empty and "Incremental Recovery (%)" in cycles:
        post_wf = cycles.loc[
            ~cycles["Injection Cycle"].astype(str).str.casefold().eq("primary waterflood")
        ]
        cycle_increment = _float(pd.to_numeric(
            post_wf["Incremental Recovery (%)"], errors="coerce"
        ).sum(min_count=1))
    component_sum = hyst + displacement if (
        hyst is not None and displacement is not None
    ) else None

    def compare(value: float | None, reference: float | None) -> str:
        if value is None or reference is None:
            return "Not available"
        return "Reconciles" if abs(value - reference) <= 0.5 else "Conflict"

    arithmetic = total - wf if total is not None and wf is not None else None
    rows = [
        {"Measure": "Waterflood recovery", "Value": wf, "Unit": "% OOIP", "Source": "Coreflood summary", "Comparison": "Source-reported"},
        {"Measure": "Waterflood recovery at curve endpoint", "Value": curve_wf, "Unit": "% OOIP", "Source": f"Recovery curve at {curve_wf_pv:g} PV" if curve_wf_pv is not None else "Recovery curve", "Comparison": compare(curve_wf, wf)},
        {"Measure": "Final recovery", "Value": total, "Unit": "% OOIP", "Source": "Coreflood summary", "Comparison": "Source-reported"},
        {"Measure": "Final recovery at curve endpoint", "Value": curve_final, "Unit": "% OOIP", "Source": "Recovery curve", "Comparison": compare(curve_final, total)},
        {"Measure": "IWAG incremental recovery", "Value": increment, "Unit": "pp", "Source": "Coreflood summary", "Comparison": "Source-reported"},
        {"Measure": "Summary arithmetic (total − waterflood)", "Value": arithmetic, "Unit": "pp", "Source": "Derived from coreflood summary", "Comparison": compare(arithmetic, increment)},
        {"Measure": "IWAG Results increment", "Value": iwag_increment, "Unit": "pp", "Source": "IWAG Results sheet", "Comparison": compare(iwag_increment, increment)},
        {"Measure": "Hysteresis + gas displacement", "Value": component_sum, "Unit": "pp", "Source": "IWAG Results components", "Comparison": compare(component_sum, iwag_increment)},
        {"Measure": "Cycle increments summed", "Value": cycle_increment, "Unit": "pp", "Source": "Recovery-by-injection-cycle table", "Comparison": compare(cycle_increment, increment)},
        {"Measure": "Recovery-curve increment", "Value": curve_increment, "Unit": "pp", "Source": "Derived from final recovery − curve waterflood recovery", "Comparison": compare(curve_increment, increment)},
    ]
    return pd.DataFrame(rows)


def _quality_issues(
    recovery_summary: pd.DataFrame,
    iwag_results: pd.DataFrame,
    recovery_curve: pd.DataFrame,
    cycles: pd.DataFrame,
    design: pd.DataFrame,
    fluid: pd.DataFrame,
    material_balance: pd.DataFrame | None = None,
    production_curve: pd.DataFrame | None = None,
) -> pd.DataFrame:
    issues: list[dict[str, str]] = []
    material_balance = material_balance if material_balance is not None else pd.DataFrame()
    production_curve = production_curve if production_curve is not None else pd.DataFrame()

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

    if delta is not None and increment is not None and abs(delta - increment) > 0.5:
        add(
            "Review", "Recovery increment does not reconcile",
            f"Summary total ({total:g}%) minus waterflood ({wf:g}%) equals {delta:g} points; the workbook reports {increment:g}.",
            "Show reported increment and summary arithmetic separately pending source adjudication.",
        )
    if iwag_increment is not None and delta is not None and abs(iwag_increment - delta) > 0.5:
        add(
            "High", "IWAG Results sheet conflicts with recovery summary",
            f"IWAG Results reports {iwag_increment:g} percentage points; summary arithmetic gives {delta:g} points.",
            "Keep both source figures visible. Do not select a preferred increment.",
        )

    recovery_reconciliation = _build_recovery_reconciliation(
        recovery_summary, iwag_results, recovery_curve, cycles
    )
    curve_increment_rows = recovery_reconciliation.loc[
        recovery_reconciliation["Measure"].eq("Recovery-curve increment")
    ]
    curve_increment = _float(curve_increment_rows.iloc[0]["Value"]) if not curve_increment_rows.empty else None
    if not cycles.empty and delta is not None and "Incremental Recovery (%)" in cycles:
        post_wf = cycles.loc[
            ~cycles["Injection Cycle"].astype(str).str.casefold().eq("primary waterflood")
        ]
        cycle_sum = pd.to_numeric(
            post_wf["Incremental Recovery (%)"], errors="coerce"
        ).sum(min_count=1)
        if pd.notna(cycle_sum) and abs(float(cycle_sum) - delta) > 0.5:
            add(
                "Review", "Cycle-level increments do not reconcile to summary recovery",
                f"Post-waterflood cycle increments sum to {float(cycle_sum):g} points versus {delta:g} points from summary arithmetic.",
                "Show cycle values as recorded; do not rebalance individual stages.",
            )
        if curve_increment is not None and pd.notna(cycle_sum) and abs(float(cycle_sum) - curve_increment) > 0.5:
            add(
                "Review", "Cycle increments do not reconcile to recovery-curve increment",
                f"Cycle increments sum to {float(cycle_sum):g} points while the recovery curve implies {curve_increment:g} points.",
                "Retain cycle and curve values independently until their source definitions are confirmed.",
            )

    if not recovery_curve.empty:
        curve_wf_pv, curve_wf = _curve_waterflood_point(recovery_curve)
        if curve_wf is not None and wf is not None and abs(curve_wf - wf) > 0.5:
            add(
                "Review", "Waterflood recovery differs between summary and coreflood curve",
                f"Summary reports {wf:g}% at waterflood; curve marks {curve_wf:g}% at {curve_wf_pv:g} PV.",
                "Keep summary KPI and curve endpoint distinct and show the discrepancy.",
            )
        saturation_cols = [
            column for column in
            ["Oil Saturation (%)", "Water Saturation (%)", "Gas Saturation (%)"]
            if column in recovery_curve
        ]
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

    pv_table, pv = _build_pv_reconciliation(
        recovery_summary, recovery_curve, production_curve, design, material_balance
    )
    expected_total = pv["expected_total"]
    expected_wag = pv["expected_wag"]
    if expected_total is not None and pv["reported_total_design"] is not None:
        if abs(pv["reported_total_design"] - expected_total) > 0.05:
            add(
                "High", "Reported total injected PV conflicts with the design schedule",
                f"Design arithmetic gives {expected_total:g} PV; Field Information reports approximately {pv['reported_total_design']:g} PV total fluid injected.",
                "Show both values and flag the schedule discrepancy; do not change the source total.",
            )

    if expected_total is not None:
        endpoint_conflicts = [
            f"{label} ends at {value:g} PV"
            for label, value in (
                ("coreflood summary", pv["summary_total"]),
                ("recovery curve", pv["curve_end"]),
                ("production curve", pv["production_end"]),
            )
            if value is not None and abs(value - expected_total) > 0.05
        ]
        if endpoint_conflicts:
            add(
                "High", "Coreflood PV endpoints conflict with the injection design",
                f"Design arithmetic gives {expected_total:g} PV; " + "; ".join(endpoint_conflicts) + ".",
                "Display source endpoints and design-derived total side by side; do not stretch or rescale either curve.",
            )
        if pv["balance_total"] is not None and abs(pv["balance_total"] - expected_total) > 0.05:
            add(
                "High", "Material-balance injected PV does not reconcile to the design",
                f"Material balance totals {pv['balance_total']:g} PV (water {pv['balance_water']:g} + gas {pv['balance_gas']:g}); design arithmetic gives {expected_total:g} PV.",
                "Keep water and gas totals visible and investigate the source calculation.",
            )

    if pv["expected_water"] is not None and pv["balance_water"] is not None:
        if abs(pv["balance_water"] - pv["expected_water"]) > 0.05:
            add(
                "Review", "Material-balance water injection differs from the slug schedule",
                f"Expected water is {pv['expected_water']:g} PV (initial waterflood plus water slugs); material balance reports {pv['balance_water']:g} PV.",
                "Preserve both totals pending reconciliation of primary waterflood and WAG water slugs.",
            )
    if pv["expected_gas"] is not None and pv["balance_gas"] is not None:
        if abs(pv["balance_gas"] - pv["expected_gas"]) > 0.05:
            add(
                "Review", "Material-balance gas injection differs from the slug schedule",
                f"Expected gas is {pv['expected_gas']:g} PV; material balance reports {pv['balance_gas']:g} PV.",
                "Preserve both totals pending reconciliation of the gas-slug schedule.",
            )
    if (
        pv["first_wf_design"] is not None and pv["curve_wf_pv"] is not None
        and abs(pv["first_wf_design"] - pv["curve_wf_pv"]) > 0.05
    ):
        add(
            "High", "Initial waterflood PV differs between design and recovery curve",
            f"Field Information specifies {pv['first_wf_design']:g} PV initial waterflood; recovery curve marks its endpoint at {pv['curve_wf_pv']:g} PV.",
            "Do not rebase the PV axis. Preserve design and curve endpoints as separate source claims.",
        )
    if (
        expected_wag is not None and pv["observed_wag_span"] is not None
        and abs(expected_wag - pv["observed_wag_span"]) > 0.05
    ):
        add(
            "High", "Observed post-waterflood PV span differs from the WAG slug schedule",
            f"Design implies {expected_wag:g} PV of WAG slugs; recovery curve spans {pv['observed_wag_span']:g} PV after its waterflood endpoint.",
            "Retain observed PV axis and scheduled slug volume separately pending source verification.",
        )

    cycle_reconciliation = _build_cycle_reconciliation(cycles, design, recovery_curve)
    missing = cycle_reconciliation.loc[cycle_reconciliation["Presence"].eq("Missing")]
    unexpected = cycle_reconciliation.loc[cycle_reconciliation["Presence"].eq("Unexpected")]
    if not missing.empty or not unexpected.empty:
        parts = []
        if not missing.empty:
            parts.append("missing expected stages: " + ", ".join(missing["Expected stage"].astype(str)))
        if not unexpected.empty:
            parts.append("unexpected source stages: " + ", ".join(unexpected["Workbook stage"].astype(str)))
        cycle_count = int(pv["cycle_count"]) if pv["cycle_count"] is not None else "unspecified"
        add(
            "High", "Injection-cycle sequence is incomplete",
            "; ".join(parts) + f"; design specifies {cycle_count} WAG cycles.",
            "Show missing/extra stages explicitly; do not invent a missing recovery increment.",
        )

    if not cycles.empty and "Injection Cycle" in cycles and not cycle_reconciliation.empty:
        source_order = [
            _norm(value) for value in cycles["Injection Cycle"].astype(str).tolist()
            if _norm(value) != "primary waterflood"
        ]
        expected_order = [
            _norm(value) for value in cycle_reconciliation.loc[
                cycle_reconciliation["Presence"].eq("Present"), "Expected stage"
            ].astype(str).tolist()
        ]
        if source_order != expected_order:
            add(
                "Review", "Injection-cycle rows are not in the expected gas/water order",
                "Workbook stage order: " + " → ".join(source_order) +
                "; expected sequence order: " + " → ".join(expected_order) + ".",
                "Retain workbook row order and confirm the intended sequence before reordering.",
            )

    phase_conflicts = cycle_reconciliation.loc[
        cycle_reconciliation["Phase alignment"].eq("Conflict")
    ]
    if not phase_conflicts.empty:
        examples = "; ".join(
            f"{row['Workbook stage']} starts at {row['PV Start']:g} PV where the curve labels '{row['Recovery-curve phase at PV start']}'"
            for _, row in phase_conflicts.iterrows()
        )
        add(
            "Review", "Injection-cycle labels conflict with recovery-curve phase labels",
            examples + ".",
            "Retain both cycle-table labels and curve phase labels; do not infer a corrected stage assignment.",
        )

    if not cycles.empty and {"PV Start", "PV End", "Injection Cycle"}.issubset(cycles.columns):
        ordered = cycles.loc[
            ~cycles["Injection Cycle"].astype(str).str.casefold().eq("primary waterflood")
        ].copy()
        ordered["PV Start"] = pd.to_numeric(ordered["PV Start"], errors="coerce")
        ordered["PV End"] = pd.to_numeric(ordered["PV End"], errors="coerce")
        ordered = ordered.dropna(subset=["PV Start", "PV End"]).sort_values("PV Start")
        breaks = []
        previous_end = None
        for _, row in ordered.iterrows():
            start_pv, end_pv = float(row["PV Start"]), float(row["PV End"])
            if end_pv <= start_pv:
                breaks.append(f"{row['Injection Cycle']} has non-positive interval {start_pv:g}–{end_pv:g} PV")
            elif previous_end is not None and abs(start_pv - previous_end) > 0.01:
                breaks.append(f"interval begins at {start_pv:g} PV after previous interval ended at {previous_end:g} PV")
            previous_end = end_pv
        if breaks:
            add(
                "Review", "Injection-cycle PV intervals are not contiguous",
                "; ".join(breaks),
                "Keep source boundaries and investigate gaps, overlaps or reversed intervals.",
            )

    ratio = _float(_lookup(design, "WAG Ratio", label_col="Parameter", value_col="Value"))
    gas_slug = _float(_lookup(design, "Gas Slug Size", label_col="Parameter", value_col="Value"))
    water_slug = _float(_lookup(design, "Water Slug Size", label_col="Parameter", value_col="Value"))
    if ratio is not None and gas_slug is not None and water_slug not in (None, 0):
        add(
            "Review", "WAG ratio value needs source confirmation",
            f"Ratio cell is stored as {ratio:.8f} of an Excel day (time-formatted); equal slug sizes ({gas_slug:g} and {water_slug:g} PV) imply 1:1.",
            "Do not display malformed ratio as valid; show gas and water slug sizes separately.",
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
        source_bytes = bytes(workbook_bytes)
        source: Any = BytesIO(source_bytes)
        source_name = workbook_name or BARONIA_WORKBOOK
        source_path = source_name
        source_kind = "provided-bytes"
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
        source_bytes = path.read_bytes()
        source_kind = "local-file"

    workbook_sha256 = sha256(source_bytes).hexdigest()
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

    issues = _quality_issues(
        recovery_summary, iwag_results, recovery_curve, cycles,
        design_parameters, fluid_properties, material_balance, production_curve,
    )
    recovery_reconciliation = _build_recovery_reconciliation(
        recovery_summary, iwag_results, recovery_curve, cycles
    )
    pv_reconciliation, pv_metrics = _build_pv_reconciliation(
        recovery_summary, recovery_curve, production_curve,
        design_parameters, material_balance,
    )
    cycle_reconciliation = _build_cycle_reconciliation(
        cycles, design_parameters, recovery_curve
    )
    gas_total = float(gas_composition["Mol%"].sum()) if not gas_composition.empty else None
    metadata = {
        "workbook_name": source_name,
        "workbook_path": source_path,
        "workbook_source_kind": source_kind,
        "workbook_sha256": workbook_sha256,
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
        "recovery_reconciliation_rows": len(recovery_reconciliation),
        "pv_reconciliation_rows": len(pv_reconciliation),
        "cycle_reconciliation_rows": len(cycle_reconciliation),
        "design_expected_total_pv": pv_metrics["expected_total"],
        "material_balance_total_pv": pv_metrics["balance_total"],
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
        "recovery_reconciliation": recovery_reconciliation,
        "pv_reconciliation": pv_reconciliation,
        "cycle_reconciliation": cycle_reconciliation,
        "metadata": metadata,
    }
