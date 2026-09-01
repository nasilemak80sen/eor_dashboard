"""
EOR Atlas – Enhanced Oil Recovery Screening & Decision Support Platform
Modular, production-ready application using Streamlit.

Phase 0-2 Implementation:
- Modular architecture (no monolithic app.py)
- Engineering rule engine for eligibility screening  
- Fuzzy logic + ML inference
- Decision synthesis engine
"""

import streamlit as st
import pandas as pd
import numpy as np
import json
from pathlib import Path

try:
    import pydeck as pdk
except Exception:  # pragma: no cover - optional dependency
    pdk = None

# Import modular services
from config.settings import settings
from utils.logging_config import logger
from utils.validators import InputValidator, ValidationStatus
from domain.fuzzy_engine import FuzzyEngine
from domain.rule_engine import RuleEngine, EligibilityStatus
from domain.screening_engine import ScreeningEngine
from ml.model_service import ModelService
from data.repositories import EnvelopeRepository, WorkbookRepository
from data.queries import RepositoryFactory

# =============================================================================
# STREAMLIT CONFIGURATION
# =============================================================================
st.set_page_config(
    page_title=settings.ui_config["page_title"],
    page_icon=settings.ui_config["page_icon"],
    layout=settings.ui_config["layout"],
)

st.markdown(
    """
    <style>
    .block-container { padding-top: 1.2rem; padding-bottom: 2rem; }
    .stAlert > div { border-radius: 12px; }
    .metric-card { background: linear-gradient(135deg, #0f172a, #1e293b); 
                   padding: 1rem 1.2rem; border-radius: 14px; color: white; }
    .eligibility-pass { color: green; font-weight: bold; }
    .eligibility-conditional { color: orange; font-weight: bold; }
    .eligibility-fail { color: red; font-weight: bold; }
    </style>
    """,
    unsafe_allow_html=True,
)

# =============================================================================
# INITIALIZE SERVICES (cached)
# =============================================================================

@st.cache_resource
def initialize_services():
    """Initialize all application services."""
    logger.info("Initializing services...")
    
    # Load data
    try:
        env, techs_all = EnvelopeRepository.load_envelopes()
        workbook_sheets = WorkbookRepository.load_workbook()
    except Exception as e:
        logger.error(f"Failed to load data: {e}")
        st.error(f"Failed to load data: {e}")
        return None
    
    # Initialize engines
    fuzzy_engine = FuzzyEngine(env, alpha=settings.fuzzy_alpha)
    rule_engine = RuleEngine()
    
    # Load ML model
    model_service = ModelService()
    if not model_service.load():
        logger.warning("ML model failed to load, proceeding without ML")
    
    # Create screening engine
    screening_engine = ScreeningEngine(fuzzy_engine, rule_engine, model_service)
    
    return {
        "screening_engine": screening_engine,
        "fuzzy_engine": fuzzy_engine,
        "rule_engine": rule_engine,
        "model_service": model_service,
        "env": env,
        "techs_all": techs_all,
        "workbook_sheets": workbook_sheets,
    }


# =============================================================================
# UI COMPONENTS
# =============================================================================

def render_database_summary_section():
    """Render professional database and screening overview cards."""
    try:
        recent_runs = RepositoryFactory.screening_repo().get_recent(days=30)
    except Exception as exc:
        logger.warning(f"Database summary unavailable: {exc}")
        recent_runs = []

    st.subheader("📊 Platform Overview")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Recent Runs", len(recent_runs) if recent_runs else 0)
    col2.metric("Model Status", "Ready" if settings.validate_paths().get("model") else "Missing")
    col3.metric("Workbook", "Loaded" if settings.validate_paths().get("workbook") else "Missing")
    col4.metric("Environment", settings.environment.upper())

    if recent_runs:
        table = []
        for run in recent_runs[:5]:
            table.append({
                "Time": run.timestamp.strftime("%Y-%m-%d %H:%M") if run.timestamp else "N/A",
                "Formation": run.formation,
                "Recommendation": run.recommended_technique or "N/A",
                "Score": round(float(run.recommendation_score), 3) if run.recommendation_score is not None else 0.0,
            })
        st.dataframe(pd.DataFrame(table), width="stretch")


