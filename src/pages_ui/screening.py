"""Engineering Screening page."""

from __future__ import annotations

import streamlit as st

from data.screening_history import persist_engineering_run
from ui.components import insight_cards, reset_button, section_title, kpi_cards, workflow_steps, render_decision_summary


def _screening_summary(result: dict | None) -> tuple[str, str, list[tuple[str, object]]]:
    if not result or not result.get("results"):
        return "Awaiting input", "Complete the form to run the engineering gate.", [("Current status", "No result yet")]

    rows = result.get("results", []) or []
    pass_count = sum(1 for item in rows if str(item.get("Status", "")).upper() == "PASS")
    conditional_count = sum(1 for item in rows if str(item.get("Status", "")).upper() == "CONDITIONAL")
    fail_count = sum(1 for item in rows if str(item.get("Status", "")).upper() == "FAIL (CRITICAL)")
    best = max(rows, key=lambda item: float(item.get("Score (%)", 0)), default={})
    status_label = "Ready" if pass_count or conditional_count else "Warning"
    return (
        "Recommendation ready",
        f"Best technique: {best.get('EOR Technique', 'N/A')} at {best.get('Score (%)', 0):.1f}% suitability.",
        [("Pass", pass_count), ("Conditional", conditional_count), ("Fail", fail_count), ("Top technique", best.get("EOR Technique", "N/A"))],
    )


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
        ("Workflow", status, "Current page state"),
        ("Primary input", "Current So", "Core screening parameter"),
        ("Decision rule", "Excel Gate", "Deterministic engineering layer"),
        ("Report Card", last_run.get("reference", "Not saved") if last_run else "Not saved", "Persistent screening record"),
    ])

    inputs_tab, result_tab = st.tabs(["Reservoir Inputs", "Engineering Gate"])
    with inputs_tab:
        workflow_steps(["Reservoir basics", "Recovery context", "Engineering review"], current_step=0)
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
            st.info("No screening result yet. Complete the Reservoir Inputs tab and submit the Engineering Gate.")
            return
        summary_title, summary_body, summary_rows = _screening_summary(result)
        render_decision_summary(
            summary_title,
            summary_body,
            "Ready" if summary_rows else "Warning",
            summary_rows,
        )
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
