"""Hybrid Intelligence page."""

from __future__ import annotations

import pandas as pd

import streamlit as st

from data.screening_history import persist_hybrid_run
from ui.components import (
    page_header,
    reset_button,
    section_title,
    kpi_cards,
    metric_cards,
    workflow_steps,
    render_decision_summary,
)


def _hybrid_summary(result: dict | None) -> tuple[str, str, list[tuple[str, object]]]:
    if not result:
        return (
            "Awaiting run",
            "Complete the form to generate an engineering-plus-ML recommendation.",
            [("Current status", "No result yet")],
        )

    hybrid = (result or {}).get("hybrid", {}) or {}
    recommendation = hybrid.get("recommendation") or {}
    ranking = hybrid.get("ranking", []) or []
    eligible_count = hybrid.get("eligible_count", len(ranking))

    if not recommendation:
        return (
            "No eligible recommendation",
            "Decision Fusion did not produce an eligible technique from the current engineering-gated model candidates.",
            [("Eligible techniques", eligible_count), ("Displayed rankings", len(ranking))],
        )

    top_name = recommendation.get("EOR Technique", "N/A")
    top_score = recommendation.get("Hybrid Score")
    engineering_status = recommendation.get("Engineering Status", "Not supplied")
    score_label = "—" if top_score is None else f"{float(top_score):.1%}"
    return (
        "Recommendation after engineering gate",
        f"Decision Fusion ranks {top_name} first among the eligible mapped candidates.",
        [
            ("Recommended technique", top_name),
            ("Hybrid rank score", score_label),
            ("Engineering gate", engineering_status),
            ("Eligible techniques", eligible_count),
        ],
    )


def _gate_outcomes(result: dict) -> tuple[list[dict], dict[str, int]]:
    screening = result.get("screening", {}) or {}
    source_rows = screening.get("results", []) or []
    rows = [row for row in source_rows if isinstance(row, dict)]

    counts = {"PASS": 0, "CONDITIONAL": 0, "FAIL": 0, "OTHER": 0}
    table_rows = []
    for row in rows:
        status = str(row.get("Status", "")).strip().upper()
        if status == "PASS":
            counts["PASS"] += 1
        elif status == "CONDITIONAL":
            counts["CONDITIONAL"] += 1
        elif status in {"FAIL", "FAIL (CRITICAL)"}:
            counts["FAIL"] += 1
        else:
            counts["OTHER"] += 1

        score = row.get("Score (%)")
        try:
            score_value = f"{float(score):.1f}%"
        except (TypeError, ValueError):
            score_value = "—"
        table_rows.append(
            {
                "EOR Technique": row.get("EOR Technique", "—"),
                "Engineering Status": row.get("Status", "—"),
                "Engineering Score": score_value,
                "Gate Finding": row.get("Cause of Fail/Pass", "—"),
            }
        )
    return table_rows, counts


def _render_engineering_layer(result: dict) -> None:
    section_title(
        "01 · Engineering feasibility",
        "Deterministic Excel Gate outcomes. FAIL and FAIL (CRITICAL) are hard exclusions from the downstream fusion ranking.",
    )
    gate_rows, counts = _gate_outcomes(result)
    if not gate_rows:
        st.warning("The current result does not contain technique-level engineering gate rows.")
        return

    metric_cards(
        [
            ("PASS", counts["PASS"], "Gate outcome"),
            ("CONDITIONAL", counts["CONDITIONAL"], "Gate outcome"),
            ("FAIL / CRITICAL", counts["FAIL"], "Hard-excluded by Decision Fusion"),
        ],
        columns=3,
        tone="blue",
    )
    if counts["OTHER"]:
        st.caption(f"Other or unclassified gate outcomes: {counts['OTHER']:,}")
    st.dataframe(
        pd.DataFrame(gate_rows),
        use_container_width=True,
        hide_index=True,
    )


def _render_catboost_layer(result: dict) -> None:
    section_title(
        "02 · CatBoost model signal",
        "Class-level model probabilities are shown independently of engineering feasibility. A high probability is not a gate pass or an eligibility decision.",
    )
    probabilities = result.get("ml_probabilities", {}) or {}
    if not result.get("ml_available") or not probabilities:
        st.warning("CatBoost probabilities are unavailable for this run.")
        if result.get("ml_error"):
            st.caption(f"Model detail: {result['ml_error']}")
        return

    model_rows = []
    for model_class, probability in sorted(
        probabilities.items(),
        key=lambda item: float(item[1]),
        reverse=True,
    ):
        try:
            probability_label = f"{float(probability):.1%}"
        except (TypeError, ValueError):
            probability_label = "Unavailable"
        model_rows.append(
            {
                "CatBoost class": str(model_class),
                "Model probability": probability_label,
            }
        )
    st.dataframe(
        pd.DataFrame(model_rows),
        use_container_width=True,
        hide_index=True,
    )
    st.caption(
        "These probabilities describe the model's class signal only. The ScreenTool taxonomy mapping and deterministic gate determine which techniques can enter Decision Fusion."
    )


