"""Engineering Screening page."""

from __future__ import annotations

import streamlit as st

from ui.components import insight_cards, section_title


def render() -> None:
    import app_2 as _app
    import hybrid_app as _hybrid

    insight_cards([
        ("INPUT", "Define the reservoir", "Enter the reservoir, recovery and injection context required by ScreenTool v3."),
        ("GATE", "Test engineering feasibility", "Each EOR technique is evaluated against deterministic engineering criteria."),
        ("OUTPUT", "Understand why", "Review PASS, CONDITIONAL and FAIL outcomes together with the engineering basis."),
    ])
    st.markdown("<div class='atlas-divider'></div>", unsafe_allow_html=True)

    section_title("Reservoir Inputs", "Current So is a core screening input. Sorw and numeric Produced GOR are optional v3 context inputs.")
    inputs, formation = _hybrid.render_eor_input_form("screening")

    if st.button("🚀 Run EOR Screening", type="primary", use_container_width=True, key="ui_screening_run"):
        try:
            result = _app.ExcelScreeningService().screen(inputs, formation)
            st.session_state["excel_screening_result"] = result
        except Exception:
            _app.logger.exception("EOR Screening failed.")
            st.error("The engineering screening could not be completed. Check the entered values.")

    result = st.session_state.get("excel_screening_result")
    if result:
        st.markdown("<div class='atlas-divider'></div>", unsafe_allow_html=True)
        section_title("Engineering Gate Result", "Deterministic output is the engineering feasibility layer used by hybrid decision fusion.")
        try:
            _app.render_excel_screening_result(result)
        except Exception as exc:
            st.error(f"Screening result could not be displayed: {exc}")
