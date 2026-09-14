"""Engineering Screening page."""

from __future__ import annotations

import streamlit as st

from ui.components import insight_cards, reset_button, section_title, kpi_cards


def render() -> None:
    import app_2 as _app
    import hybrid_app as _hybrid

    insight_cards([
        ("01 · INPUT", "Define the reservoir", "Enter the complete ScreenTool v3 reservoir and operating context."),
        ("02 · GATE", "Test feasibility", "Submit the completed form once; the deterministic gate then evaluates every EOR technique."),
        ("03 · REVIEW", "Understand why", "PASS, CONDITIONAL and FAIL outcomes remain traceable to their engineering criteria."),
    ])
    st.markdown("<div class='atlas-divider'></div>", unsafe_allow_html=True)

    result = st.session_state.get("excel_screening_result")
    status = "Result available" if result else "Awaiting screening"
    kpi_cards([
        ("Workflow", status, "Current page state"),
        ("Primary input", "Current So", "Core screening parameter"),
        ("Decision rule", "Excel Gate", "Deterministic engineering layer"),
    ])

    inputs_tab, result_tab = st.tabs(["Reservoir Inputs", "Engineering Gate"])
    with inputs_tab:
        action_col, _ = st.columns([1, 4])
        with action_col:
            reset_button(
                "↺ Reset inputs",
                prefixes="screening_",
                result_keys=("excel_screening_result",),
                key="screening_reset_inputs",
            )
        section_title(
            "Reservoir Inputs",
            "Complete the reservoir context first. No engineering gate is executed while individual fields are edited.",
        )
        with st.form("screening_reservoir_form", clear_on_submit=False):
            inputs, formation = _hybrid.render_eor_input_form("screening")
            st.caption("Complete the form, then submit once to run the Engineering Gate.")
            submitted = st.form_submit_button(
                "🚀 Run EOR Screening",
                type="primary",
                use_container_width=True,
            )
        if submitted:
            try:
                st.session_state["excel_screening_result"] = _app.ExcelScreeningService().screen(inputs, formation)
                st.toast("EOR engineering screening completed", icon="✅")
            except Exception:
                _app.logger.exception("EOR Screening failed.")
                st.error("The engineering screening could not be completed. Check the entered values.")

    result = st.session_state.get("excel_screening_result")
    with result_tab:
        if not result:
            st.info("No screening result yet. Complete the Reservoir Inputs tab and submit the Engineering Gate.")
            return
        section_title(
            "Engineering Gate Result",
            "This deterministic result is the engineering anchor for the downstream hybrid decision path.",
        )
        with st.expander("Re-run / change inputs", expanded=False):
            st.caption("Return to Reservoir Inputs, change the reservoir context, and submit the gate again.")
        try:
            _app.render_excel_screening_result(result)
        except Exception as exc:
            st.error(f"Screening result could not be displayed: {exc}")
