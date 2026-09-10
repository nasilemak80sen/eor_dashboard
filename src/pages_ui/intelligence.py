"""Hybrid Intelligence page."""

from __future__ import annotations

import streamlit as st

from ui.components import insight_cards, reset_button, section_title


def render(services: dict) -> None:
    import hybrid_app as _hybrid

    insight_cards([
        ("01 · GATE", "Excel screening", "Hard engineering failures remain excluded from the hybrid recommendation."),
        ("02 · MODEL", "CatBoost probability", "The active compatibility model contributes a data-driven technique signal."),
        ("03 · FUSION", "Decision recommendation", "Engineering score and model probability are reconciled into a ranked Top 3."),
    ])
    st.markdown("<div class='atlas-divider'></div>", unsafe_allow_html=True)

    input_tab, decision_tab = st.tabs(["Reservoir Inputs", "Hybrid Decision"])

    with input_tab:
        action_col, _ = st.columns([1, 4])
        with action_col:
            reset_button(
                "↺ Reset inputs",
                prefixes="intel_",
                result_keys=("eor_intelligence_result",),
                key="intelligence_reset_inputs",
            )
        section_title("Reservoir Context", "Use the same full v3 input schema as EOR Screening so the two pages remain consistent.")
        inputs, formation = _hybrid.render_eor_input_form("intel")
        if st.button("🧠 Run Hybrid Intelligence", type="primary", use_container_width=True, key="ui_hybrid_intelligence_run"):
            _hybrid._run_intelligence_from_current_inputs(services, inputs, formation)

    with decision_tab:
        result = st.session_state.get("eor_intelligence_result")
        if not result:
            st.info("Run Hybrid Intelligence from the Reservoir Inputs tab to populate the decision result.")
            return
        section_title("Decision Result", "Recommendation, Top 3 ranking, engineering gate and model context.")
        try:
            _hybrid.render_eor_intelligence_result(result)
        except Exception as exc:
            st.error(f"Hybrid intelligence result could not be displayed: {exc}")
