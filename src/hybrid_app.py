"""EOR Atlas production entrypoint for the target architecture.

Target architecture:
    Excel Gate -> CatBoost Intelligence -> Decision Fusion

This entrypoint deliberately does not load, calculate, or render fuzzy suitability.
The reservoir input form is aligned with EOR_Screening_Tool_2026_v3.0.xlsx.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

import pandas as pd
import streamlit as st

import app_2 as _app
from ml.hybrid_intelligence import HybridDecisionService, build_opportunity_context


# Reuse stable downstream services/helpers from app_2, but do not reuse its
# legacy input form because that form does not fully match the v3 workbook.


def initialize_services() -> Dict[str, Any]:
    """Initialize only services required by the production dashboard path."""
    model_service = _app.ModelService()
    workbook_sheets = _app.WorkbookRepository.load_workbook()
    return {
        "model_service": model_service,
        "model_loaded": model_service.is_loaded(),
        "workbook_sheets": workbook_sheets,
    }


def render_sidebar_status(services: Dict[str, Any]) -> None:
    """Render production status without the retired fuzzy layer."""
    try:
        path_status = _app.settings.validate_paths()
    except Exception:
        path_status = {}

    model_ready = bool(services.get("model_loaded"))
    workbook_ready = bool(path_status.get("workbook"))
    config_ready = bool(path_status.get("config"))

    st.sidebar.header("Operational Status")
    st.sidebar.markdown(
        f"""
        <div class="status-box">
            <div class="status-row"><span>CatBoost Model</span><span class="status-pill {'ready' if model_ready else 'warn'}">{'Ready' if model_ready else 'Unavailable'}</span></div>
            <div class="status-row"><span>Workbook</span><span class="status-pill {'ready' if workbook_ready else 'warn'}">{'Loaded' if workbook_ready else 'Missing'}</span></div>
            <div class="status-row"><span>ML Config</span><span class="status-pill {'ready' if config_ready else 'warn'}">{'Valid' if config_ready else 'Check'}</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.sidebar.caption("Production decision stack")
    st.sidebar.write("• Excel Gate")
    st.sidebar.write("• CatBoost Intelligence")
    st.sidebar.write("• Decision Fusion")


