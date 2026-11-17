"""Engineering Screening page."""

from __future__ import annotations

import streamlit as st

from data.screening_history import persist_engineering_run
from ui.components import page_header, reset_button, section_title, kpi_cards, workflow_steps, render_decision_summary


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

    page_header(
        "ENGINEERING WORKSPACE",
        "EOR Screening",
        "Run the deterministic EOR Screening Tool 2026 v3 engineering gate against a defined reservoir context, then review and retain its decision record.",
    )

    action_col, _ = st.columns([1, 5])
    with action_col:
        reset_button(
            "↺ Reset screening inputs",
            prefixes="screening_",
            result_keys=("excel_screening_result", "screening_last_run"),
            key="screening_reset_inputs",
        )

    section_title(
        "1. Define the reservoir",
        "Complete the reservoir, recovery and operating context. Editing inputs does not execute the engineering gate.",
    )
    with st.container(border=True):
        with st.form("screening_reservoir_form", clear_on_submit=False):
            inputs, formation = _hybrid.render_eor_input_form("screening")
            st.caption(
                "Submit once when the reservoir context is complete. This page runs the deterministic Excel Gate only; CatBoost and Decision Fusion are handled in Hybrid Intelligence."
            )
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
    last_run = st.session_state.get("screening_last_run")
    status = "Result available" if result else "Awaiting submission"
    report_reference = last_run.get("reference", "Saved") if last_run else "Not saved"

    kpi_cards(
        [
            ("Workflow", status, "Current screening state"),
            ("Decision layer", "Excel Gate", "Deterministic engineering assessment"),
            ("Execution", "Submit-driven", "No gate execution during field edits"),
            ("Report card", report_reference, "Persistent record for the latest successful save"),
        ]
    )

    completed_steps = 3 if result and last_run else 1 if result else 0
    workflow_steps(
        ["Reservoir context", "Engineering Gate", "Audit record"],
        current_step=completed_steps,
    )

    st.divider()
    section_title(
        "2. Engineering Gate result",
        "Review technique-level feasibility and the deterministic assessment returned by the existing Excel Screening service.",
    )
    if not result:
        st.info(
            "No screening result is available yet. Complete the reservoir form above and submit the Engineering Gate to generate the assessment."
        )
        return

    summary_title, summary_body, summary_rows = _screening_summary(result)
    render_decision_summary(
        summary_title,
        summary_body,
        "Ready" if summary_rows else "Warning",
        summary_rows,
    )
    if last_run:
        st.caption(f"Saved report card: **{last_run['reference']}**")
    else:
        st.warning(
            "The engineering result is available in this session, but no saved report card was confirmed. Check the persistence error before treating this run as an archived record."
        )

    section_title(
        "Technique-level engineering assessment",
        "The original result renderer is retained so every technique, criterion and result detail continues to come from the existing Excel Gate output.",
    )
    try:
        _app.render_excel_screening_result(result)
    except Exception as exc:
        st.error(f"Screening result could not be displayed: {exc}")
