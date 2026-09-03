"""
EOR Atlas - Enhanced Oil Recovery Screening System
Phase 3B & Phase 4: Integrated ML + Engineering Decision Support

Architecture:
- Streamlit UI (presentation layer)
- ModelService (ML layer) → PredictionResult
- EngineeringRuleEngine (domain logic)
- DecisionEngine (reconciliation)

UI does NOT contain business logic.
"""

import streamlit as st
import logging
from typing import Dict

from src.config import STREAMLIT_CONFIG, SESSION_CONFIG, FEATURES, EOR_TECHNIQUES, NUM_FEATURES, NUM_CLASSES, CONFIDENCE_THRESHOLDS, CONFIDENCE_LEVELS
from src.model_service import ModelService
from src.decision_engine import DecisionEngine
from src.ui.ui_components import ( MLResultCard, EngineeringAssessmentCard, IntegratedDecisionCard, CandidateRanking, SensitivityAnalysis, DecisionMatrix, ModelStatus)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configure Streamlit
st.set_page_config(
    page_title=STREAMLIT_CONFIG["page_title"],
    page_icon=STREAMLIT_CONFIG["page_icon"],
    layout=STREAMLIT_CONFIG["layout"],
    initial_sidebar_state=STREAMLIT_CONFIG["initial_sidebar_state"],
)

# Initialize services (cached for performance)
@st.cache_resource
def initialize_services():
    """Initialize ML and decision services"""
    model_service = ModelService()
    decision_engine = DecisionEngine()
    return model_service, decision_engine


def get_reservoir_input() -> Dict:
    """
    Get reservoir input from UI
    
    Phase 3B: Collect all required features
    """
    
    st.markdown("### 📊 Reservoir Input Data")
    
    reservoir_data = {}
    
    # Organize inputs in columns
    col1, col2, col3 = st.columns(3)
    
    with col1:
        reservoir_data["Depth"] = st.number_input(
            "Depth (ft)",
            min_value=100.0,
            max_value=20000.0,
            value=5000.0,
            step=100.0,
            help="Reservoir depth in feet"
        )
        
        reservoir_data["Porosity"] = st.number_input(
            "Porosity (%)",
            min_value=0.0,
            max_value=100.0,
            value=20.0,
            step=1.0,
            help="Effective porosity as percentage"
        )
        
        reservoir_data["Permeability"] = st.number_input(
            "Permeability (md)",
            min_value=0.0,
            max_value=10000.0,
            value=100.0,
            step=10.0,
            help="Permeability in millidarcies"
        )
        
        reservoir_data["API"] = st.number_input(
            "API Gravity (°API)",
            min_value=0.0,
            max_value=60.0,
            value=32.0,
            step=1.0,
            help="Oil API gravity"
        )
        
        reservoir_data["Viscosity"] = st.number_input(
            "Viscosity (cp)",
            min_value=0.1,
            max_value=1000.0,
            value=10.0,
            step=0.5,
            help="Oil viscosity at reservoir temperature"
        )
    
    with col2:
        reservoir_data["Oil_Saturation"] = st.number_input(
            "Oil Saturation (%)",
            min_value=0.0,
            max_value=100.0,
            value=65.0,
            step=1.0,
            help="Initial oil saturation"
        )
        
        reservoir_data["Formation"] = st.selectbox(
            "Formation Type",
            ["Sandstone", "Carbonate", "Shale", "Mixed"],
            help="Primary formation lithology"
        )
        
        reservoir_data["Temperature"] = st.number_input(
            "Temperature (°F)",
            min_value=50.0,
            max_value=500.0,
            value=150.0,
            step=5.0,
            help="Reservoir temperature"
        )
        
        reservoir_data["Clay_Content"] = st.number_input(
            "Clay Content (%)",
            min_value=0.0,
            max_value=100.0,
            value=15.0,
            step=1.0,
            help="Clay content percentage"
        )
        
        reservoir_data["Water_Saturation"] = st.number_input(
            "Water Saturation (%)",
            min_value=0.0,
            max_value=100.0,
            value=35.0,
            step=1.0,
            help="Initial water saturation"
        )
    
    with col3:
        reservoir_data["Net_to_Gross"] = st.number_input(
            "Net-to-Gross Ratio",
            min_value=0.0,
            max_value=1.0,
            value=0.7,
            step=0.05,
            help="Net pay to gross thickness"
        )
        
        reservoir_data["Trap_Type"] = st.selectbox(
            "Trap Type",
            ["Structural", "Stratigraphic", "Combination"],
            help="Trap type classification"
        )
        
        reservoir_data["Lithology"] = st.selectbox(
            "Lithology",
            ["Sandstone", "Dolomite", "Limestone", "Shale", "Mixed"],
            help="Primary lithology"
        )
        
        reservoir_data["Underburden"] = st.selectbox(
            "Underburden",
            ["Good", "Fair", "Poor"],
            help="Underburden quality"
        )
        
        reservoir_data["Seal_Quality"] = st.selectbox(
            "Seal Quality",
            ["Excellent", "Good", "Fair"],
            help="Seal quality assessment"
        )
        
        reservoir_data["Faulting"] = st.number_input(
            "Faulting (%)",
            min_value=0.0,
            max_value=100.0,
            value=10.0,
            step=5.0,
            help="Degree of faulting"
        )
        
        reservoir_data["Dip"] = st.number_input(
            "Dip (degrees)",
            min_value=0.0,
            max_value=90.0,
            value=15.0,
            step=1.0,
            help="Structural dip"
        )
    
    return reservoir_data