def render_executive_kpi_row():
    """Render executive summary cards for a polished operational dashboard."""
    try:
        recent_runs = RepositoryFactory.screening_repo().get_recent(days=30)
    except Exception:
        recent_runs = []

    path_status = settings.validate_paths()
    model_ready = bool(path_status.get("model"))
    workbook_ready = bool(path_status.get("workbook"))
    active_runs = len(recent_runs) if recent_runs else 0

    st.subheader("Executive KPI Snapshot")
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)

    with kpi1:
        st.markdown(
            f"<div class='exec-kpi-card'><div class='exec-kpi-label'>Recent Runs</div><div class='exec-kpi-value'>{active_runs}</div></div>",
            unsafe_allow_html=True,
        )
    with kpi2:
        st.markdown(
            f"<div class='exec-kpi-card'><div class='exec-kpi-label'>Model Status</div><div class='exec-kpi-value'>{'Ready' if model_ready else 'Missing'}</div></div>",
            unsafe_allow_html=True,
        )
    with kpi3:
        st.markdown(
            f"<div class='exec-kpi-card'><div class='exec-kpi-label'>Workbook</div><div class='exec-kpi-value'>{'Loaded' if workbook_ready else 'Missing'}</div></div>",
            unsafe_allow_html=True,
        )
    with kpi4:
        st.markdown(
            f"<div class='exec-kpi-card'><div class='exec-kpi-label'>Environment</div><div class='exec-kpi-value'>{settings.environment.upper()}</div></div>",
            unsafe_allow_html=True,
        )


def render_model_registry_section():
    """Render model registry and version history for production tracking."""
    st.subheader("🧠 Model Registry & Version History")

    try:
        versions = RepositoryFactory.model_version_repo().list_versions()
    except Exception as exc:
        logger.warning(f"Model registry unavailable: {exc}")
        versions = []

    if not versions:
        st.info("No model versions are registered yet. Run a training job to populate the registry.")
        return

    rows = []
    for version in versions:
        rows.append({
            "Version": version.version,
            "Algorithm": version.algorithm,
            "Framework": version.framework,
            "Accuracy": round(float(version.test_accuracy), 4) if version.test_accuracy is not None else None,
            "Weighted F1": round(float(version.test_weighted_f1), 4) if version.test_weighted_f1 is not None else None,
            "Training Date": version.training_date.strftime("%Y-%m-%d %H:%M") if version.training_date else "N/A",
            "Active": "Yes" if version.is_active else "No",
        })

    st.dataframe(pd.DataFrame(rows), width="stretch")


