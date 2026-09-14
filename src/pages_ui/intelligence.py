"""Hybrid Intelligence page."""

from __future__ import annotations

import streamlit as st

from data.screening_history import persist_hybrid_run
from ui.components import insight_cards, reset_button, section_title, kpi_cards


def render(services: dict) -> None:
    import hybrid_app as _hybrid

    insight_cards([
        ("01 · GATE", "Engineering anchor", "Hard engineering failures remain excluded before ML contributes to the recommendation."),
        ("02 · MODEL", "CatBoost signal", "The active model contributes a data-driven technique probability after the form is submitted."),
        ("03 · RECORD", "Decision history", "Engineering, CatBoost and Hybrid recommendations are stored together as an auditable report card."),
    ])
    st.markdown("<div class='atlas-divider'></div>", unsafe_allow_html=True)

    result = st.session_state.get("eor_intelligence_result")
    last_run = st.session_state.get("intelligence_last_run")
    kpi_cards([
        ("Workflow", "Result available" if result else "Awaiting run", "Current page state"),
        ("Engineering", "Excel Gate", "Deterministic anchor"),
        ("Model", "CatBoost", "Data-driven signal"),
        ("Report Card", last_run.get("reference", "Not saved") if last_run else "Not saved", "Persistent hybrid record"),
    ])

    input_tab, decision_tab = st.tabs(["Reservoir Inputs", "Hybrid Decision"])
    with input_tab:
        action_col, _ = st.columns([1, 4])
        with action_col:
            reset_button(
                "↺ Reset inputs",
                prefixes="intel_",
                result_keys=("eor_intelligence_result", "intelligence_last_run"),
                key="intelligence_reset_inputs",
            )
        section_title(
            "Reservoir Context",
            "Complete the same v3 schema used by Engineering Screening. No Excel Gate, CatBoost, or Decision Fusion calculation runs while fields are edited.",
        )
        with st.form("hybrid_reservoir_form", clear_on_submit=False):
            inputs, formation = _hybrid.render_eor_input_form("intel")
            st.caption("Complete the reservoir context, then submit once to run and save Excel Gate → CatBoost → Decision Fusion.")
            submitted = st.form_submit_button(
                "🧠 Run Hybrid Intelligence",
                type="primary",
                use_container_width=True,
            )
        if submitted:
            try:
                _hybrid._run_intelligence_from_current_inputs(services, inputs, formation)
                result = st.session_state.get("eor_intelligence_result")
                if result:
                    st.session_state["intelligence_last_run"] = persist_hybrid_run(result)
                    st.toast(
                        f"Hybrid screening saved as {st.session_state['intelligence_last_run']['reference']}",
                        icon="🧠",
                    )
            except Exception as exc:
                st.error(f"Hybrid intelligence could not be completed or saved: {exc}")

    result = st.session_state.get("eor_intelligence_result")
    with decision_tab:
        if not result:
            st.info("No hybrid result yet. Complete Reservoir Inputs and submit Hybrid Intelligence.")
            return
        section_title(
            "Decision Result",
            "Read the recommendation together with the gate status and model context — not as a standalone ML prediction.",
        )
        if last_run := st.session_state.get("intelligence_last_run"):
            st.caption(f"Saved report card: **{last_run['reference']}**")
        try:
            _hybrid.render_eor_intelligence_result(result)
        except Exception as exc:
            st.error(f"Hybrid intelligence result could not be displayed: {exc}")