# Workbook-aligned defaults. Blank optional values are represented as None
# in the final payload rather than invented numeric defaults.
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
    """Safe wrapper around number_input with a unique prefix-scoped key."""
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
            depth_ft = _number_input(
                "Depth (ft)", prefix=prefix, key_suffix="depth", value=d["depth_ft"], step=50.0
            )
            reservoir_pressure = _number_input(
                "Reservoir Pressure (psia)", prefix=prefix, key_suffix="pressure", value=d["reservoir_pressure"], step=50.0
            )
            temperature_c = _number_input(
                "Temperature (°C)", prefix=prefix, key_suffix="temperature", value=d["temperature_c"], step=1.0
            )
            visc_cp = _number_input(
                "Oil Viscosity (cP)", prefix=prefix, key_suffix="visc", value=d["visc_cp"], step=0.1
            )

        with b:
            api = _number_input(
                "API Gravity (°API)", prefix=prefix, key_suffix="api", value=d["api"], max_value=80.0, step=0.5
            )
            perm_md = _number_input(
                "Permeability (mD)", prefix=prefix, key_suffix="perm", value=d["perm_md"], step=10.0
            )
            porosity_frac = _number_input(
                "Porosity (fraction)", prefix=prefix, key_suffix="por", value=d["porosity_frac"], max_value=1.0, step=0.01
            )
            salinity_ppm = _number_input(
                "Salinity (TDS) (ppm)", prefix=prefix, key_suffix="tds", value=d["salinity_ppm"], step=1000.0
            )
            hardness_ppm = _number_input(
                "Hardness (Ca²⁺+Mg²⁺) (ppm)", prefix=prefix, key_suffix="hardness", value=d["hardness_ppm"], step=50.0
            )

        with c:
            rock_type = st.selectbox(
                "Rock Type",
                ["Sandstone", "Carbonate"],
                index=0,
                key=f"{prefix}_rock",
            )
            net_pay_m = _number_input(
                "Net Pay (m)", prefix=prefix, key_suffix="netpay", value=d["net_pay_m"], step=1.0
            )
            heterogeneity = st.selectbox(
                "Heterogeneity",
                ["Low", "Moderate", "High"],
                index=1,
                key=f"{prefix}_heterogeneity",
            )
            gas_availability = st.selectbox(
                "Injection Gas Available",
                ["Yes", "No"],
                index=0,
                key=f"{prefix}_gas_availability",
                help="Generic injection-gas source for HC / immiscible gas screening.",
            )
            oxygen_present = st.selectbox(
                "Oxygen Present in Polymer System",
                ["Yes", "No"],
                index=1,
                key=f"{prefix}_oxygen",
            )

    with st.expander("🛢️ Recovery / EOR Context", expanded=True):
        a, b, c = st.columns(3)
        with a:
            so_pct = _number_input(
                "Current Oil Saturation, So (%)",
                prefix=prefix,
                key_suffix="so",
                value=d["so_pct"],
                max_value=100.0,
                step=1.0,
                help="Current average remaining oil saturation; % pore volume.",
            )
            ooip_mmstb = _number_input(
                "STOIIP (MMstb)", prefix=prefix, key_suffix="ooip", value=d["ooip_mmstb"], step=10.0
            )
            base_rf_pct = _number_input(
                "Base RF (without EOR) (%)",
                prefix=prefix,
                key_suffix="base_rf",
                value=d["base_rf_pct"],
                max_value=100.0,
                step=1.0,
            )
            drive_mechanism = st.selectbox(
                "Drive Mechanism",
                list(DRIVE_MULTIPLIERS.keys()),
                index=list(DRIVE_MULTIPLIERS.keys()).index(d["drive_mechanism"]),
                key=f"{prefix}_drive",
            )
            drive_multiplier = DRIVE_MULTIPLIERS.get(drive_mechanism, 1.0)

        with b:
            co2_availability = st.selectbox(
                "CO2 Availability", ["Yes", "No"], index=0, key=f"{prefix}_co2"
            )
            mmp_satisfied = st.selectbox(
                "MMP Satisfied?", ["Yes", "No"], index=0, key=f"{prefix}_mmp"
            )
            waterflood_history = st.selectbox(
                "Waterflood History", ["Yes", "No"], index=0, key=f"{prefix}_waterflood"
            )
            water_cut_pct = _number_input(
                "Water Cut (%)", prefix=prefix, key_suffix="watercut", value=d["water_cut_pct"], max_value=100.0, step=1.0
            )
            field_maturity = st.selectbox(
                "Field Maturity",
                ["Early", "Mid", "Late"],
                index=1,
                key=f"{prefix}_maturity",
            )
            maturity_factor = MATURITY_FACTORS.get(field_maturity, 1.0)

        with c:
            mobility_ratio = st.selectbox(
                "Mobility Ratio", ["Favorable", "Neutral", "Unfavorable"], index=0, key=f"{prefix}_mobility"
            )
            adsorption_risk = st.selectbox(
                "Surfactant Adsorption Risk", ["Low", "Medium", "High"], index=0, key=f"{prefix}_adsorption"
            )
            water_handling = st.selectbox(
                "Produced Water Handling Complexity", ["Low", "Medium", "High"], index=0, key=f"{prefix}_water_handling"
            )
            offshore = st.selectbox(
                "Offshore Field?", ["Yes", "No"], index=1, key=f"{prefix}_offshore"
            )

    with st.expander("🔁 Injection / WAG / Gas Context", expanded=False):
        a, b, c = st.columns(3)
        with a:
            water_injection_facilities = st.selectbox(
                "Water Injection Facilities", ["Yes", "No"], index=0, key=f"{prefix}_water_fac"
            )
            gas_injection_facilities = st.selectbox(
                "Gas Injection Facilities", ["Yes", "No"], index=0, key=f"{prefix}_gas_fac"
            )
            wag_ratio = st.selectbox(
                "WAG Ratio", ["1:1", "2:1", "1:2", "Custom"], index=0, key=f"{prefix}_wag_ratio"
            )

        with b:
            gas_injectivity = st.selectbox(
                "Gas Injectivity", ["Good", "Fair", "Poor"], index=0, key=f"{prefix}_gas_inj"
            )
            water_injectivity = st.selectbox(
                "Water Injectivity", ["Good", "Fair", "Poor"], index=0, key=f"{prefix}_water_inj"
            )
            gravity_override_risk = st.selectbox(
                "Gravity Override Risk", ["Low", "Medium", "High"], index=0, key=f"{prefix}_gravity"
            )

        with c:
            hc_gas_availability = st.selectbox(
                "HC Gas Availability", ["Yes", "No"], index=1, key=f"{prefix}_hc_availability"
            )
            produced_gor_category = st.selectbox(
                "Produced GOR Category",
                ["Low", "Moderate", "High", "Unknown"],
                index=3,
                key=f"{prefix}_gor_category",
                help="Used when numeric Produced GOR is unavailable.",
            )
            gas_reinjectable = st.selectbox(
                "Produced Gas Reinjectable?",
                ["Yes", "No", "Unknown"],
                index=2,
                key=f"{prefix}_reinjectable",
            )

    with st.expander("🧩 Optional ScreenTool v3 Parameters", expanded=False):
        st.caption(
            "Optional v3 parameters are context/opportunity inputs. Current So is already captured above; "
            "Sorw and numeric Produced GOR are optional and never fabricate a value when unavailable."
        )
        optional_a, optional_b = st.columns(2)

        with optional_a:
            sorw_available = st.checkbox(
                "Residual Oil Saturation to Waterflood, Sorw available",
                value=False,
                key=f"{prefix}_sorw_available_v3",
                help="Optional SCAL/simulation input.",
            )
            sorw_pct = _number_input(
                "Sorw (%)",
                prefix=prefix,
                key_suffix="sorw_v3",
                value=30.0,
                max_value=100.0,
                step=1.0,
            ) if sorw_available else None

        with optional_b:
            gor_available = st.checkbox(
                "Numeric Produced GOR available",
                value=False,
                key=f"{prefix}_gor_available_v3",
                help="Optional numeric input; manual GOR Category remains available as fallback.",
            )
            produced_gor_scf_stb = _number_input(
                "Produced GOR (scf/STB)",
                prefix=prefix,
                key_suffix="gor_numeric_v3",
                value=500.0,
                min_value=0.0,
                step=50.0,
            ) if gor_available else None

    # Derived v3 helpers — never used as hard gates by this wrapper.
    phi_so = (porosity_frac * so_pct / 100.0) if so_pct is not None else None
    movable_so = max(so_pct - sorw_pct, 0.0) if sorw_pct is not None else None

    preview = {
        "so_pct": so_pct,
        "sorw_pct": sorw_pct,
        "produced_gor_scf_stb": produced_gor_scf_stb,
    }
    opportunity_preview = build_opportunity_context(preview)

    p1, p2, p3 = st.columns(3)
    with p1:
        st.metric("Current Oil Saturation, So", f"{so_pct:.1f}% PV")
    with p2:
        st.metric("φSo Product", "—" if phi_so is None else f"{phi_so:.3f}")
    with p3:
        st.metric("So − Sorw", "—" if movable_so is None else f"{movable_so:.1f}% PV")

    gor_numeric = opportunity_preview.get("produced_gor_scf_stb")
    gor_category_numeric = opportunity_preview.get("gor_category")
    if gor_numeric is not None:
        st.caption(f"Numeric GOR-derived category: **{gor_category_numeric or 'Unknown'}**")

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

    hc_source_status = derived.get("hc_source_status", "Unavailable")
    numeric_gor_category = derived.get("gor_category_numeric", "—")
    st.caption(
        f"HC Gas Source Status = **{hc_source_status}** · Numeric GOR Category = **{numeric_gor_category}**"
    )

    return values, formation



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



