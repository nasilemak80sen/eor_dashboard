"""Engineering Screening page."""
from __future__ import annotations
import streamlit as st

from data.screening_history import persist_engineering_run
from ui.components import insight_cards, reset_button, section_title, kpi_cards
from ui.decision import data_quality, decision_trace, next_steps, view_mode, why_why_not


def render() -> None:
    import app_2 as _app
    import hybrid_app as _hybrid

    insight_cards([
        ("01 · INPUT", "Define the reservoir", "Enter the complete ScreenTool v3 reservoir and operating context."),
        ("02 · GATE", "Test feasibility", "Submit the completed form once; the deterministic gate evaluates every EOR technique."),
        ("03 · RECORD", "Create a report card", "Every submitted screening is saved with its exact inputs and engineering decision trace."),
    ])
    st.markdown("<div class='atlas-divider'></div>", unsafe_allow_html=True)

    result = st.session_state.get("excel_screening_result")
    last_run = st.session_state.get("screening_last_run")
    status = "Result available" if result else "Awaiting screening"
    kpi_cards([
        ("Workflow", "Result available" if result else "Awaiting screening", "Current page state"),
        ("Primary input", "Current So", "Core screening parameter"),
        ("Decision rule", "Excel Gate", "Deterministic engineering layer"),
        ("Report Card", last_run.get("reference", "Not saved") if last_run else "Not saved", "Persistent screening record"),
    ])

    inputs_tab, result_tab = st.tabs(["Reservoir Inputs", "Engineering Decision"])
    with inputs_tab:
        action_col, _ = st.columns([1, 4])
        with action_col:
            reset_button(
                "↺ Reset inputs",
                prefixes="screening_",
                result_keys=("excel_screening_result", "screening_last_run"),
                key="screening_reset_inputs",
            )
        section_title(
            "Reservoir Inputs",
            "Complete the reservoir context first. No engineering gate is executed while individual fields are edited.",
        )
        with st.form("screening_reservoir_form", clear_on_submit=False):
            inputs, formation = _hybrid.render_eor_input_form("screening")
            st.caption("Complete the form, then submit once to run and save the Engineering Gate.")
            submitted = st.form_submit_button(
                "🚀 Run EOR Screening",
                type="primary",
                use_container_width=True,
            )
        if submitted:
            try:
                result = _app.ExcelScreeningService().screen(inputs, formation)
                st.session_state["excel_screening_result"] = result
                st.session_state["screening_last_run"] = persist_engineering_run(inputs, formation, result)
                st.toast(
                    f"Screening saved as {st.session_state['screening_last_run']['reference']}",
                    icon="✅",
                )
            except Exception:
                _app.logger.exception("EOR Screening failed.")
                st.error("The engineering screening could not be completed or saved. Check the entered values.")

    result = st.session_state.get("excel_screening_result")
    with result_tab:
        if not result:
            st.info("No screening result yet. Complete Reservoir Inputs and submit the Engineering Gate.")
            return
        section_title(
            "Engineering Gate Result",
            "This deterministic result is the engineering anchor for the downstream hybrid decision path and is now persisted for audit/history.",
        )
        if last_run := st.session_state.get("screening_last_run"):
            st.caption(f"Saved report card: **{last_run['reference']}**")
        with st.expander("Re-run / change inputs", expanded=False):
            st.caption("Return to Reservoir Inputs, change the reservoir context, and submit the gate again. A new report card will be created.")
        try:
            _app.render_excel_screening_result(result)
        except Exception as exc:
            st.error(f"Screening result could not be displayed: {exc}")
            return

        rows = result.get("results") or result.get("techniques") or result.get("ranking") or []
        if isinstance(rows, dict):
            rows = list(rows.values())
        pass_count = conditional_count = fail_count = 0
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, dict):
                continue
            status = str(row.get("Status") or row.get("status") or row.get("Engineering Status") or "").upper()
            pass_count += status == "PASS"
            conditional_count += status == "CONDITIONAL"
            fail_count += status == "FAIL"
        kpi_cards([
            ("Engineering PASS", pass_count, "Techniques meeting the gate"),
            ("Conditional", conditional_count, "Requires further validation"),
            ("FAIL", fail_count, "Excluded from downstream hybrid logic"),
            ("Decision anchor", "Excel Gate", "Deterministic engineering basis"),
        ])

        if mode == "Engineering":
            with st.expander("Decision Trace", expanded=True):
                decision_trace(result, None, rows if isinstance(rows, list) else [])
            with st.expander("Why / Why Not", expanded=True):
                why_why_not(rows if isinstance(rows, list) else [])
            with st.expander("Data & Assumption Quality", expanded=False):
                data_quality(inputs_state)
        else:
            st.info("Leadership view keeps the outcome focused on feasibility, status and the downstream decision hand-off.")
            with st.expander("Why / Why Not", expanded=True):
                why_why_not(rows if isinstance(rows, list) else [], max_items=2)

        with st.expander("Recommended Next Steps", expanded=True):
            recommendation = rows[0] if isinstance(rows, list) and rows and isinstance(rows[0], dict) else None
            next_steps(recommendation)
