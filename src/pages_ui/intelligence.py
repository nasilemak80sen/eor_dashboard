"""Hybrid Intelligence page."""

from __future__ import annotations

import streamlit as st

from ui.components import insight_cards, section_title


def render(services: dict) -> None:
    import hybrid_app as _hybrid

    insight_cards([
        ("01 · GATE", "Excel screening", "Hard engineering failures remain excluded from the hybrid recommendation."),
        ("02 · MODEL", "CatBoost probability", "The active compatibility model contributes a data-driven technique signal."),
        ("03 · FUSION", "Decision recommendation", "Engineering score and model probability are reconciled into a ranked Top 3."),
    ])
    st.markdown("<div class='atlas-divider'></div>", unsafe_allow_html=True)

    section_title("Reservoir Context", "Use the same full v3 input schema as EOR Screening so the two pages remain consistent.")
    inputs, formation = _hybrid.render_eor_input_form("intel")

    if st.button("🧠 Run Hybrid Intelligence", type="primary", use_container_width=True, key="ui_hybrid_intelligence_run"):
        _hybrid._run_intelligence_from_current_inputs(services, inputs, formation)

    result = st.session_state.get("eor_intelligence_result")
    if result:
        st.markdown("<div class='atlas-divider'></div>", unsafe_allow_html=True)
        section_title("Decision Result", "Recommendation, Top 3 ranking, engineering gate and model context.")
        try:
            _hybrid.render_eor_intelligence_result(result)
        except Exception as exc:
            st.error(f"Hybrid intelligence result could not be displayed: {exc}")
