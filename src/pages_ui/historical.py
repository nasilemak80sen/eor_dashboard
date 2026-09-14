"""Historical EOR reference studies and screening decision history."""

from __future__ import annotations

import json
from typing import Any, Dict

import pandas as pd
import plotly.express as px
import streamlit as st

from data.historical_studies import load_historical_studies, merge_manual_studies
from data.screening_history import get_report_card, list_report_cards
from ui.components import kpi_cards, section_title

PAPER_URL = "https://petronas.sharepoint.com/:b:/t/ts_coe_dpereservoirengineer/IQAna3H6SXe_QKMCZsZ3aYsF7AUg2qGi98p4cxD1QI2znO9o?e=EtADtU"


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


def _reference_for_record(row: Dict[str, Any]) -> str:
    timestamp = str(row.get("timestamp") or "")
    return f"EOR-{timestamp[:4] or 'RUN'}-{int(row['id']):06d}"


def _render_historical_filters(frame: pd.DataFrame) -> pd.DataFrame:
    st.markdown("### Past EOR Screening Input")
    field_options = sorted(frame["Field"].dropna().astype(str).unique().tolist())
    study_options = sorted(frame["EOR Study"].dropna().astype(str).unique().tolist())

    a, b = st.columns(2)
    with a:
        selected_fields = st.multiselect(
            "Field",
            field_options,
            default=[],
            placeholder="All fields",
            key="historical_study_fields",
        )
    with b:
        selected_studies = st.multiselect(
            "EOR Studies / Methods",
            study_options,
            default=[],
            placeholder="All EOR studies",
            key="historical_study_methods",
        )

    filtered = frame.copy()
    if selected_fields:
        filtered = filtered[filtered["Field"].isin(selected_fields)]
    if selected_studies:
        filtered = filtered[filtered["EOR Study"].isin(selected_studies)]
    return filtered


def _render_manual_study_entry() -> None:
    with st.expander("➕ Add a historical EOR study record", expanded=False):
        st.caption("Use this for a study record not yet present in the workbook. It remains available for the current dashboard session.")
        with st.form("historical_manual_study_form", clear_on_submit=True):
            a, b, c = st.columns(3)
            with a:
                field = st.text_input("Field", placeholder="e.g. Tapis")
            with b:
                reservoir = st.text_input("Reservoir", placeholder="e.g. J18/20")
            with c:
                study = st.text_input("EOR Study / Method", placeholder="e.g. CO2M WAG")
            eur = st.number_input("Incremental EUR (MMstb)", min_value=0.0, step=1.0, value=0.0)
            submitted = st.form_submit_button("Add historical study", type="secondary")

        if submitted and field.strip() and study.strip() and eur > 0:
            st.session_state.setdefault("historical_manual_rows", []).append(
                {
                    "Field": field.strip(),
                    "Reservoir": reservoir.strip() or "—",
                    "EOR Study": study.strip(),
                    "Incremental EUR (MMstb)": float(eur),
                    "Status": "User added",
                }
            )
            st.toast("Historical EOR study added to this session", icon="✅")
            st.rerun()


