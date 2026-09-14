"""Hybrid Intelligence page."""

from __future__ import annotations

import streamlit as st

from ui.components import insight_cards, reset_button, section_title, kpi_cards


def render(services: dict) -> None:
    import hybrid_app as _hybrid

    insight_cards([
        ("01 · GATE", "Engineering anchor", "Hard engineering failures remain excluded before ML contributes to the recommendation."),
        ("02 · MODEL", "CatBoost signal", "The active model contributes a data-driven technique probability after the form is submitted."),
        ("03 · FUSION", "Decision ranking", "Engineering and model signals are reconciled into an interpretable ranked recommendation."),
    ])
    st.markdown("<div class='atlas-divider'></div>", unsafe_allow_html=True)

    result = st.session_state.get("eor_intelligence_result")
    kpi_cards([
        ("Workflow", "Result available" if result else "Awaiting run", "Current page state"),
        ("Engineering", "Excel Gate", "Deterministic anchor"),
        ("Model", "CatBoost", "Data-driven signal"),
    ])

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
        section_title(
            "Reservoir Context",
            "Complete the same v3 schema used by Engineering Screening. No Excel Gate, CatBoost, or Decision Fusion calculation runs while fields are edited.",
        )
        with st.form("hybrid_reservoir_form", clear_on_submit=False):
            inputs, formation = _hybrid.render_eor_input_form("intel")
            st.caption("Complete the reservoir context, then submit once to run Excel Gate → CatBoost → Decision Fusion.")
            submitted = st.form_submit_button(
                "🧠 Run Hybrid Intelligence",
                type="primary",
                use_container_width=True,
            )
        if submitted:
            try:
                _hybrid._run_intelligence_from_current_inputs(services, inputs, formation)
                st.toast("Hybrid recommendation updated", icon="🧠")
            except Exception as exc:
                st.error(f"Hybrid intelligence could not be completed: {exc}")

    result = st.session_state.get("eor_intelligence_result")
    with decision_tab:
        if not result:
            st.info("No hybrid result yet. Complete Reservoir Inputs and submit Hybrid Intelligence.")
            return
        section_title(
            "Decision Result",
            "Read the recommendation together with the gate status and model context — not as a standalone ML prediction.",
        )
        try:
            _hybrid.render_eor_intelligence_result(result)
        except Exception as exc:
            st.error(f"Hybrid intelligence result could not be displayed: {exc}")
