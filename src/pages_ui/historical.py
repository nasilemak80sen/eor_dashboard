"""Historical EOR report-card and decision-history page."""

from __future__ import annotations

import json
from typing import Any, Dict

import pandas as pd
import streamlit as st

from data.screening_history import get_report_card, list_report_cards
from ui.components import kpi_cards, section_title


def _parse_json(value: Any) -> Any:
    if value is None or value == "":
        return None
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return value


def _fmt_number(value: Any, decimals: int = 2) -> str:
    try:
        return f"{float(value):,.{decimals}f}"
    except (TypeError, ValueError):
        return "—"


def _render_register(records: list[Dict[str, Any]]) -> int | None:
    if not records:
        st.info("No screening report cards have been saved yet. Run EOR Screening or Hybrid Intelligence first.")
        return None

    df = pd.DataFrame(records)
    df["Reference"] = df.apply(
        lambda row: f"EOR-{str(row.get('timestamp', ''))[:4]}-{int(row['id']):06d}", axis=1
    )
    df["Timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M")
    df["Mode"] = df["recommendation_mode"].fillna("—")
    df["Recommendation"] = df["recommended_technique"].fillna("—")
    df["Score"] = pd.to_numeric(df["recommendation_score"], errors="coerce").round(1)
    df["Status"] = df["recommendation_status"].fillna("—")

    view = df[["Reference", "Timestamp", "Formation", "Mode", "Recommendation", "Status", "Score"]].copy()
    view.columns = ["Run ID", "Timestamp", "Formation", "Run Type", "Recommendation", "Status", "Score"]
    st.dataframe(view, use_container_width=True, hide_index=True)

    options = {
        row["Reference"]: int(row["id"])
        for _, row in df.iterrows()
    }
    selected_label = st.selectbox(
        "Open a report card",
        list(options.keys()),
        key="historical_selected_run",
    )
    return options[selected_label]


