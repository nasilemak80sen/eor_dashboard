"""Engineering Screening page."""

from __future__ import annotations

import streamlit as st

from ui.components import insight_cards, reset_button, section_title, kpi_cards


def render() -> None:
    import app_2 as _app
    import hybrid_app as _hybrid

    insight_cards([
        ("01 · INPUT", "Define the reservoir", "Enter the complete ScreenTool v3 reservoir and operating context."),
        ("02 · GATE", "Test feasibility", "Deterministic criteria evaluate each EOR technique against the engineering basis."),
        ("03 · REVIEW", "Understand why", "PASS, CONDITIONAL and FAIL outcomes remain traceable to their criteria."),
    ])
    st.markdown("<div class='atlas-divider'></div>", unsafe_allow_html=True)

    result = st.session_state.get("excel_screening_result")
    status = "Result available" if result else "Awaiting screening"
    kpi_cards([("Workflow", status, "Current page state"), ("Primary input", "Current So", "Core screening parameter"), ("Decision rule", "Excel Gate", "Deterministic engineering layer")])

    inputs_tab, result_tab = st.tabs(["Reservoir Inputs", "Engineering Gate"])
    with inputs_tab:
        action_col, _ = st.columns([1, 4])
        with action_col:
            reset_button("↺ Reset inputs", prefixes="screening_", result_keys=("excel_screening_result",), key="screening_reset_inputs")
        section_title("Reservoir Inputs", "Current So is required for the live gate; Sorw and numeric Produced GOR are optional context inputs.")
        inputs, formation = _hybrid.render_eor_input_form("screening")
        st.caption("Tip: widen the browser for the full engineering form. Values update immediately, while the gate runs only when you submit.")
        if st.button("🚀 Run EOR Screening", type="primary", use_container_width=True, key="ui_screening_run"):
            try:
                st.session_state["excel_screening_result"] = _app.ExcelScreeningService().screen(inputs, formation)
                st.toast("EOR engineering screening completed", icon="✅")
            except Exception:
                _app.logger.exception("EOR Screening failed.")
                st.error("The engineering screening could not be completed. Check the entered values.")

    with result_tab:
        if not result:
            st.info("No screening result yet. Complete the Reservoir Inputs tab and run the Engineering Gate.")
            return
        section_title("Engineering Gate Result", "This deterministic result is the engineering anchor for the downstream hybrid decision path.")
        with st.expander("Re-run / change inputs", expanded=False):
            st.caption("Return to Reservoir Inputs to modify the reservoir context and re-run the gate.")
        try:
            _app.render_excel_screening_result(result)
        except Exception as exc:
            st.error(f"Screening result could not be displayed: {exc}")