def _stacked_bar(frame: pd.DataFrame, category: str, title: str) -> None:
    if frame.empty:
        st.info("No historical records match the selected Field / EOR Study filters.")
        return

    chart_frame = frame[["Field", category, "Incremental EUR (MMstb)"]].copy()
    chart_frame[category] = chart_frame[category].fillna("Unknown")
    chart_frame = (
        chart_frame.groupby(["Field", category], as_index=False)["Incremental EUR (MMstb)"]
        .sum()
    )

    fig = px.bar(
        chart_frame,
        x="Field",
        y="Incremental EUR (MMstb)",
        color=category,
        barmode="stack",
        title=title,
        labels={
            "Field": "Field",
            "Incremental EUR (MMstb)": "INCREMENTAL EUR (MMSTB)",
            category: category,
        },
        custom_data=[category],
    )
    fig.update_traces(
        hovertemplate=(
            "<b>%{x}</b><br>"
            f"{category}: %{{customdata[0]}}<br>"
            "Incremental EUR: %{y:,.2f} MMstb<extra></extra>"
        )
    )
    field_order = (
        chart_frame.groupby("Field")["Incremental EUR (MMstb)"]
        .sum()
        .sort_values(ascending=False)
        .index.tolist()
    )
    fig.update_layout(
        height=430,
        margin=dict(l=50, r=20, t=55, b=110),
        legend_title_text=category,
        xaxis={"categoryorder": "array", "categoryarray": field_order, "tickangle": -60},
        yaxis_title="INCREMENTAL EUR (MMSTB)",
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def _render_historical_eor_reference_section() -> None:
    section_title(
        "Historical EOR Studies",
        "Past EOR screening evidence from the historical Screening_Parameters register, presented in the same decision-oriented form as the reference Power BI page.",
    )

    try:
        source_frame, metadata = load_historical_studies()
    except Exception as exc:
        st.error(f"Historical EOR source data is unavailable: {exc}")
        st.info("Expected a workbook containing a sheet named 'Screening_Parameters'.")
        return

    manual_rows = st.session_state.get("historical_manual_rows", [])
    frame = merge_manual_studies(source_frame, manual_rows)
    filtered = _render_historical_filters(frame)

    kpi_cards([
        ("Historical Fields", filtered["Field"].nunique(), "Fields in selected historical scope"),
        ("EOR Studies", filtered["EOR Study"].nunique(), "Distinct historical methods"),
        ("Reservoirs", filtered["Reservoir"].nunique(), "Reservoirs represented"),
        ("Incremental EUR", _fmt_number(filtered["Incremental EUR (MMstb)"].sum(), 1), "MMstb in selected scope"),
    ])

    st.caption(
        f"Source: `{metadata['source_name']}` · Sheet: `{metadata['sheet_name']}` · "
        f"Records: {metadata['rows']}{' + ' + str(len(manual_rows)) + ' user-added' if manual_rows else ''}"
    )

    st.markdown("#### 📊 Past EOR Screening Result")
    _stacked_bar(filtered, "EOR Study", "INCREMENTAL EUR (MMSTB) by Field and EOR Studies")
    _stacked_bar(filtered, "Reservoir", "INCREMENTAL EUR (MMSTB) by Field and Reservoir")

    with st.expander("View filtered historical records", expanded=False):
        st.dataframe(
            filtered.sort_values(["Field", "Incremental EUR (MMstb)"], ascending=[True, False]),
            use_container_width=True,
            hide_index=True,
        )

    st.info(
        "Source paper used for the historical EOR screening reference: "
        "TITLE: YEAR 2000 IOR/EOR SCREENING FOR MALAYSIA'S OIL PRODUCING FIELDS · YEAR: 2001."
    )
    st.link_button("📄 ACCESS PAPER HERE", PAPER_URL, use_container_width=True)
    _render_manual_study_entry()


def _render_register(records: list[Dict[str, Any]]) -> int | None:
    if not records:
        st.info("No EOR screening report cards have been saved yet. Run EOR Screening or Hybrid Intelligence first.")
        return None

    df = pd.DataFrame(records)
    df["Reference"] = df.apply(_reference_for_record, axis=1)
    df["Timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M")
    df["Formation"] = df["formation"].fillna("—")
    df["Mode"] = df["recommendation_mode"].fillna("—")
    df["Recommendation"] = df["recommended_technique"].fillna("—")
    df["Score"] = pd.to_numeric(df["recommendation_score"], errors="coerce").round(1)
    df["Status"] = df["recommendation_status"].fillna("—")
    view = df[["Reference", "Timestamp", "Formation", "Mode", "Recommendation", "Status", "Score"]].copy()
    view.columns = ["Run ID", "Timestamp", "Formation", "Run Type", "Recommendation", "Status", "Score"]
    st.dataframe(view, use_container_width=True, hide_index=True)

    options = {row["Reference"]: int(row["id"]) for _, row in df.iterrows()}
    selected_label = st.selectbox("Open a report card", list(options.keys()), key="historical_selected_run")
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
    rows = [{"Parameter": key.replace("_", " ").title(), "Value": inputs[key] if inputs[key] not in (None, "") else "—"} for key in keys]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def _render_engineering(card: Dict[str, Any]) -> None:
    rows = card.get("engineering", [])
    if not rows:
        st.info("No engineering result records were stored for this run.")
        return
    frame = pd.DataFrame(rows)
    details = frame["details"].map(_parse_json) if "details" in frame.columns else pd.Series(dtype=object)
    detail_rows = [item for item in details if isinstance(item, dict)]
    if detail_rows:
        frame = pd.DataFrame(detail_rows)
    wanted = ["EOR Technique", "Status", "Suitability", "Score (%)", "ΔRF_EOR (%)", "Final RF (%)", "EUR (MMstb)", "Cause of Fail/Pass"]
    available = [column for column in wanted if column in frame.columns]
    st.dataframe(frame[available] if available else frame, use_container_width=True, hide_index=True)


def _render_ml(card: Dict[str, Any]) -> None:
    rows = card.get("ml", [])
    if not rows:
        st.info("No CatBoost result records were stored. This may be an Engineering-only run.")
        return
    frame = pd.DataFrame(rows)
    frame["Probability"] = pd.to_numeric(frame["probability"], errors="coerce").fillna(0.0).map(lambda value: f"{value:.2%}")
    frame["Top Prediction"] = frame["is_top_prediction"].map(lambda value: "Yes" if bool(value) else "No")
    st.dataframe(frame[["technique", "Probability", "Top Prediction", "confidence"]].rename(columns={"technique": "EOR Technique", "confidence": "Confidence"}), use_container_width=True, hide_index=True)


def _render_hybrid(card: Dict[str, Any]) -> None:
    rows = card.get("hybrid", [])
    if not rows:
        st.info("No Hybrid Fusion result records were stored for this run.")
        return
    frame = pd.DataFrame(rows)
    for column in ["hybrid_score", "catboost_probability", "engineering_score"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0.0).map(lambda value: f"{value:.1%}")
    frame["Recommended"] = frame["is_recommended"].map(lambda value: "Yes" if bool(value) else "")
    st.dataframe(frame[["rank", "technique", "hybrid_score", "catboost_probability", "engineering_score", "engineering_status", "Recommended"]].rename(columns={"rank": "Rank", "technique": "EOR Technique", "hybrid_score": "Hybrid Score", "catboost_probability": "CatBoost", "engineering_score": "Engineering", "engineering_status": "Engineering Status"}), use_container_width=True, hide_index=True)


def _render_report_card(card: Dict[str, Any]) -> None:
    run = card["run"]
    reference = card["reference"]
    inputs = _parse_json(run.get("input_payload")) or {}
    evidence = _parse_json(run.get("evidence_summary")) or {}
    assumptions = _parse_json(run.get("assumptions")) or {}

    section_title(f"Screening Report Card · {reference}", "Exact submitted inputs plus the independent Engineering, CatBoost and Hybrid decision records captured for this run.")
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
    engineering_tab, ml_tab, hybrid_tab, trace_tab = st.tabs(["Engineering", "CatBoost", "Hybrid Fusion", "Decision Trace"])
    with engineering_tab:
        _render_engineering(card)
    with ml_tab:
        _render_ml(card)
    with hybrid_tab:
        _render_hybrid(card)
    with trace_tab:
        st.code("User Inputs → Excel Engineering Gate → CatBoost → Decision Fusion → Report Card")
        trace = _parse_json(run.get("rule_trace"))
        if trace:
            with st.expander("Engineering rule trace", expanded=False):
                st.json(trace)
        with st.expander("Recorded assumptions / provenance", expanded=False):
            st.json({"assumptions": assumptions, "evidence": evidence})
        st.caption(f"Model version: {run.get('model_version') or '—'} · Workbook version: {run.get('workbook_version') or '—'} · Rule version: {run.get('rule_version') or '—'}")


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
        delta = float(rv) - float(lv) if isinstance(lv, (int, float)) and isinstance(rv, (int, float)) else None
        rows.append({"Parameter": key.replace("_", " ").title(), left_ref: lv if lv not in (None, "") else "—", right_ref: rv if rv not in (None, "") else "—", "Δ (Right − Left)": _fmt_number(delta, 2) if delta is not None else "—"})
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    summary = pd.DataFrame([
        {"Run": left_ref, "Type": left["run"].get("recommendation_mode") or "—", "Recommendation": left["run"].get("recommended_technique") or "—", "Score": left["run"].get("recommendation_score")},
        {"Run": right_ref, "Type": right["run"].get("recommendation_mode") or "—", "Recommendation": right["run"].get("recommended_technique") or "—", "Score": right["run"].get("recommendation_score")},
    ])
    st.dataframe(summary, use_container_width=True, hide_index=True)


def render() -> None:
    """Render Historical EOR studies first, then durable screening records."""
    try:
        records = list_report_cards(days=3650)
    except Exception as exc:
        records = []
        st.warning(f"Screening run history is unavailable: {exc}")

    st.title("Historical EOR")
    st.caption("Past EOR study evidence and saved EOR Atlas screening decisions.")
    _render_historical_eor_reference_section()

    st.markdown("<div class='atlas-divider'></div>", unsafe_allow_html=True)
    section_title("EOR Screening Run Records", "Durable report cards generated by submitted Engineering and Hybrid screening runs.")

    engineering_count = sum(record.get("recommendation_mode") == "ENGINEERING" for record in records)
    hybrid_count = sum(record.get("recommendation_mode") == "HYBRID" for record in records)
    kpi_cards([
        ("Saved Runs", len(records), "Persisted report cards"),
        ("Engineering Runs", engineering_count, "Excel Gate submissions"),
        ("Hybrid Runs", hybrid_count, "Excel + CatBoost + Fusion"),
        ("Audit Source", "SQLite", "Persistent decision history"),
    ])

    register_tab, card_tab, compare_tab = st.tabs(["Run Register", "Screening Report Card", "Compare Runs"])
    with register_tab:
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
        options = {_reference_for_record(row): int(row["id"]) for row in records}
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
