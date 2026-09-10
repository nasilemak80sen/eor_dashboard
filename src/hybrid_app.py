"""EOR Atlas production entrypoint for the target architecture.

This adapter intentionally reuses the existing dashboard implementation while
replacing only the live intelligence path:

    Excel Gate -> CatBoost -> Decision Fusion

Fuzzy suitability is not loaded, calculated, or rendered here.
"""

from __future__ import annotations

from typing import Any, Dict

import pandas as pd
import streamlit as st

import app_2 as _app
from ml.hybrid_intelligence import HybridDecisionService, build_opportunity_context


_ORIGINAL_RENDER_INPUT_FORM = _app.render_eor_input_form


def initialize_services() -> Dict[str, Any]:
    """Initialize only services required by the production dashboard path."""
    model_service = _app.ModelService()
    workbook_sheets = _app.WorkbookRepository.load_workbook()
    return {
        "model_service": model_service,
        "model_loaded": model_service.is_loaded(),
        "workbook_sheets": workbook_sheets,
    }


def render_eor_input_form(prefix: str):
    """Reuse the stable ScreenTool form and append optional ScreenTool v3 data."""
    inputs, formation = _ORIGINAL_RENDER_INPUT_FORM(prefix)

    with st.expander("🧩 ScreenTool v3 Optional Parameters", expanded=False):
        st.caption(
            "These parameters are optional opportunity/context indicators. "
            "They do not create a universal engineering PASS/FAIL gate."
        )
        sorw_raw = st.number_input(
            "Residual Oil Saturation to Waterflood, Sorw (%)",
            min_value=0.0,
            max_value=100.0,
            value=float(inputs.get("sorw_pct", 0.0)),
            step=1.0,
            key=f"{prefix}_sorw_v3",
            help="Optional SCAL/simulation input used to derive movable oil saturation.",
        )
        sorw_provided = st.checkbox(
            "Sorw available from SCAL / simulation",
            value=bool(inputs.get("sorw_pct") is not None),
            key=f"{prefix}_sorw_available_v3",
        )

    inputs["sorw_pct"] = sorw_raw if sorw_provided else None

    opportunity = build_opportunity_context(inputs)
    movable = opportunity.get("movable_oil_saturation_pct")

    if opportunity["sorw_available"]:
        st.caption(
            f"Movable Oil Saturation Indicator (So − Sorw) = **{movable:.1f}%**"
        )
    else:
        st.caption("Movable Oil Saturation Indicator = **Not available**")

    return inputs, formation


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
    model_service = services["model_service"]

    ml_available = model_service.is_loaded()
    ml_probabilities: Dict[str, float] = {}
    ml_top3 = []
    model_info: Dict[str, Any] = {}
    ml_error = None

    if ml_available:
        try:
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
                <div class="exec-kpi-value">{recommendation['EOR Technique']}</div>
                <div class="exec-kpi-subtext">
                    Hybrid score: {_format_probability(recommendation['Hybrid Score'])}
                    · CatBoost: {_format_probability(recommendation['CatBoost Probability'])}
                    · Engineering: {recommendation['Engineering Score']:.0%}
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
                    "EOR Technique": row["EOR Technique"],
                    "Hybrid Score": row["Hybrid Score"],
                    "CatBoost Probability": row["CatBoost Probability"],
                    "Engineering Score": row["Engineering Score"],
                    "Engineering Status": row["Engineering Status"],
                    "Gate Failed": "Yes" if row["Gate Failed"] else "No",
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
                    "EOR Technique": row["EOR Technique"],
                    "Status": row["Status"],
                    "Score": row["Score (%)"],
                    "Engineering Reason": row["Cause of Fail/Pass"],
                }
                for row in screen_rows
            ]
        )
        gate_df["Score"] = gate_df["Score"].map(lambda x: f"{float(x):.1f}%")
        st.dataframe(gate_df, use_container_width=True, hide_index=True)

    opportunity = hybrid.get("opportunity_context", {})
    st.markdown("### 🧩 ScreenTool v3 Opportunity Context")
    context_cols = st.columns(4)
    context_values = [
        ("Current So", opportunity.get("current_oil_saturation_pct"), "%"),
        ("Sorw", opportunity.get("sorw_pct"), "%"),
        ("So − Sorw", opportunity.get("movable_oil_saturation_pct"), "%"),
        ("Produced GOR", opportunity.get("produced_gor_scf_stb"), " scf/STB"),
    ]
    for col, (label, value, suffix) in zip(context_cols, context_values):
        with col:
            if value is None:
                st.metric(label, "—")
            else:
                st.metric(label, f"{float(value):,.1f}{suffix}")

    if opportunity.get("gor_category"):
        st.caption(f"GOR category from numeric value: **{opportunity['gor_category']}**")

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


# Patch only the production entrypoints. The rest of app_2 remains unchanged.
_app.initialize_services = initialize_services
_app.render_eor_input_form = render_eor_input_form
_app.run_eor_intelligence = run_eor_intelligence
_app.render_eor_intelligence_result = render_eor_intelligence_result
_app.main()