def render_saved_run_detail_section():
    """Display saved screening detail and allow side-by-side comparison of historical runs."""
    st.subheader("🧾 Saved Run Detail & Comparison")

    try:
        history = RepositoryFactory.screening_repo().get_recent(days=365)
    except Exception as exc:
        logger.warning(f"Historical screening data unavailable: {exc}")
        history = []

    if not history:
        st.info("No saved screening runs are available yet. Run a screening to populate the history audit trail.")
        return

    history_df = pd.DataFrame([
        {
            "Run ID": run.id,
            "Timestamp": run.timestamp.strftime("%Y-%m-%d %H:%M") if run.timestamp else "N/A",
            "Formation": run.formation,
            "Recommendation": run.recommended_technique or "N/A",
            "Status": run.recommendation_status or "N/A",
            "Score": round(float(run.recommendation_score), 3) if run.recommendation_score is not None else 0.0,
        }
        for run in history
    ])

    st.dataframe(history_df, width="stretch")

    run_a_id = st.selectbox("Select a saved run to reopen", [run.id for run in history], index=0)
    selected_run = next((run for run in history if run.id == run_a_id), history[0])

    st.markdown("### Reopened assessment")
    detail_cols = st.columns(2)
    with detail_cols[0]:
        st.write(f"**Run ID:** {selected_run.id}")
        st.write(f"**Timestamp:** {selected_run.timestamp.strftime('%Y-%m-%d %H:%M') if selected_run.timestamp else 'N/A'}")
        st.write(f"**Formation:** {selected_run.formation}")
        st.write(f"**Recommendation:** {selected_run.recommended_technique or 'N/A'}")
    with detail_cols[1]:
        st.write(f"**Final Status:** {selected_run.recommendation_status or 'N/A'}")
        st.write(f"**Score:** {selected_run.recommendation_score if selected_run.recommendation_score is not None else 'N/A'}")
        st.write(f"**Model Version:** {selected_run.model_version or 'N/A'}")
        st.write(f"**Data Readiness:** {selected_run.data_readiness_pct or 'N/A'}%")

    input_payload = selected_run.input_payload or {}
    if input_payload:
        st.write("**Exact input values:**")
        st.dataframe(pd.DataFrame([input_payload]), width="stretch")
    else:
        st.info("No exact input payload was stored for this historical run.")

    rule_trace = selected_run.rule_trace or {}
    if rule_trace:
        st.write("**Structured rule trace:**")
        st.json(rule_trace)
    else:
        st.info("No structured rule trace was recorded for this historical run.")

    assumptions = selected_run.assumptions or {}
    if assumptions:
        st.write("**Recorded assumptions:**")
        st.json(assumptions)

    evidence_summary = selected_run.evidence_summary or {}
    if evidence_summary:
        st.write("**Evidence summary:**")
        st.json(evidence_summary)

    st.download_button(
        label="Download saved assessment JSON",
        data=json.dumps({
            "run_id": selected_run.id,
            "timestamp": selected_run.timestamp.isoformat() if selected_run.timestamp else None,
            "formation": selected_run.formation,
            "recommendation": selected_run.recommended_technique,
            "status": selected_run.recommendation_status,
            "score": selected_run.recommendation_score,
            "inputs": input_payload,
            "rule_trace": rule_trace,
            "assumptions": assumptions,
            "evidence_summary": evidence_summary,
        }, indent=2),
        file_name=f"eor_run_{selected_run.id}.json",
        mime="application/json",
    )

    st.markdown("### Compare two saved runs")
    if len(history) >= 2:
        compare_ids = [run.id for run in history]
        run_b_id = st.selectbox("Select the second run for comparison", compare_ids, index=min(1, len(compare_ids)-1))
        if run_b_id == run_a_id:
            st.caption("Choose a different run for the comparison to be meaningful.")
        else:
            comparison = RepositoryFactory.screening_repo().compare_runs(run_a_id, run_b_id)
            if "error" in comparison:
                st.warning(comparison["error"])
            else:
                left = comparison["left"]
                right = comparison["right"]
                delta = comparison["delta_score"]
                compare_cols = st.columns(2)
                with compare_cols[0]:
                    st.write("**Left run**")
                    st.json(left)
                with compare_cols[1]:
                    st.write("**Right run**")
                    st.json(right)
                st.metric("Score Delta", f"{delta:+.3f}")
                st.write("**What changed:**")
                st.write(f"- Recommendation changed from {left['recommendation']} to {right['recommendation']}")
                st.write(f"- Status changed from {left['status']} to {right['status']}")
                st.write(f"- Score delta: {delta:+.3f}")
    else:
        st.info("At least two saved runs are needed for comparison.")


