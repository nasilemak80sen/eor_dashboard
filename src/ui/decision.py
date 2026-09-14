"""Decision-centric UI primitives for EOR Atlas."""
from __future__ import annotations
from html import escape
from typing import Any, Iterable
import pandas as pd
import streamlit as st


def fmt_score(value: Any) -> str:
    try:
        return f"{float(value):.1%}"
    except (TypeError, ValueError):
        return "—"


def status_class(status: Any) -> str:
    value = str(status or "").upper()
    return {"PASS": "pass", "CONDITIONAL": "conditional", "FAIL": "fail"}.get(value, "neutral")


def decision_hero(recommendation: dict[str, Any] | None, quality: str = "Decision available") -> None:
    if not recommendation:
        st.warning("No eligible technique was produced by the current decision path.")
        return
    technique = recommendation.get("EOR Technique", "N/A")
    status = recommendation.get("Engineering Status", "—")
    st.markdown(
        f'''<div class="atlas-decision-hero">
        <div class="atlas-decision-kicker">FINAL DECISION</div>
        <div class="atlas-decision-title">Recommended EOR Technique</div>
        <div class="atlas-decision-technique">{escape(str(technique))}</div>
        <div class="atlas-decision-subtitle">Engineering Gate → CatBoost → Decision Fusion</div>
        <div class="atlas-decision-score-row">
        <div><span>HYBRID</span><strong>{fmt_score(recommendation.get("Hybrid Score"))}</strong></div>
        <div><span>CATBOOST</span><strong>{fmt_score(recommendation.get("CatBoost Probability"))}</strong></div>
        <div><span>ENGINEERING</span><strong>{fmt_score(recommendation.get("Engineering Score"))}</strong></div>
        <div><span>GATE</span><strong class="atlas-inline-status {status_class(status)}">{escape(str(status))}</strong></div>
        <div><span>QUALITY</span><strong>{escape(quality)}</strong></div>
        </div></div>''', unsafe_allow_html=True
    )


def decision_trace(screening: dict[str, Any] | None, ml_top3: Iterable[Any] | None, ranking: Iterable[dict[str, Any]] | None) -> None:
    screening = screening or {}
    ranking = list(ranking or [])
    ml_top3 = list(ml_top3 or [])
    st.markdown("### Decision Trace")
    st.caption("Production decision chain shown as an auditable sequence.")
    stages = [
        ("01", "INPUT", "Reservoir context", "Submitted reservoir properties"),
        ("02", "ENGINEERING GATE", "Excel screening", "Deterministic feasibility"),
        ("03", "MODEL", "CatBoost", f"{len(ml_top3)} top model signals" if ml_top3 else "Model signal evaluated during fusion"),
        ("04", "FUSION", "Decision Fusion", f"{len(ranking)} ranked techniques" if ranking else "Engineering + model reconciliation"),
        ("05", "FINAL", "Hybrid ranking", str(ranking[0].get("EOR Technique")) if ranking else "Awaiting recommendation"),
    ]
    for number, label, title, meta in stages:
        st.markdown(
            f'''<div class="atlas-trace-step"><div class="atlas-trace-number">{number}</div><div><div class="atlas-trace-label">{escape(label)}</div><div class="atlas-trace-title">{escape(title)}</div><div class="atlas-trace-meta">{escape(meta)}</div></div></div>''',
            unsafe_allow_html=True,
        )


def why_why_not(ranking: Iterable[dict[str, Any]], max_items: int = 3) -> None:
    rows = list(ranking or [])[:max_items]
    if not rows:
        return
    st.markdown("### Why / Why Not")
    tabs = st.tabs([f"#{i + 1} {row.get('EOR Technique', 'Technique')}" for i, row in enumerate(rows)])
    for i, (tab, row) in enumerate(zip(tabs, rows)):
        with tab:
            cols = st.columns(4)
            cols[0].metric("Engineering", fmt_score(row.get("Engineering Score")))
            cols[1].metric("CatBoost", fmt_score(row.get("CatBoost Probability")))
            cols[2].metric("Hybrid", fmt_score(row.get("Hybrid Score")))
            cols[3].metric("Gate", row.get("Engineering Status", "—"))
            status = str(row.get("Engineering Status", "")).upper()
            if status == "PASS":
                st.success("Engineering gate is satisfied under the current criteria.")
            elif status == "CONDITIONAL":
                st.warning("Technically plausible, but a conditional engineering penalty applies.")
            else:
                st.error("Engineering gate is not satisfied under the current criteria.")
            st.info("Selected because it has the strongest combined hybrid position." if i == 0 else "Lower than the leading recommendation in the current hybrid ranking.")


def data_quality(values: dict[str, Any] | None) -> str:
    values = values or {}
    core = ("depth_ft", "reservoir_pressure", "temperature_c", "visc_cp", "api", "perm_md", "porosity_pct", "so_pct")
    count = sum(values.get(key) is not None for key in core)
    quality = "HIGH" if count == len(core) else ("MEDIUM" if count >= 6 else "LIMITED")
    st.markdown("### Data & Assumption Quality")
    st.caption("Known inputs are explicit; unavailable optional inputs are not fabricated.")
    rows = []
    for label, key in [("Depth", "depth_ft"), ("Pressure", "reservoir_pressure"), ("Temperature", "temperature_c"), ("Viscosity", "visc_cp"), ("API", "api"), ("Permeability", "perm_md"), ("Porosity", "porosity_pct"), ("Current So", "so_pct")]:
        rows.append({"Parameter": label, "State": "Provided" if values.get(key) is not None else "Unavailable"})
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    return quality


def next_steps(recommendation: dict[str, Any] | None) -> None:
    technique = str((recommendation or {}).get("EOR Technique", "the selected technique"))
    status = str((recommendation or {}).get("Engineering Status", "")).upper()
    actions = ["Validate the highest-impact engineering assumptions before concept selection.", f"Review technical evidence and constraints specific to {technique}."]
    if status == "CONDITIONAL":
        actions.insert(1, "Resolve the conditional engineering criteria before advancing the technique.")
    elif status == "FAIL":
        actions.insert(1, "Do not advance the technique without addressing the failed engineering gate.")
    else:
        actions.insert(1, "Progress to laboratory, subsurface and facility feasibility validation as appropriate.")
    st.markdown("### Recommended Next Steps")
    for i, action in enumerate(actions, 1):
        st.markdown(f'<div class="atlas-next-step"><span>{i}</span><div>{escape(action)}</div></div>', unsafe_allow_html=True)


def view_mode(key: str) -> str:
    return st.radio("View", ["Engineering", "Leadership"], horizontal=True, key=key)