def run_eor_intelligence(
    services: Dict[str, Any],
    values: Dict[str, Any],
    formation: str,
) -> Dict[str, Any]:
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
            ml_input = _build_legacy_catboost_input(values, formation)
            prediction = model_service.predict(ml_input)
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

    opportunity_context = build_opportunity_context(values)
    hybrid = HybridDecisionService().fuse(
        screening_result,
        ml_probabilities,
        top_n=3,
        opportunity_context=opportunity_context,
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



def _format_probability(value: float) -> str:
    return f"{value:.1%}"



def render_eor_intelligence_result(result: Dict[str, Any]) -> None:
    """Render the production Excel-gated hybrid intelligence result."""
    st.subheader("🧠 Hybrid EOR Intelligence")
    st.markdown(
        """
        <div class="intelligence-note">
        <strong>Decision architecture:</strong>
        the ScreenTool provides the engineering gate, CatBoost provides the
        data-driven EOR technique probabilities, and Decision Fusion combines
        the two. Fuzzy suitability is not used in this production path.
        </div>
        """,
        unsafe_allow_html=True,
    )

    hybrid = result.get("hybrid", {})
    recommendation = hybrid.get("recommendation")
    ranking = hybrid.get("ranking", [])

    if recommendation:
        st.markdown(
            f"""
            <div class="exec-kpi-card" style="margin-bottom:1rem;">
                <div class="exec-kpi-label">🏆 Hybrid Recommendation</div>
                <div class="exec-kpi-value">{recommendation.get('EOR Technique', 'N/A')}</div>
                <div class="exec-kpi-subtext">
                    Hybrid score: {_format_probability(float(recommendation.get('Hybrid Score', 0.0)))}
                    · CatBoost: {_format_probability(float(recommendation.get('CatBoost Probability', 0.0)))}
                    · Engineering: {float(recommendation.get('Engineering Score', 0.0)):.0%}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.warning("No eligible technique was produced by the hybrid decision layer.")

    st.markdown("### 🏆 Hybrid Ranking")
    if ranking:
        rows = []
        for rank, row in enumerate(ranking, start=1):
            rows.append(
                {
                    "Rank": rank,
                    "EOR Technique": row.get("EOR Technique", ""),
                    "Hybrid Score": row.get("Hybrid Score", 0.0),
                    "CatBoost Probability": row.get("CatBoost Probability", 0.0),
                    "Engineering Score": row.get("Engineering Score", 0.0),
                    "Engineering Status": row.get("Engineering Status", ""),
                    "Gate Failed": "Yes" if row.get("Gate Failed", False) else "No",
                }
            )
        ranking_df = pd.DataFrame(rows)
        for column in ["Hybrid Score", "CatBoost Probability", "Engineering Score"]:
            ranking_df[column] = ranking_df[column].map(lambda x: f"{float(x):.1%}")
        st.dataframe(ranking_df, use_container_width=True, hide_index=True)
    else:
        st.info("No mapped CatBoost techniques passed through the engineering gate.")

    st.markdown("### 🧱 Excel Gate")
    screen_rows = result.get("screening", {}).get("results", [])
    if screen_rows:
        gate_df = pd.DataFrame(
            [
                {
                    "EOR Technique": row.get("EOR Technique", ""),
                    "Status": row.get("Status", ""),
                    "Score": row.get("Score (%)", 0.0),
                    "Engineering Reason": row.get("Cause of Fail/Pass", ""),
                }
                for row in screen_rows
            ]
        )
        gate_df["Score"] = gate_df["Score"].map(lambda x: f"{float(x):.1f}%")
        st.dataframe(gate_df, use_container_width=True, hide_index=True)

    opportunity = hybrid.get("opportunity_context", {})
    st.markdown("### 🧩 ScreenTool v3 Opportunity Context")
    context_cols = st.columns(6)
    context_values = [
        ("Current So", opportunity.get("current_oil_saturation_pct"), "% PV"),
        ("Sorw", opportunity.get("sorw_pct"), "% PV"),
        ("So − Sorw", opportunity.get("movable_oil_saturation_pct"), "% PV"),
        ("Produced GOR", opportunity.get("produced_gor_scf_stb"), " scf/STB"),
        ("GOR Category", opportunity.get("gor_category"), ""),
        ("Sorw Available", "Yes" if opportunity.get("sorw_available") else "No", ""),
    ]
    for col, (label, value, suffix) in zip(context_cols, context_values):
        with col:
            if value is None:
                st.metric(label, "—")
            elif isinstance(value, str):
                st.metric(label, value)
            else:
                st.metric(label, f"{float(value):,.1f}{suffix}")

    if result.get("ml_error"):
        st.warning(f"CatBoost inference unavailable: {result['ml_error']}")

    if result.get("ml_probabilities"):
        st.markdown("### 🤖 CatBoost Probability Distribution")
        probability_series = pd.Series(result["ml_probabilities"], dtype=float).sort_values(ascending=False)
        st.bar_chart(probability_series)

    with st.expander("🐱 CatBoost Model Information", expanded=False):
        if result.get("model_info"):
            st.json(result["model_info"])
        else:
            st.info("No CatBoost model information is available for this run.")

    with st.expander("⚖️ Decision Fusion Configuration", expanded=False):
        st.json(hybrid.get("weights", {}))
        st.caption(
            "These are initial fusion defaults. They should be recalibrated against labeled historical validation cases before use as a formal performance claim."
        )



def _run_intelligence_from_current_inputs(
    services: Dict[str, Any],
    inputs: Dict[str, Any],
    formation: str,
) -> None:
    """Execute intelligence while preserving every v3 input field."""
    try:
        result = run_eor_intelligence(services, inputs, formation)
        st.session_state["eor_intelligence_result"] = result
    except Exception:
        _app.logger.exception("EOR Intelligence execution failed.")
        st.error("EOR Intelligence could not complete. Check the input values and service status.")



def main() -> None:
    """Production dashboard entrypoint with a v3-safe input/intelligence flow."""
    st.title("EOR Atlas – Decision Support Platform with Machine Learning Classifications")
    st.caption("Engineering-first EOR dashboard with deterministic screening, CatBoost intelligence, and decision fusion.")

    try:
        services = initialize_services()
    except Exception:
        _app.logger.exception("EOR Atlas services failed to initialize.")
        services = {"model_service": None, "model_loaded": False, "workbook_sheets": {}}

    render_sidebar_status(services)

    tabs = st.tabs([
        "🏠 Executive Overview",
        "🔍 EOR Screening",
        "🎯 EOR Candidate Screening",
        "🧪 CEOR — Fluid / Fluid",
        "🪨 CEOR — Fluid / Rock",
        "📚 Past EOR Results",
        "⚠️ Challenges & Lessons",
        "🤖 EOR Intelligence",
    ])

    with tabs[0]:
        _app.render_executive_overview_section()

    with tabs[1]:
        st.header("🔍 EOR Screening")
        st.write("Deterministic reservoir screening using the EOR Screening Tool 2026 v3 criteria.")
        inputs, formation = render_eor_input_form("screening")
        if st.button("🚀 Run Screening", type="primary", use_container_width=True, key="excel_screening_run"):
            try:
                result = _app.ExcelScreeningService().screen(inputs, formation)
                st.session_state["excel_screening_result"] = result
            except Exception:
                _app.logger.exception("EOR Screening failed.")
                st.error("The deterministic screening could not be completed. Check the entered values.")
        result = st.session_state.get("excel_screening_result")
        if result:
            st.success("✅ EOR Screening completed")
            _app.render_excel_screening_result(result)
        with st.expander("Workbook source / diagnostic", expanded=False):
            st.write(f"Workbook: `{_app.settings.workbook_path}`")
            st.write("Executable worksheet: `Screening`")
            st.write("Input source: `InputData!B4:B48`")
            st.write("Output source: `Screening!A1:I14`")

    with tabs[2]:
        _app.render_field_candidates_section()
    with tabs[3]:
        _app.render_fluid_fluid_section()
    with tabs[4]:
        _app.render_fluid_rock_section()
    with tabs[5]:
        st.header("📚 Past EOR Results")
        _app.render_database_summary_section()
        st.divider()
        _app.render_saved_run_detail_section()
    with tabs[6]:
        _app.render_challenges_section()

    with tabs[7]:
        st.header("🤖 EOR Intelligence with CatBoost Classification")
        st.write("Uses the same full v3 reservoir input set as EOR Screening. CatBoost and the deterministic Excel gate are combined through Decision Fusion.")
        inputs, formation = render_eor_input_form("intel")
        if st.button("🧠 Run EOR Intelligence", type="primary", use_container_width=True, key="run_eor_intelligence_v3"):
            _run_intelligence_from_current_inputs(services, inputs, formation)

        result = st.session_state.get("eor_intelligence_result")
        if result:
            render_eor_intelligence_result(result)
            st.divider()
            model_service = services.get("model_service")
            if model_service is not None and model_service.is_loaded():
                with st.expander("🐱 Active CatBoost Model Information", expanded=False):
                    try:
                        st.json(model_service.get_model_info())
                    except Exception as exc:
                        st.warning(f"Model information could not be displayed: {exc}")
            st.divider()
            try:
                _app.render_model_registry_section()
            except Exception:
                _app.logger.exception("Model registry rendering failed.")
                st.info("Model registry is currently unavailable.")


# Make the module executable with `streamlit run src/hybrid_app.py`.
if __name__ == "__main__":
    main()