def _render_input_snapshot(inputs: Dict[str, Any]) -> None:
    if not inputs:
        st.info("No exact input snapshot was stored for this historical run.")
        return

    preferred_order = [
        "depth_ft", "reservoir_pressure", "temperature_c", "visc_cp", "api", "perm_md",
        "porosity_frac", "porosity_pct", "so_pct", "salinity_ppm", "hardness_ppm",
        "rock_type", "net_pay_m", "heterogeneity", "gas_availability", "oxygen_present",
        "ooip_mmstb", "base_rf_pct", "drive_mechanism", "co2_availability", "mmp_satisfied",
        "waterflood_history", "water_cut_pct", "field_maturity", "mobility_ratio",
        "adsorption_risk", "water_handling", "offshore", "water_injection_facilities",
        "gas_injection_facilities", "wag_ratio", "gas_injectivity", "water_injectivity",
        "gravity_override_risk", "hc_gas_availability", "produced_gor_category",
        "gas_reinjectable", "produced_gor_scf_stb", "sorw_pct",
    ]
    keys = [key for key in preferred_order if key in inputs]
    keys += [key for key in inputs if key not in keys]

    rows = []
    for key in keys:
        value = inputs[key]
        rows.append({
            "Parameter": key.replace("_", " ").title(),
            "Value": value if value not in (None, "") else "—",
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def _render_engineering(card: Dict[str, Any]) -> None:
    rows = card.get("engineering", [])
    if not rows:
        st.info("No engineering result records were stored for this run.")
        return
    frame = pd.DataFrame(rows)
    if "details" in frame.columns:
        details = frame["details"].map(_parse_json)
        detail_rows = [item for item in details if isinstance(item, dict)]
        if detail_rows:
            frame = pd.DataFrame(detail_rows)
    wanted = [
        "EOR Technique", "Status", "Suitability", "Score (%)", "ΔRF_EOR (%)",
        "Final RF (%)", "EUR (MMstb)", "Cause of Fail/Pass",
    ]
    available = [column for column in wanted if column in frame.columns]
    if available:
        st.dataframe(frame[available], use_container_width=True, hide_index=True)
    else:
        st.dataframe(frame, use_container_width=True, hide_index=True)


def _render_ml(card: Dict[str, Any]) -> None:
    rows = card.get("ml", [])
    if not rows:
        st.info("No CatBoost result records were stored. This may be an Engineering-only run.")
        return
    frame = pd.DataFrame(rows)
    frame["Probability"] = pd.to_numeric(frame["probability"], errors="coerce").fillna(0.0)
    frame["Probability"] = (frame["Probability"] * 100).round(2).astype(str) + "%"
    frame["Top Prediction"] = frame["is_top_prediction"].map(lambda value: "Yes" if bool(value) else "No")
    st.dataframe(
        frame[["technique", "Probability", "Top Prediction", "confidence"]].rename(
            columns={"technique": "EOR Technique", "confidence": "Confidence"}
        ),
        use_container_width=True,
        hide_index=True,
    )


def _render_hybrid(card: Dict[str, Any]) -> None:
    rows = card.get("hybrid", [])
    if not rows:
        st.info("No Hybrid Fusion result records were stored for this run.")
        return
    frame = pd.DataFrame(rows)
    for column in ["hybrid_score", "catboost_probability", "engineering_score"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0.0).map(lambda value: f"{value:.1%}")
    frame["Recommended"] = frame["is_recommended"].map(lambda value: "Yes" if bool(value) else "")
    st.dataframe(
        frame[["rank", "technique", "hybrid_score", "catboost_probability", "engineering_score", "engineering_status", "Recommended"]].rename(
            columns={
                "rank": "Rank", "technique": "EOR Technique", "hybrid_score": "Hybrid Score",
                "catboost_probability": "CatBoost", "engineering_score": "Engineering",
                "engineering_status": "Engineering Status",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )


def _render_report_card(card: Dict[str, Any]) -> None:
    run = card["run"]
    reference = card["reference"]
    inputs = _parse_json(run.get("input_payload")) or {}
    evidence = _parse_json(run.get("evidence_summary")) or {}
    assumptions = _parse_json(run.get("assumptions")) or {}

    section_title(
        f"Screening Report Card · {reference}",
        "The exact submitted inputs and the independent Engineering, CatBoost, and Hybrid decision records captured for this run.",
    )

    recommendation = run.get("recommended_technique") or "No recommendation"
    score = run.get("recommendation_score")
    mode = run.get("recommendation_mode") or "ENGINEERING"
    cols = st.columns(5)
    cols[0].metric("Run ID", reference)
    cols[1].metric("Run Type", mode)
    cols[2].metric("Formation", run.get("formation") or "—")
    cols[3].metric("Recommendation", recommendation)
    cols[4].metric("Decision Score", _fmt_number(score, 1) if score is not None else "—")

    st.markdown("### 1 · User Input Snapshot")
    _render_input_snapshot(inputs)

    engineering_tab, ml_tab, hybrid_tab, trace_tab = st.tabs([
        "Engineering", "CatBoost", "Hybrid Fusion", "Decision Trace",
    ])
    with engineering_tab:
        st.caption("Deterministic engineering eligibility captured at submission time.")
        _render_engineering(card)
    with ml_tab:
        st.caption("CatBoost probabilities captured from the active model used for this run.")
        _render_ml(card)
    with hybrid_tab:
        st.caption("Final ranking created by the production Engineering + CatBoost decision fusion.")
        _render_hybrid(card)
    with trace_tab:
        st.markdown("#### Decision Path")
        st.code("User Inputs → Excel Engineering Gate → CatBoost → Decision Fusion → Report Card")
        trace = _parse_json(run.get("rule_trace"))
        if trace:
            with st.expander("Engineering rule trace", expanded=False):
                st.json(trace)
        with st.expander("Recorded assumptions / provenance", expanded=False):
            st.json({"assumptions": assumptions, "evidence": evidence})
        st.caption(
            f"Model version: {run.get('model_version') or '—'} · "
            f"Workbook version: {run.get('workbook_version') or '—'} · "
            f"Rule version: {run.get('rule_version') or '—'}"
        )


def _numeric_input_map(card: Dict[str, Any]) -> Dict[str, float]:
    inputs = _parse_json(card["run"].get("input_payload")) or {}
    output: Dict[str, float] = {}
    for key, value in inputs.items():
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            output[key] = float(value)
    return output


def _render_compare(left: Dict[str, Any], right: Dict[str, Any]) -> None:
    st.markdown("### Compare Screening Runs")
    left_ref, right_ref = left["reference"], right["reference"]
    st.caption(f"Comparing **{left_ref}** against **{right_ref}**")

    left_inputs = _parse_json(left["run"].get("input_payload")) or {}
    right_inputs = _parse_json(right["run"].get("input_payload")) or {}
    keys = list(dict.fromkeys(list(left_inputs.keys()) + list(right_inputs.keys())))
    rows = []
    for key in keys:
        lv, rv = left_inputs.get(key), right_inputs.get(key)
        delta = None
        try:
            if isinstance(lv, (int, float)) and isinstance(rv, (int, float)):
                delta = float(rv) - float(lv)
        except (TypeError, ValueError):
            delta = None
        rows.append({
            "Parameter": key.replace("_", " ").title(),
            left_ref: lv if lv not in (None, "") else "—",
            right_ref: rv if rv not in (None, "") else "—",
            "Δ (Right − Left)": _fmt_number(delta, 2) if delta is not None else "—",
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    result_cols = st.columns(3)
    for col, title, card in [
        (result_cols[0], "Engineering Recommendation", left),
        (result_cols[1], "CatBoost Signal", right),
        (result_cols[2], "Hybrid Recommendation", right),
    ]:
        with col:
            run = card["run"]
            st.metric(title, run.get("recommended_technique") or "—")
            st.caption(
                f"Mode: {run.get('recommendation_mode') or '—'} · "
                f"Score: {_fmt_number(run.get('recommendation_score'), 1)}"
            )


def render() -> None:
    """Render the durable EOR screening history workspace."""
    try:
        records = list_report_cards(days=3650)
    except Exception as exc:
        st.error(f"Historical screening storage is unavailable: {exc}")
        return

    engineering_count = sum(record.get("recommendation_mode") == "ENGINEERING" for record in records)
    hybrid_count = sum(record.get("recommendation_mode") == "HYBRID" for record in records)
    kpi_cards([
        ("Saved Runs", len(records), "Persisted screening report cards"),
        ("Engineering Runs", engineering_count, "Excel Gate submissions"),
        ("Hybrid Runs", hybrid_count, "Excel + CatBoost + Fusion submissions"),
        ("Audit Source", "SQLite", "Persistent local decision history"),
    ])

    register_tab, card_tab, compare_tab = st.tabs([
        "Run Register", "Screening Report Card", "Compare Runs",
    ])

    with register_tab:
        section_title(
            "Screening Run Register",
            "Every submitted screening becomes a durable case with a stable Run ID and exact input snapshot.",
        )
        selected_id = _render_register(records)
        if selected_id is not None and st.button("Open selected report card", key="historical_open_card", type="primary"):
            st.session_state["historical_open_run_id"] = selected_id
            st.rerun()

    with card_tab:
        selected_id = st.session_state.get("historical_open_run_id")
        if selected_id is None and records:
            selected_id = int(records[0]["id"])
        if selected_id is None:
            st.info("Select a saved run from the Run Register to inspect its report card.")
        else:
            try:
                card = get_report_card(int(selected_id))
            except Exception as exc:
                card = None
                st.error(f"Unable to load the selected report card: {exc}")
            if card:
                _render_report_card(card)
            else:
                st.info("The selected report card no longer exists.")

    with compare_tab:
        if len(records) < 2:
            st.info("At least two saved screening runs are required for comparison.")
            return
        options = {
            f"EOR-{str(row.get('timestamp', ''))[:4]}-{int(row['id']):06d}": int(row["id"])
            for row in records
        }
        labels = list(options.keys())
        left_label = st.selectbox("Left run", labels, index=0, key="historical_compare_left")
        right_label = st.selectbox("Right run", labels, index=1 if len(labels) > 1 else 0, key="historical_compare_right")
        if left_label == right_label:
            st.warning("Choose two different screening runs to compare.")
        else:
            left_card = get_report_card(options[left_label])
            right_card = get_report_card(options[right_label])
            if left_card and right_card:
                _render_compare(left_card, right_card)
