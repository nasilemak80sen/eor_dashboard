"""EOR Atlas production execution layer.

This module contains the stable engineering / ML execution functions used by
both the redesigned UI shell (eor_atlas.py) and compatibility callers.

Target decision path:
    Excel Gate -> CatBoost Intelligence -> Decision Fusion

The redesigned UI is implemented in ``src/eor_atlas.py``.  This module remains
safe to execute directly by delegating to that application shell instead of
running the retired legacy top-tab renderer.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

import pandas as pd
import streamlit as st

import app_2 as _app
from ml.hybrid_intelligence import HybridDecisionService, build_opportunity_context


# -----------------------------------------------------------------------------
# Production service initialization
# -----------------------------------------------------------------------------

def initialize_services() -> Dict[str, Any]:
    """Initialize only services required by the production decision path."""
    model_service = _app.ModelService()
    workbook_sheets = _app.WorkbookRepository.load_workbook()
    return {
        "model_service": model_service,
        "model_loaded": model_service.is_loaded(),
        "workbook_sheets": workbook_sheets,
    }


def render_sidebar_status(services: Dict[str, Any]) -> None:
    """Render the compatibility status panel used by the new UI shell."""
    try:
        path_status = _app.settings.validate_paths()
    except Exception:
        path_status = {}

    model_ready = bool(services.get("model_loaded"))
    workbook_ready = bool(services.get("workbook_sheets")) or bool(path_status.get("workbook"))
    config_ready = bool(path_status.get("config"))

    st.sidebar.markdown(
        "<div class='atlas-brand'>"
        "<div class='atlas-brand-mark'>EA</div>"
        "<div><div class='atlas-brand-title'>EOR ATLAS</div>"
        "<div class='atlas-brand-subtitle'>Reservoir Engineering Decision Support</div></div>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.sidebar.markdown("<div class='nav-section-label'>SYSTEM STATUS</div>", unsafe_allow_html=True)

    rows = [
        ("Excel Gate", workbook_ready),
        ("CatBoost", model_ready),
        ("Decision Fusion", True),
        ("ML Config", config_ready),
    ]
    for label, ready in rows:
        status_class = "ready" if ready else "warn"
        status_text = "READY" if ready else "CHECK"
        st.sidebar.markdown(
            f"<div class='status-strip'><span>{label}</span><span class='status-pill {status_class}'>{status_text}</span></div>",
            unsafe_allow_html=True,
        )


# -----------------------------------------------------------------------------
# Workbook-aligned v3 input form
# -----------------------------------------------------------------------------

V3_DEFAULTS: Dict[str, Any] = {
    "depth_ft": 5000.0,
    "reservoir_pressure": 2500.0,
    "temperature_c": 95.0,
    "visc_cp": 2.0,
    "api": 35.0,
    "perm_md": 100.0,
    "porosity_frac": 0.20,
    "so_pct": 55.0,
    "salinity_ppm": 50000.0,
    "hardness_ppm": 300.0,
    "rock_type": "Sandstone",
    "net_pay_m": 30.0,
    "heterogeneity": "Moderate",
    "gas_availability": "Yes",
    "oxygen_present": "No",
    "ooip_mmstb": 100.0,
    "base_rf_pct": 35.0,
    "drive_mechanism": "Solution Gas Drive",
    "co2_availability": "Yes",
    "mmp_satisfied": "Yes",
    "waterflood_history": "Yes",
    "water_cut_pct": 60.0,
    "field_maturity": "Mid",
    "mobility_ratio": "Favorable",
    "adsorption_risk": "Low",
    "water_handling": "Low",
    "offshore": "No",
    "water_injection_facilities": "Yes",
    "gas_injection_facilities": "Yes",
    "wag_ratio": "1:1",
    "gas_injectivity": "Good",
    "water_injectivity": "Good",
    "gravity_override_risk": "Low",
    "hc_gas_availability": "No",
    "produced_gor_category": "Unknown",
    "gas_reinjectable": "Unknown",
}

DRIVE_MULTIPLIERS = {
    "Solution Gas Drive": 1.3,
    "Weak Water Drive": 1.2,
    "Moderate Water Drive": 1.0,
    "Strong Water Drive": 0.8,
    "Gas Cap Expansion": 1.4,
    "Combination Drive": 1.1,
    "Natural Fracture": 0.9,
    "Others": 1.0,
}

MATURITY_FACTORS = {
    "Early": 0.8,
    "Mid": 1.0,
    "Late": 1.15,
}


def _safe_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if pd.notna(result) else default


def _number_input(
    label: str,
    *,
    prefix: str,
    key_suffix: str,
    value: float,
    min_value: float = 0.0,
    max_value: Optional[float] = None,
    step: float = 1.0,
    help_text: Optional[str] = None,
) -> float:
    kwargs: Dict[str, Any] = {
        "min_value": min_value,
        "value": float(value),
        "step": step,
        "key": f"{prefix}_{key_suffix}",
    }
    if max_value is not None:
        kwargs["max_value"] = max_value
    if help_text:
        kwargs["help"] = help_text
    return float(st.number_input(label, **kwargs))


def render_eor_input_form(prefix: str) -> Tuple[Dict[str, Any], str]:
    """Render the complete EOR Screening Tool 2026 v3 input schema."""
    d = V3_DEFAULTS

    with st.expander("📝 Reservoir Characteristics", expanded=True):
        a, b, c = st.columns(3)
        with a:
            formation = st.selectbox(
                "Formation Category",
                ["Sandstone", "Carbonate", "Unconsolidated sands"],
                index=0,
                key=f"{prefix}_formation",
            )
            depth_ft = _number_input("Depth (ft)", prefix=prefix, key_suffix="depth", value=d["depth_ft"], step=50.0)
            reservoir_pressure = _number_input("Reservoir Pressure (psia)", prefix=prefix, key_suffix="pressure", value=d["reservoir_pressure"], step=50.0)
            temperature_c = _number_input("Temperature (°C)", prefix=prefix, key_suffix="temperature", value=d["temperature_c"], step=1.0)
            visc_cp = _number_input("Oil Viscosity (cP)", prefix=prefix, key_suffix="visc", value=d["visc_cp"], step=0.1)
        with b:
            api = _number_input("API Gravity (°API)", prefix=prefix, key_suffix="api", value=d["api"], max_value=80.0, step=0.5)
            perm_md = _number_input("Permeability (mD)", prefix=prefix, key_suffix="perm", value=d["perm_md"], step=10.0)
            porosity_frac = _number_input("Porosity (fraction)", prefix=prefix, key_suffix="por", value=d["porosity_frac"], max_value=1.0, step=0.01)
            salinity_ppm = _number_input("Salinity (TDS) (ppm)", prefix=prefix, key_suffix="tds", value=d["salinity_ppm"], step=1000.0)
            hardness_ppm = _number_input("Hardness (Ca²⁺+Mg²⁺) (ppm)", prefix=prefix, key_suffix="hardness", value=d["hardness_ppm"], step=50.0)
        with c:
            rock_type = st.selectbox("Rock Type", ["Sandstone", "Carbonate"], index=0, key=f"{prefix}_rock")
            net_pay_m = _number_input("Net Pay (m)", prefix=prefix, key_suffix="netpay", value=d["net_pay_m"], step=1.0)
            heterogeneity = st.selectbox("Heterogeneity", ["Low", "Moderate", "High"], index=1, key=f"{prefix}_heterogeneity")
            gas_availability = st.selectbox("Injection Gas Available", ["Yes", "No"], index=0, key=f"{prefix}_gas_availability")
            oxygen_present = st.selectbox("Oxygen Present in Polymer System", ["Yes", "No"], index=1, key=f"{prefix}_oxygen")

    with st.expander("🛢️ Recovery / EOR Context", expanded=True):
        a, b, c = st.columns(3)
        with a:
            so_pct = _number_input("Current Oil Saturation, So (%)", prefix=prefix, key_suffix="so", value=d["so_pct"], max_value=100.0, step=1.0, help_text="Current average remaining oil saturation; % pore volume.")
            ooip_mmstb = _number_input("STOIIP (MMstb)", prefix=prefix, key_suffix="ooip", value=d["ooip_mmstb"], step=10.0)
            base_rf_pct = _number_input("Base RF (without EOR) (%)", prefix=prefix, key_suffix="base_rf", value=d["base_rf_pct"], max_value=100.0, step=1.0)
            drive_mechanism = st.selectbox("Drive Mechanism", list(DRIVE_MULTIPLIERS.keys()), index=list(DRIVE_MULTIPLIERS.keys()).index(d["drive_mechanism"]), key=f"{prefix}_drive")
            drive_multiplier = DRIVE_MULTIPLIERS.get(drive_mechanism, 1.0)
        with b:
            co2_availability = st.selectbox("CO2 Availability", ["Yes", "No"], index=0, key=f"{prefix}_co2")
            mmp_satisfied = st.selectbox("MMP Satisfied?", ["Yes", "No"], index=0, key=f"{prefix}_mmp")
            waterflood_history = st.selectbox("Waterflood History", ["Yes", "No"], index=0, key=f"{prefix}_waterflood")
            water_cut_pct = _number_input("Water Cut (%)", prefix=prefix, key_suffix="watercut", value=d["water_cut_pct"], max_value=100.0, step=1.0)
            field_maturity = st.selectbox("Field Maturity", ["Early", "Mid", "Late"], index=1, key=f"{prefix}_maturity")
            maturity_factor = MATURITY_FACTORS.get(field_maturity, 1.0)
        with c:
            mobility_ratio = st.selectbox("Mobility Ratio", ["Favorable", "Neutral", "Unfavorable"], index=0, key=f"{prefix}_mobility")
            adsorption_risk = st.selectbox("Surfactant Adsorption Risk", ["Low", "Medium", "High"], index=0, key=f"{prefix}_adsorption")
            water_handling = st.selectbox("Produced Water Handling Complexity", ["Low", "Medium", "High"], index=0, key=f"{prefix}_water_handling")
            offshore = st.selectbox("Offshore Field?", ["Yes", "No"], index=1, key=f"{prefix}_offshore")

    with st.expander("🔁 Injection / WAG / Gas Context", expanded=False):
        a, b, c = st.columns(3)
        with a:
            water_injection_facilities = st.selectbox("Water Injection Facilities", ["Yes", "No"], index=0, key=f"{prefix}_water_fac")
            gas_injection_facilities = st.selectbox("Gas Injection Facilities", ["Yes", "No"], index=0, key=f"{prefix}_gas_fac")
            wag_ratio = st.selectbox("WAG Ratio", ["1:1", "2:1", "1:2", "Custom"], index=0, key=f"{prefix}_wag_ratio")
        with b:
            gas_injectivity = st.selectbox("Gas Injectivity", ["Good", "Fair", "Poor"], index=0, key=f"{prefix}_gas_inj")
            water_injectivity = st.selectbox("Water Injectivity", ["Good", "Fair", "Poor"], index=0, key=f"{prefix}_water_inj")
            gravity_override_risk = st.selectbox("Gravity Override Risk", ["Low", "Medium", "High"], index=0, key=f"{prefix}_gravity")
        with c:
            hc_gas_availability = st.selectbox("HC Gas Availability", ["Yes", "No"], index=1, key=f"{prefix}_hc_availability")
            produced_gor_category = st.selectbox("Produced GOR Category", ["Low", "Moderate", "High", "Unknown"], index=3, key=f"{prefix}_gor_category")
            gas_reinjectable = st.selectbox("Produced Gas Reinjectable?", ["Yes", "No", "Unknown"], index=2, key=f"{prefix}_reinjectable")

    with st.expander("🧩 Optional ScreenTool v3 Parameters", expanded=False):
        st.caption("Current So is a core screening input. Sorw and numeric Produced GOR are optional context inputs and are not fabricated when unavailable.")
        optional_a, optional_b = st.columns(2)
        with optional_a:
            sorw_available = st.checkbox("Residual Oil Saturation to Waterflood, Sorw available", value=False, key=f"{prefix}_sorw_available_v3")
            sorw_pct = _number_input("Sorw (%)", prefix=prefix, key_suffix="sorw_v3", value=30.0, max_value=100.0, step=1.0) if sorw_available else None
        with optional_b:
            gor_available = st.checkbox("Numeric Produced GOR available", value=False, key=f"{prefix}_gor_available_v3")
            produced_gor_scf_stb = _number_input("Produced GOR (scf/STB)", prefix=prefix, key_suffix="gor_numeric_v3", value=500.0, min_value=0.0, step=50.0) if gor_available else None

    phi_so = (porosity_frac * so_pct / 100.0) if so_pct is not None else None
    movable_so = max(so_pct - sorw_pct, 0.0) if sorw_pct is not None else None

    preview = {"so_pct": so_pct, "sorw_pct": sorw_pct, "produced_gor_scf_stb": produced_gor_scf_stb}
    opportunity_preview = build_opportunity_context(preview)

    p1, p2, p3 = st.columns(3)
    p1.metric("Current Oil Saturation, So", f"{so_pct:.1f}% PV")
    p2.metric("φSo Product", "—" if phi_so is None else f"{phi_so:.3f}")
    p3.metric("So − Sorw", "—" if movable_so is None else f"{movable_so:.1f}% PV")
    if opportunity_preview.get("gor_category"):
        st.caption(f"Numeric GOR-derived category: **{opportunity_preview['gor_category']}**")

    values: Dict[str, Any] = {
        "depth_ft": depth_ft,
        "reservoir_pressure": reservoir_pressure,
        "temperature_c": temperature_c,
        "visc_cp": visc_cp,
        "api": api,
        "perm_md": perm_md,
        "porosity_frac": porosity_frac,
        "porosity_pct": porosity_frac * 100.0,
        "so_pct": so_pct,
        "salinity_ppm": salinity_ppm,
        "hardness_ppm": hardness_ppm,
        "rock_type": rock_type,
        "net_pay_m": net_pay_m,
        "heterogeneity": heterogeneity,
        "gas_availability": gas_availability,
        "oxygen_present": oxygen_present,
        "ooip_mmstb": ooip_mmstb,
        "base_rf_pct": base_rf_pct,
        "drive_mechanism": drive_mechanism,
        "drive_multiplier": drive_multiplier,
        "co2_availability": co2_availability,
        "mmp_satisfied": mmp_satisfied,
        "waterflood_history": waterflood_history,
        "water_cut_pct": water_cut_pct,
        "field_maturity": field_maturity,
        "maturity_factor": maturity_factor,
        "mobility_ratio": mobility_ratio,
        "adsorption_risk": adsorption_risk,
        "water_handling": water_handling,
        "offshore": offshore,
        "water_injection_facilities": water_injection_facilities,
        "gas_injection_facilities": gas_injection_facilities,
        "wag_ratio": wag_ratio,
        "gas_injectivity": gas_injectivity,
        "water_injectivity": water_injectivity,
        "gravity_override_risk": gravity_override_risk,
        "hc_gas_availability": hc_gas_availability,
        "produced_gor_category": produced_gor_category,
        "gas_reinjectable": gas_reinjectable,
        "produced_gor_scf_stb": produced_gor_scf_stb,
        "sorw_pct": sorw_pct,
    }

    try:
        derived = _app.ExcelScreeningService().prepare_inputs(values)
    except Exception:
        derived = values.copy()

    st.caption(
        f"HC Gas Source Status = **{derived.get('hc_source_status', 'Unavailable')}** · "
        f"Numeric GOR Category = **{derived.get('gor_category_numeric', '—')}**"
    )
    return values, formation


# -----------------------------------------------------------------------------
# Hybrid decision execution and result rendering
# -----------------------------------------------------------------------------

def _build_legacy_catboost_input(values: Dict[str, Any], formation: str) -> Dict[str, Any]:
    """Build the exact range-based input expected by the current v1 CatBoost artifact."""
    formation_map = {
        "Sandstone": "Sandstone",
        "Carbonate": "Carbonates",
        "Carbonates": "Carbonates",
        "Unconsolidated sands": "Unconsolidated sands",
    }
    mapped = formation_map.get(formation)
    if mapped is None:
        raise ValueError(f"Unsupported formation: {formation}")

    required = ["depth_ft", "porosity_pct", "perm_md", "api", "visc_cp", "so_pct"]
    missing = [key for key in required if values.get(key) is None]
    if missing:
        raise KeyError(f"Missing CatBoost inputs: {missing}")

    def positive(key: str) -> float:
        value = float(values[key])
        if value <= 0:
            raise ValueError(f"{key} must be greater than zero.")
        return value

    depth = positive("depth_ft")
    porosity = float(values["porosity_pct"])
    permeability = positive("perm_md")
    api = float(values["api"])
    viscosity = positive("visc_cp")
    oil_saturation = float(values["so_pct"])

    if not 0 <= porosity <= 100:
        raise ValueError("Porosity must be between 0 and 100%.")
    if not 0 <= api <= 100:
        raise ValueError("API gravity must be between 0 and 100°.")
    if not 0 <= oil_saturation <= 100:
        raise ValueError("Oil saturation must be between 0 and 100%.")

    return {
        "depth_min_ft": depth,
        "depth_max_ft": depth,
        "porosity_min_pct": porosity,
        "porosity_max_pct": porosity,
        "perm_min_md": permeability,
        "perm_max_md": permeability,
        "api_min": api,
        "api_max": api,
        "visc_min_cp": viscosity,
        "visc_max_cp": viscosity,
        "so_min_pct": oil_saturation,
        "so_max_pct": oil_saturation,
        "formation_category": mapped,
    }


def run_eor_intelligence(services: Dict[str, Any], values: Dict[str, Any], formation: str) -> Dict[str, Any]:
    """Run Excel Gate -> CatBoost -> Decision Fusion."""
    screening_result = _app.ExcelScreeningService().screen(values, formation)
    model_service = services.get("model_service")
    if model_service is None:
        raise RuntimeError("CatBoost model service is unavailable.")

    ml_available = False
    ml_probabilities: Dict[str, float] = {}
    ml_top3 = []
    model_info: Dict[str, Any] = {}
    ml_error: Optional[str] = None

    try:
        ml_available = bool(model_service.is_loaded())
        if ml_available:
            prediction = model_service.predict(_build_legacy_catboost_input(values, formation))
            if not prediction.success:
                raise RuntimeError(prediction.warning or "CatBoost prediction failed.")
            ml_top3 = list(prediction.top_n(3))
            ml_probabilities = {
                str(candidate.technique): float(candidate.probability)
                for candidate in prediction.candidates
            }
            model_info = model_service.get_model_info()
    except Exception as exc:
        ml_available = False
        ml_error = str(exc)

    hybrid = HybridDecisionService().fuse(
        screening_result,
        ml_probabilities,
        top_n=3,
        opportunity_context=build_opportunity_context(values),
    )

    return {
        "formation": formation,
        "inputs": values,
        "screening": screening_result,
        "ml_available": ml_available,
        "ml_probabilities": ml_probabilities,
        "ml_top3": ml_top3,
        "ml_error": ml_error,
        "model_info": model_info,
        "hybrid": hybrid,
    }


def _run_intelligence_from_current_inputs(services: Dict[str, Any], inputs: Dict[str, Any], formation: str) -> None:
    try:
        st.session_state["eor_intelligence_result"] = run_eor_intelligence(services, inputs, formation)
    except Exception:
        _app.logger.exception("EOR Intelligence execution failed.")
        st.error("EOR Intelligence could not complete. Check the input values and service status.")


def _format_probability(value: Any) -> str:
    try:
        return f"{float(value):.1%}"
    except (TypeError, ValueError):
        return "0.0%"


def render_eor_intelligence_result(result: Dict[str, Any]) -> None:
    """Render the production Excel-gated hybrid intelligence result."""
    st.subheader("Hybrid Decision Result")
    hybrid = result.get("hybrid", {}) or {}
    recommendation = hybrid.get("recommendation")
    ranking = hybrid.get("ranking", []) or []

    if recommendation:
        st.markdown(
            f"<div class='decision-card'><div class='label'>Recommended EOR Technique</div>"
            f"<div class='value'>{recommendation.get('EOR Technique', 'N/A')}</div>"
            f"<div class='meta'>Hybrid {_format_probability(recommendation.get('Hybrid Score', 0))} · "
            f"CatBoost {_format_probability(recommendation.get('CatBoost Probability', 0))} · "
            f"Engineering {float(recommendation.get('Engineering Score', 0)):.0%}</div></div>",
            unsafe_allow_html=True,
        )
    else:
        st.warning("No eligible technique was produced by the hybrid decision layer.")

    if ranking:
        st.markdown("### Top 3 Hybrid Ranking")
        rows = []
        for rank, row in enumerate(ranking, start=1):
            rows.append({
                "Rank": rank,
                "EOR Technique": row.get("EOR Technique", ""),
                "Hybrid Score": f"{float(row.get('Hybrid Score', 0)):.1%}",
                "CatBoost": f"{float(row.get('CatBoost Probability', 0)):.1%}",
                "Engineering": f"{float(row.get('Engineering Score', 0)):.1%}",
                "Status": row.get("Engineering Status", ""),
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    opportunity = hybrid.get("opportunity_context", {}) or {}
    st.markdown("### ScreenTool v3 Context")
    context = st.columns(6)
    context_values = [
        ("Current So", opportunity.get("current_oil_saturation_pct"), "% PV"),
        ("Sorw", opportunity.get("sorw_pct"), "% PV"),
        ("So − Sorw", opportunity.get("movable_oil_saturation_pct"), "% PV"),
        ("Produced GOR", opportunity.get("produced_gor_scf_stb"), " scf/STB"),
        ("GOR Category", opportunity.get("gor_category"), ""),
        ("Sorw Available", "Yes" if opportunity.get("sorw_available") else "No", ""),
    ]
    for col, (label, value, suffix) in zip(context, context_values):
        with col:
            if value is None:
                st.metric(label, "—")
            elif isinstance(value, str):
                st.metric(label, value)
            else:
                st.metric(label, f"{float(value):,.1f}{suffix}")

    if result.get("ml_error"):
        st.warning(f"CatBoost inference unavailable: {result['ml_error']}")

    with st.expander("🐱 CatBoost Model Information", expanded=False):
        if result.get("model_info"):
            st.json(result["model_info"])
        else:
            st.info("No CatBoost model information is available for this run.")

    with st.expander("⚖️ Decision Fusion Configuration", expanded=False):
        st.json(hybrid.get("weights", {}))


# -----------------------------------------------------------------------------
# Compatibility entrypoint
# -----------------------------------------------------------------------------

def main() -> None:
    """Delegate direct execution to the redesigned EOR Atlas UI shell."""
    try:
        from eor_atlas import main as atlas_main
    except Exception as exc:
        _app.logger.exception("Unable to load the redesigned EOR Atlas UI shell.")
        st.error(f"EOR Atlas UI shell could not be loaded: {exc}")
        return

    atlas_main()


if __name__ == "__main__":
    main()
