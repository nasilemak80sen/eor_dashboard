"""Hybrid Intelligence page."""
from __future__ import annotations
import streamlit as st
from ui.components import insight_cards, reset_button, section_title, kpi_cards
from ui.decision import data_quality, decision_trace, next_steps, view_mode, why_why_not, decision_hero


def render(services: dict) -> None:
    import hybrid_app as _hybrid
    insight_cards([
        ("01 · GATE", "Engineering anchor", "Hard engineering failures remain excluded before ML contributes to the recommendation."),
        ("02 · MODEL", "CatBoost signal", "The active model contributes a data-driven technique probability after the form is submitted."),
        ("03 · FUSION", "Decision ranking", "Engineering and model signals are reconciled into an interpretable ranked recommendation."),
    ])
    st.markdown("<div class='atlas-divider'></div>", unsafe_allow_html=True)
    result=st.session_state.get("eor_intelligence_result"); inputs_state=st.session_state.get("intel_last_inputs") or {}
    kpi_cards([("Workflow","Result available" if result else "Awaiting run","Current page state"),("Engineering","Excel Gate","Deterministic anchor"),("Model","CatBoost","Data-driven signal"),("Fusion","65 / 35","ML / engineering weighting")])
    input_tab,decision_tab=st.tabs(["Reservoir Inputs","Hybrid Decision"])
    with input_tab:
        action_col,_=st.columns([1,4])
        with action_col:reset_button("↺ Reset inputs",prefixes="intel_",result_keys=("eor_intelligence_result","intel_last_inputs"),key="intelligence_reset_inputs")
        section_title("Reservoir Context","Complete the same v3 schema used by Engineering Screening. No decision calculation runs while fields are edited.")
        with st.form("hybrid_reservoir_form",clear_on_submit=False):
            inputs,formation=_hybrid.render_eor_input_form("intel")
            st.caption("Complete the reservoir context, then submit once to run Excel Gate → CatBoost → Decision Fusion.")
            submitted=st.form_submit_button("🧠 Run Hybrid Intelligence",type="primary",use_container_width=True)
        if submitted:
            try:
                with st.status("Running Hybrid Intelligence…",expanded=True) as run_status:
                    st.write("Executing Engineering Gate.")
                    result=_hybrid.run_eor_intelligence(services,inputs,formation)
                    st.write("CatBoost inference and Decision Fusion completed.")
                    st.session_state["eor_intelligence_result"]=result; st.session_state["intel_last_inputs"]=inputs.copy(); st.session_state["intel_last_formation"]=formation
                    run_status.update(label="Hybrid Intelligence complete",state="complete")
                st.toast("Hybrid recommendation updated",icon="🧠")
            except Exception as exc:
                st.error(f"Hybrid intelligence could not be completed: {exc}")
    result=st.session_state.get("eor_intelligence_result")
    with decision_tab:
        if not result:st.info("No hybrid result yet. Complete Reservoir Inputs and submit Hybrid Intelligence.");return
        mode=view_mode("intelligence_view_mode"); hybrid=result.get("hybrid",{}) or {}; recommendation=hybrid.get("recommendation"); ranking=hybrid.get("ranking",[]) or []; quality="HIGH" if result.get("ml_available") and inputs_state else ("MEDIUM" if inputs_state else "LIMITED")
        decision_hero(recommendation,quality)
        if mode=="Leadership":
            kpi_cards([("Recommendation",recommendation.get("EOR Technique","—") if recommendation else "—","Top hybrid outcome"),("Hybrid score",f"{float(recommendation.get('Hybrid Score',0)):.1%}" if recommendation else "—","Combined decision signal"),("Gate",recommendation.get("Engineering Status","—") if recommendation else "—","Engineering anchor"),("ML","Available" if result.get("ml_available") else "Unavailable","CatBoost runtime state")])
            with st.expander("Why / Why Not",expanded=True):why_why_not(ranking)
            with st.expander("Decision Trace",expanded=False):decision_trace(result.get("screening"),result.get("ml_top3"),ranking)
            with st.expander("Recommended Next Steps",expanded=True):next_steps(recommendation)
        else:
            with st.expander("Decision Trace",expanded=True):decision_trace(result.get("screening"),result.get("ml_top3"),ranking)
            with st.expander("Why / Why Not",expanded=True):why_why_not(ranking)
            with st.expander("Data & Assumption Quality",expanded=False):data_quality(inputs_state)
            with st.expander("ScreenTool v3 Context",expanded=False):st.json(hybrid.get("opportunity_context",{}) or {})
            with st.expander("CatBoost Model Information",expanded=False):st.json(result["model_info"]) if result.get("model_info") else st.info("No CatBoost model information is available for this run.")
            with st.expander("Decision Fusion Configuration",expanded=False):st.json(hybrid.get("weights",{}))
            if result.get("ml_error"):st.warning(f"CatBoost inference unavailable: {result['ml_error']}")
            with st.expander("Recommended Next Steps",expanded=True):next_steps(recommendation)