def main():
    """Main application"""
    
    # Header
    st.markdown("# 🔍 EOR Atlas")
    st.markdown(
        "Enhanced Oil Recovery Screening System — "
        "Phase 3B & Phase 4: ML + Engineering Decision Support"
    )
    st.markdown("---")
    
    # Initialize services
    model_service, decision_engine = initialize_services()
    
    # Sidebar: System status and navigation
    st.sidebar.markdown("# Navigation")
    
    tab_choice = st.sidebar.radio(
        "Select view:",
        ["🎯 Screening", "📊 Batch Analysis", "ℹ️ Help"]
    )
    
    # Model status
    ModelStatus.render(model_service.get_model_info())
    
    if not model_service.is_model_loaded():
        st.error(
            "⚠️ ML model not available. "
            "Engineering screening still functional. "
            f"\n\nError: {model_service.error_message}"
        )
        return
    
    # Main screening workflow
    if tab_choice == "🎯 Screening":
        
        st.markdown("## Reservoir Screening Workflow")
        
        # Get reservoir input
        reservoir_data = get_reservoir_input()
        
        # Run screening button
        col1, col2 = st.columns([1, 3])
        with col1:
            if st.button("🚀 Run Screening", use_container_width=True):
                st.session_state.run_screening = True
        
        # Only run if button clicked (not on every rerun)
        if st.session_state.get("run_screening", False):
            
            st.markdown("---")
            st.markdown("## Screening Results")
            
            # Phase 3B: ML Prediction
            with st.spinner("Running ML prediction..."):
                ml_result = model_service.predict(reservoir_data)
            
            if ml_result.is_valid:
                
                # Display ML result
                st.markdown("## Phase 3B: ML Screening")
                MLResultCard.render(ml_result)
                
                st.markdown("---")
                
                # Phase 4: Engineering Assessment + Decision
                st.markdown("## Phase 4: Engineering Assessment & Decision")
                
                # Get integrated assessment for primary prediction
                primary_assessment = decision_engine.assess_and_decide(
                    ml_result,
                    reservoir_data
                )
                
                # Display integrated decision
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    # Engineering assessment card
                    EngineeringAssessmentCard.render(
                        primary_assessment.engineering_assessment
                    )
                
                with col2:
                    # Decision card
                    IntegratedDecisionCard.render(primary_assessment)
                
                st.markdown("---")
                
                # Ranking all candidates
                st.markdown("## Candidate Ranking Analysis")
                
                ranked_assessments = decision_engine.rank_all_candidates(
                    ml_result,
                    reservoir_data
                )
                
                CandidateRanking.render(ranked_assessments)
                
                st.markdown("---")
                
                # Sensitivity analysis
                st.markdown("## Sensitivity Analysis")
                
                sensitivity_param = st.selectbox(
                    "Select parameter to analyze:",
                    ["Viscosity", "Permeability", "Depth", "API"]
                )
                
                # Define ranges for sensitivity
                ranges = {
                    "Viscosity": (1, 100),
                    "Permeability": (10, 500),
                    "Depth": (1000, 15000),
                    "API": (10, 45),
                }
                
                range_low, range_high = ranges.get(sensitivity_param, (0, 100))
                
                sensitivity_results = decision_engine.sensitivity_analysis(
                    ml_result,
                    reservoir_data,
                    parameter=sensitivity_param,
                    range_low=range_low,
                    range_high=range_high,
                    steps=7
                )
                
                SensitivityAnalysis.render(sensitivity_results)
                
                st.markdown("---")
                
                # Decision summary for export
                st.markdown("## Summary")
                
                summary = decision_engine.get_decision_summary(primary_assessment)
                st.info(summary)
            
            else:
                st.error(f"❌ Screening failed: {ml_result.error_message}")
    
    elif tab_choice == "📊 Batch Analysis":
        st.markdown("## Batch Analysis")
        st.info(
            "Upload a CSV file with reservoir data for bulk screening. "
            "Each row = one reservoir."
        )
        
        uploaded_file = st.file_uploader("Upload CSV", type=["csv"])
        
        if uploaded_file:
            import pandas as pd
            
            df = pd.read_csv(uploaded_file)
            st.write(f"Loaded {len(df)} reservoirs")
            
            if st.button("Run Batch Screening"):
                reservoirs = df.to_dict("records")
                results = model_service.batch_predict(reservoirs)
                
                # Display results
                results_df = pd.DataFrame([
                    {
                        "Technique": r.technique,
                        "Confidence": r.confidence_percentage,
                        "Valid": r.is_valid
                    }
                    for r in results
                ])
                
                st.dataframe(results_df, use_container_width=True)
                
                # Download results
                csv = results_df.to_csv(index=False)
                st.download_button(
                    "📥 Download Results",
                    csv,
                    "eor_screening_results.csv",
                    "text/csv"
                )
    
    elif tab_choice == "ℹ️ Help":
        st.markdown("## EOR Atlas Help")
        
        st.markdown("### Architecture Overview")
        st.markdown("""
        **Phase 3B: ML ↔ Streamlit Integration**
        - ModelService encapsulates CatBoost
        - Returns PredictionResult (not raw ML output)
        - UI never directly calls ML functions
        
        **Phase 4: Engineering Decision Intelligence**
        - EngineeringRuleEngine evaluates domain criteria
        - DecisionEngine reconciles ML + Engineering
        - IntegratedAssessment = final recommendation
        """)
        
        st.markdown("### Decision Matrix")
        DecisionMatrix.render()
        
        st.markdown("### Tips")
        st.markdown("""
        - **Low ML Confidence:** Engineering review essential
        - **Engineering Conflict:** Requires domain expert input
        - **Strong Candidate:** High confidence in both ML and engineering
        - **Sensitivity Analysis:** Explore decision stability
        """)


if __name__ == "__main__":
    main()