def _render_fusion_layer(result: dict, hybrid_app) -> None:
    section_title(
        "03 · Decision Fusion recommendation",
        "The fused ranking combines model signal with engineering scores only after hard gate failures have been excluded.",
    )
    hybrid = result.get("hybrid", {}) or {}
    recommendation = hybrid.get("recommendation")
    ranking = hybrid.get("ranking", []) or []
    eligible_count = hybrid.get("eligible_count", len(ranking))

    if not recommendation:
        st.warning(
            "No eligible EOR technique was produced. Review the engineering outcomes and CatBoost availability; do not infer eligibility from model probability alone."
        )
        metric_cards(
            [("Eligible techniques", eligible_count, "After engineering gate and taxonomy mapping")],
            columns=1,
            tone="warning",
        )
    else:
        summary_title, summary_body, summary_rows = _hybrid_summary(result)
        render_decision_summary(
            summary_title,
            summary_body,
            "Ready",
            summary_rows,
        )
        metric_cards(
            [
                ("Eligible techniques", eligible_count, "After engineering gate and taxonomy mapping"),
                ("Displayed ranking", len(ranking), "Top-N fusion output"),
            ],
            columns=2,
            tone="accent",
        )

    if ranking:
        ranking_rows = []
        for rank, row in enumerate(ranking, start=1):
            ranking_rows.append(
                {
                    "Rank": rank,
                    "EOR Technique": row.get("EOR Technique", "—"),
                    "Hybrid rank score": (
                        "—"
                        if row.get("Hybrid Score") is None
                        else f"{float(row.get('Hybrid Score')):.1%}"
                    ),
                    "CatBoost class probability": (
                        "—"
                        if row.get("CatBoost Probability") is None
                        else f"{float(row.get('CatBoost Probability')):.1%}"
                    ),
                    "Engineering score": (
                        "—"
                        if row.get("Engineering Score") is None
                        else f"{float(row.get('Engineering Score')):.1%}"
                    ),
                    "Engineering status": row.get("Engineering Status", "—"),
                }
            )
        st.dataframe(
            pd.DataFrame(ranking_rows),
            use_container_width=True,
            hide_index=True,
        )
        st.caption(
            "Hybrid rank score is normalized over the displayed Top-N results. It is not a CatBoost probability or an independent estimate of technical success."
        )

    with st.expander("Full decision trace, ScreenTool context and configuration", expanded=False):
        hybrid_app.render_eor_intelligence_result(result)


def render(services: dict) -> None:
    import hybrid_app as _hybrid

    page_header(
        "ENGINEERING + MACHINE LEARNING",
        "Hybrid Intelligence",
        "Combine deterministic engineering feasibility with CatBoost class probabilities, then review the gated Decision Fusion recommendation.",
    )

    action_col, _ = st.columns([1, 5])
    with action_col:
        reset_button(
            "↺ Reset hybrid inputs",
            prefixes="intel_",
            result_keys=("eor_intelligence_result", "intelligence_last_run"),
            key="intelligence_reset_inputs",
        )

    section_title(
        "1. Define the reservoir context",
        "Use the same ScreenTool v3 input schema as EOR Screening. No Excel Gate, CatBoost inference or Decision Fusion calculation runs while fields are edited.",
    )
    with st.container(border=True):
        with st.form("hybrid_reservoir_form", clear_on_submit=False):
            inputs, formation = _hybrid.render_eor_input_form("intel")
            st.caption(
                "Submit once to execute Excel Gate → CatBoost → Decision Fusion and save the combined decision record."
            )
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
    last_run = st.session_state.get("intelligence_last_run")
    kpi_cards(
        [
            ("Workflow", "Result available" if result else "Awaiting submission", "Latest submitted run"),
            ("Engineering", "Excel Gate", "Deterministic feasibility layer"),
            ("Model", "CatBoost", "Class probability layer"),
            ("Report card", last_run.get("reference", "Saved") if last_run else "Not saved", "Combined persistent record"),
        ]
    )

    completed_steps = 3 if result and last_run else 2 if result else 0
    workflow_steps(
        ["Reservoir context", "Engineering + model run", "Decision record"],
        current_step=completed_steps,
    )

    st.divider()
    if not result:
        st.info(
            "No Hybrid Intelligence result is available yet. Complete the reservoir context and submit the form to run the three-stage decision path."
        )
        return

    if last_run:
        st.caption(f"Saved hybrid report card: **{last_run['reference']}**")
    else:
        st.warning(
            "The hybrid result is available in this session, but a saved report card has not been confirmed. Check the persistence error before treating this run as archived."
        )

    section_title(
        "2. Read the three decision layers separately",
        "Each layer answers a different question. Only the fused result below represents the final ranked recommendation.",
    )
    _render_engineering_layer(result)
    st.divider()
    _render_catboost_layer(result)
    st.divider()
    _render_fusion_layer(result, _hybrid)