def render_sidebar_status():
    """Render the status summary in the sidebar for a cleaner production view."""
    path_status = settings.validate_paths()
    model_ready = bool(path_status.get("model"))
    workbook_ready = bool(path_status.get("workbook"))
    config_ready = bool(path_status.get("config"))

    st.sidebar.header("Operational Status")
    st.sidebar.markdown(
        f"""
        <div class='sidebar-status-box'>
            <div class='status-row'><span>Model</span><span class='status-pill {'ready' if model_ready else 'warn'}'>{'Ready' if model_ready else 'Missing'}</span></div>
            <div class='status-row'><span>Workbook</span><span class='status-pill {'ready' if workbook_ready else 'warn'}'>{'Loaded' if workbook_ready else 'Missing'}</span></div>
            <div class='status-row'><span>Config</span><span class='status-pill {'ready' if config_ready else 'warn'}'>{'Valid' if config_ready else 'Check'}</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.sidebar.caption("Decision stack")
    st.sidebar.write("• Rule engine")
    st.sidebar.write("• Fuzzy logic")
    st.sidebar.write("• Neural network")
    st.sidebar.write("• Decision synthesis")


def render_geospatial_map_section():
    """Render a professional geospatial monitoring section similar to the provided pydeck example."""
    st.subheader("🌍 Geospatial Monitoring")
    st.caption("Reservoir field and opportunity footprint overview")

    geo_data = pd.DataFrame(
        np.random.randn(500, 2) / [70, 90] + [37.76, -122.4],
        columns=["lat", "lon"],
    )

    if pdk is not None:
        st.pydeck_chart(
            pdk.Deck(
                map_style="mapbox://styles/mapbox/light-v9",
                initial_view_state=pdk.ViewState(
                    latitude=37.76,
                    longitude=-122.4,
                    zoom=8,
                    pitch=30,
                    bearing=0,
                ),
                layers=[
                    pdk.Layer(
                        "HexagonLayer",
                        data=geo_data,
                        get_position="[lon, lat]",
                        radius=1500,
                        elevation_scale=4,
                        elevation_range=[0, 1000],
                        extruded=True,
                        pickable=True,
                        get_fill_color=[255, 125, 64, 180],
                        get_line_color=[255, 125, 64, 180],
                    ),
                    pdk.Layer(
                        "ScatterplotLayer",
                        data=geo_data,
                        get_position="[lon, lat]",
                        get_color=[38, 166, 154, 180],
                        get_radius=150,
                        pickable=True,
                    ),
                ],
            )
        )
    else:
        st.map(geo_data[["lat", "lon"]])

    with st.expander("Field metadata"):
        st.markdown(
            """
            - Assessment region: Offshore West Basin
            - Reservoir class: Mature sandstone / carbonate transition
            - Monitoring mode: Live screening + historical analog review
            - Spatial view: Operational footprint and candidate clustering
            """
        )


def display_data_quality_section(data_quality: dict):
    """Display data quality assessment."""
    status = data_quality.get("status", "Unknown")
    readiness = data_quality.get("readiness_percentage", 0)
    
    col1, col2, col3, col4 = st.columns(4)
    
    col1.metric(
        "Data Status",
        f"{readiness:.0f}%",
        f"of {data_quality['required_parameters']} required",
    )
    col2.metric("Valid Parameters", f"{data_quality['valid_parameters']}/{data_quality['required_parameters']}")
    col3.metric("Outliers Detected", len(data_quality.get("outliers", [])))
    col4.metric("Overall Status", status)


def display_eligibility_section(eligibility: dict):
    """Display engineering eligibility screening."""
    st.subheader("🏗️ Engineering Eligibility Screening")
    
    # Summary counts
    pass_count = sum(
        1
        for status, _ in eligibility.values()
        if status == EligibilityStatus.PASS
    )
    conditional_count = sum(
        1
        for status, _ in eligibility.values()
        if status == EligibilityStatus.CONDITIONAL
    )
    fail_count = sum(
        1
        for status, _ in eligibility.values()
        if status == EligibilityStatus.FAIL
    )
    
    col1, col2, col3 = st.columns(3)
    col1.metric("🟢 PASS", pass_count)
    col2.metric("🟡 CONDITIONAL", conditional_count)
    col3.metric("🔴 FAIL", fail_count)
    
    st.write("---")
    
    # Detailed results
    for technique, (status, results) in sorted(eligibility.items()):
        with st.expander(f"{status} — {technique}", expanded=(status == EligibilityStatus.PASS)):
            
            # Criteria table
            criteria_data = []
            for result in results:
                criteria_data.append({
                    "Criterion": result["criterion"],
                    "Status": "✓" if result["passes"] else "✗",
                    "Value": f"{result['value']:.1f}" if result["value"] else "N/A",
                    "Explanation": result["explanation"],
                    "Impact": result["impact"],
                })
            
            df_criteria = pd.DataFrame(criteria_data)
            st.dataframe(df_criteria, width="stretch")


def display_fuzzy_section(fuzzy_scores: dict, fuzzy_explanations: dict):
    """Display fuzzy suitability evaluation."""
    st.subheader("⚖️ Fuzzy Suitability Scores")
    
    # Bar chart of all scores
    fuzzy_series = pd.Series(fuzzy_scores).sort_values(ascending=False)
    st.bar_chart(fuzzy_series)
    
    st.write("---")
    
    # Detailed explanation for top techniques
    top_techniques = fuzzy_series.head(3).index.tolist()
    
    for idx, technique in enumerate(top_techniques):
        col1, col2 = st.columns([1.5, 0.5])
        
        with col1:
            with st.expander(f"📊 {technique} – Fuzzy Analysis", expanded=(idx == 0)):
                rows, overall_score = fuzzy_explanations[technique]
                
                if not rows:
                    st.info("No fuzzy envelope found for this technique-formation pair.")
                else:
                    # Membership table
                    df_members = pd.DataFrame(rows)
                    st.dataframe(df_members, width="stretch")
                    
                    # Membership chart
                    st.bar_chart(
                        df_members.set_index("Variable")["Membership"],
                    )
                    st.metric("Mean Fuzzy Membership", f"{overall_score:.3f}")
        
        with col2:
            st.metric(f"{technique} Score", f"{fuzzy_scores[technique]:.3f}")


def display_ml_section(ml_top3: list, ml_probabilities: dict):
    """Display ML inference results."""
    if not ml_top3:
        st.info("ML model not available or inference failed.")
        return
    
    st.subheader("🤖 Neural Network Inference")
    
    # Top 3 predictions
    df_top3 = pd.DataFrame(ml_top3, columns=["Technique", "NN Probability"])
    st.dataframe(df_top3, width="stretch")
    
    # All probabilities chart
    ml_series = pd.Series(ml_probabilities).sort_values(ascending=False)
    st.bar_chart(ml_series)


def display_recommendation_section(result):
    """Display final recommendation and reasoning."""
    st.subheader("✅ Final Recommendation")
    
    # Large recommendation card
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown(f"### {result.recommendation}")
        st.markdown(f"**Status:** {result.recommendation_status}")
    
    with col2:
        st.metric("Recommendation Score", f"{result.recommendation_score:.3f}")
    
    st.write("---")
    
    # Reasoning details
    st.write("**Decision Reasoning:**")
    reasoning = result.reasoning
    
    reason_cols = st.columns(2)
    with reason_cols[0]:
        if "pass_techniques" in reasoning:
            st.markdown(f"**Eligible (PASS):** {', '.join(reasoning['pass_techniques']) or 'None'}")
        if "conditional_techniques" in reasoning:
            st.markdown(f"**Conditional:** {', '.join(reasoning['conditional_techniques']) or 'None'}")
    
    with reason_cols[1]:
        if "fuzzy_score" in reasoning:
            st.metric("Fuzzy Score", f"{reasoning['fuzzy_score']:.3f}")
        if "ml_score" in reasoning:
            st.metric("ML Score", f"{reasoning['ml_score']:.3f}")
    
    st.info(f"**Mode:** {result.mode} | **Strategy:** {reasoning.get('strategy', 'N/A')}")


def render_executive_overview_section():
    """Executive overview aligned to the PDF portfolio dashboard."""
    st.header("🏠 Executive Overview")

    portfolio = pd.DataFrame({
        "Metric": ["Fields", "Reservoirs", "EOR Families", "Historical Studies", "RF Gap (MMstb)", "Candidates"],
        "Value": [41, 600, 9, 128, 1.31, 18],
    })
    metric_cols = st.columns(6)
    for i, (metric, value) in enumerate(zip(portfolio["Metric"], portfolio["Value"])):
        with metric_cols[i]:
            st.markdown(
                f"<div class='exec-kpi-card'><div class='exec-kpi-label'>{metric}</div><div class='exec-kpi-value'>{value}</div></div>",
                unsafe_allow_html=True,
            )

    map_df = pd.DataFrame(
        {
            "Field": ["Angsi", "Barton", "Dulang", "Tapis", "Baram"],
            "Latitude": [4.3, 4.1, 3.9, 3.8, 5.0],
            "Longitude": [103.1, 103.3, 103.6, 103.2, 112.0],
            "EOR_Status": ["Candidate", "Multiple", "Historical", "Candidate", "Historical"],
            "RF_Gap": [120, 95, 80, 66, 105],
        }
    )

    st.subheader("Field Opportunity Map")
    if pdk is not None:
        st.pydeck_chart(
            pdk.Deck(
                map_style="mapbox://styles/mapbox/light-v9",
                initial_view_state=pdk.ViewState(latitude=4.3, longitude=103.4, zoom=5, pitch=30),
                layers=[
                    pdk.Layer(
                        "ScatterplotLayer",
                        data=map_df,
                        get_position="[Longitude, Latitude]",
                        get_color=[255, 120, 60, 200],
                        get_radius="RF_Gap",
                        pickable=True,
                    )
                ],
            )
        )
    else:
        st.map(map_df[["Latitude", "Longitude"]])

    st.subheader("Portfolio Summary Table")
    st.dataframe(map_df, width="stretch")


def render_eor_screening_tab(services):
    """Decision-support screening interface aligned to the PDF workflow."""
    st.header("🔍 EOR Screening")
    st.write("Reservoir input, method screening, rationale, and recommendation engine.")

    with st.expander("📝 Reservoir Characteristics", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            formation = st.selectbox("Formation Category", settings.ui_config["formation_categories"], index=0)
            depth_ft = st.number_input("Depth (ft)", min_value=0.0, value=5000.0, step=50.0)
            porosity_pct = st.number_input("Porosity (%)", min_value=0.0, max_value=100.0, value=20.0, step=0.5)
        with col2:
            perm_md = st.number_input("Permeability (mD)", min_value=0.0, value=100.0, step=10.0)
            api = st.number_input("Oil Gravity (°API)", min_value=0.0, max_value=80.0, value=35.0, step=0.5)
            visc_cp = st.number_input("Viscosity (cp)", min_value=0.0, value=2.0, step=0.1)
        with col3:
            so_pct = st.number_input("Oil Saturation (%)", min_value=0.0, max_value=100.0, value=55.0, step=1.0)
            reservoir_pressure = st.number_input("Reservoir Pressure (psi)", min_value=0.0, value=2500.0, step=50.0)
            temperature_c = st.number_input("Temperature (°C)", min_value=0.0, value=95.0, step=5.0)

    if st.button("🚀 Run Screening", type="primary", width="stretch"):
        values = {
            "depth_ft": depth_ft,
            "porosity_pct": porosity_pct,
            "perm_md": perm_md,
            "api": api,
            "visc_cp": visc_cp,
            "so_pct": so_pct,
            "reservoir_pressure": reservoir_pressure,
            "temperature_c": temperature_c,
        }
        try:
            with st.spinner("Screening in progress..."):
                result = services["screening_engine"].screen(values, formation, services["techs_all"])
            st.success("✅ Screening complete")
            display_data_quality_section(result.data_quality)
            st.write("---")
            display_eligibility_section(result.eligibility)
            st.write("---")
            display_fuzzy_section(result.fuzzy_scores, result.fuzzy_explanations)
            st.write("---")
            if services["model_service"].is_loaded():
                display_ml_section(result.ml_top3, result.ml_probabilities)
                st.write("---")
            display_recommendation_section(result)
        except Exception as exc:
            logger.error(f"Screening failed: {exc}")
            st.error(f"Screening failed: {exc}")


def render_field_candidates_section():
    """Field and reservoir candidate screening aligned to the PDF candidate plots."""
    st.header("🗺️ Field / Reservoir Candidates")

    candidate_df = pd.DataFrame(
        {
            "Field": ["Angsi", "Dulang", "Barton", "Baram", "Tapis", "Penara"],
            "Reservoir": ["A12", "E14", "B7", "E10", "N12", "P1"],
            "Temperature_C": [85, 93, 72, 108, 80, 66],
            "EUR_MMstb": [68, 52, 41, 88, 54, 34],
            "RF_Gap": [20, 18, 15, 24, 17, 12],
            "Permeability_mD": [120, 160, 80, 180, 110, 90],
            "Method": ["CO2 WAG", "Polymer", "ASP", "CO2 WAG", "Polymer", "Steam"],
        }
    )

    st.subheader("Candidate Reservoir Scatter")
    st.bar_chart(candidate_df.set_index("Field")["EUR_MMstb"])

    st.subheader("Opportunity Rank")
    st.bar_chart(candidate_df.set_index("Field")["RF_Gap"])

    st.dataframe(candidate_df, width="stretch")


def render_fluid_fluid_section():
    """Fluid–fluid CEOR section aligned to the PDF design."""
    st.header("🧪 CEOR — Fluid / Fluid")

    rheology_df = pd.DataFrame(
        {
            "Shear_Rate": [10, 30, 50, 100, 200],
            "Polymer_A": [120, 90, 75, 58, 44],
            "Polymer_B": [132, 104, 82, 64, 49],
            "Polymer_C": [110, 88, 70, 54, 41],
        }
    ).set_index("Shear_Rate")
    st.subheader("Rheology")
    st.line_chart(rheology_df)

    thermal_df = pd.DataFrame(
        {
            "Time_Days": [0, 7, 14, 30, 60],
            "Retention_A": [100, 96, 90, 84, 79],
            "Retention_B": [100, 92, 85, 75, 68],
        }
    ).set_index("Time_Days")
    st.subheader("Thermal Stability")
    st.line_chart(thermal_df)

    phase_df = pd.DataFrame(
        {
            "Formulation": ["A-1", "A-2", "B-1", "B-2", "C-1"],
            "No_Precipitation": [82, 70, 65, 91, 76],
            "Precipitation": [18, 30, 35, 9, 24],
        }
    )
    st.subheader("Phase Behaviour")
    st.bar_chart(phase_df.set_index("Formulation"))

    st.subheader("IFT Comparison")
    ift_df = pd.DataFrame(
        {"Formulation": ["F1", "F2", "F3", "F4"], "IFT": [0.022, 0.010, 0.040, 0.013]}
    )
    st.bar_chart(ift_df.set_index("Formulation"))


def render_fluid_rock_section():
    """Fluid–rock CEOR section aligned to the PDF design."""
    st.header("🪨 CEOR — Fluid / Rock")

    adsorption_df = pd.DataFrame(
        {
            "Days": [0, 7, 14, 30, 60],
            "Adsorption_Surf_A": [0.0, 0.18, 0.27, 0.35, 0.42],
            "Adsorption_Surf_B": [0.0, 0.12, 0.20, 0.28, 0.31],
        }
    ).set_index("Days")
    st.subheader("Adsorption vs Time")
    st.line_chart(adsorption_df)

    coreflood_df = pd.DataFrame(
        {
            "Core": ["Core 1", "Core 2", "Core 3", "Core 4"],
            "Waterflood": [42, 38, 45, 41],
            "EOR_Increment": [15, 18, 11, 14],
        }
    )
    st.subheader("Core Flood Incremental Recovery")
    st.bar_chart(coreflood_df.set_index("Core"))

    sor_df = pd.DataFrame(
        {
            "Core": ["Core 1", "Core 2", "Core 3", "Core 4"],
            "Sor_Reduction": [36, 28, 41, 31],
        }
    )
    st.subheader("Sor Reduction")
    st.bar_chart(sor_df.set_index("Core"))


def render_challenges_section():
    """Lessons-learnt and challenge registry reflecting the PDF knowledge pages."""
    st.header("⚠️ Challenges & Lessons Learnt")

    challenge_df = pd.DataFrame(
        {
            "Field": ["Angsi", "Dulang", "Barton", "Baram"],
            "Chemical_Compatibility": ["High", "Medium", "Low", "High"],
            "Facilities": ["Medium", "Low", "High", "Medium"],
            "Fluid_Handling": ["High", "Medium", "Medium", "Low"],
            "Cost_Logistics": ["High", "Medium", "Low", "High"],
        }
    )
    st.dataframe(challenge_df, width="stretch")

    dist = pd.DataFrame(
        {
            "Challenge": ["Chemical compatibility", "Facilities", "Fluid handling", "Cost / logistics", "Risk / uncertainty"],
            "Count": [4, 3, 3, 2, 2],
        }
    )
    st.subheader("Challenge Distribution")
    st.bar_chart(dist.set_index("Challenge"))


def render_eor_intelligence_section():
    """ML and model intelligence layer aligned with the PDF's intelligence panel."""
    st.header("🤖 EOR Intelligence")
    render_model_registry_section()
    st.write("---")
    render_saved_run_detail_section()


def main():
    """Main EOR Atlas application entry point with the rebuilt dashboard architecture."""
    st.title("🛢️ EOR Atlas – Decision Support Platform")
    st.caption("Engineering-first EOR dashboard built around screening, candidate discovery, CEOR evidence, and auditability.")

    st.markdown(
        """
        <style>
        .block-container { padding-top: 1.1rem; }
        .stTabs [role="tablist"] { background: rgba(15, 23, 42, 0.05); border-radius: 10px; }
        .stTabs [role="tab"] { padding: 0.7rem 1rem; }
        div[data-testid="stMetricValue"] { font-size: 1.4rem; }
        .metric-card { background: linear-gradient(135deg, #0f172a, #1e293b); padding: 0.8rem 1rem; border-radius: 12px; color: white; margin-bottom: 0.75rem; }
        .exec-kpi-card {
            background: linear-gradient(135deg, #0f172a 0%, #1d4ed8 100%);
            border-radius: 14px;
            padding: 1rem 1.1rem;
            margin-bottom: 0.8rem;
            min-height: 110px;
            box-shadow: 0 6px 18px rgba(15, 23, 42, 0.15);
        }
        .exec-kpi-label {
            color: rgba(255,255,255,0.75);
            font-size: 0.77rem;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            margin-bottom: 0.5rem;
        }
        .exec-kpi-value {
            color: white;
            font-size: 1.8rem;
            font-weight: 700;
            line-height: 1.2;
        }
        .sidebar-status-box {
            background: rgba(15, 23, 42, 0.04);
            border: 1px solid rgba(15, 23, 42, 0.08);
            border-radius: 12px;
            padding: 0.75rem;
        }
        .status-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 0.5rem;
            margin: 0.35rem 0;
            font-size: 0.88rem;
        }
        .status-pill {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            padding: 0.18rem 0.5rem;
            border-radius: 999px;
            font-size: 0.72rem;
            font-weight: 600;
        }
        .status-pill.ready { background: rgba(22, 163, 74, 0.12); color: #166534; }
        .status-pill.warn { background: rgba(245, 158, 11, 0.12); color: #b45309; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.sidebar.header("📋 EOR Atlas")
    st.sidebar.caption("Engineering decision workspace")
    render_sidebar_status()

    path_status = settings.validate_paths()
    if not all(path_status.values()):
        missing = [k for k, v in path_status.items() if not v]
        st.sidebar.warning(f"Artifacts pending: {', '.join(missing)}")

    services = initialize_services()
    if services is None:
        st.error("Failed to initialize application services.")
        return

    tabs = st.tabs([
        "🏠 Executive Overview",
        "🔍 EOR Screening",
        "🗺️ Field / Reservoir Candidates",
        "🧪 CEOR — Fluid / Fluid",
        "🪨 CEOR — Fluid / Rock",
        "📚 Past EOR Results",
        "⚠️ Challenges & Lessons",
        "🤖 EOR Intelligence",
    ])

    with tabs[0]:
        render_executive_overview_section()

    with tabs[1]:
        render_eor_screening_tab(services)

    with tabs[2]:
        render_field_candidates_section()

    with tabs[3]:
        render_fluid_fluid_section()

    with tabs[4]:
        render_fluid_rock_section()

    with tabs[5]:
        st.header("📚 Past EOR Results")
        render_database_summary_section()
        st.write("---")
        st.subheader("Historical outcome ledger")
        try:
            history = RepositoryFactory.screening_repo().get_recent(days=365)
            history_df = pd.DataFrame([
                {"Run ID": run.id, "Field": run.formation, "Recommendation": run.recommended_technique, "Status": run.recommendation_status, "Score": run.recommendation_score}
                for run in history
            ])
            st.dataframe(history_df, width="stretch")
        except Exception as exc:
            logger.warning(f"Historical results unavailable: {exc}")
            st.info("No historical records available yet.")

    with tabs[6]:
        render_challenges_section()

    with tabs[7]:
        render_eor_intelligence_section()


if __name__ == "__main__":
    main()
