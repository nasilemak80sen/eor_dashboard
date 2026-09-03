"""
UI Components for Streamlit
Phase 3B: ML result display
Phase 4: Engineering + decision display
"""

import streamlit as st
import pandas as pd
from typing import Dict, List

from src.ml_prediction import PredictionResult, EngineeringAssessment, IntegratedAssessment
from src.decision_engine import DecisionEngine


class MLResultCard:
    """Phase 3B: Display ML prediction result"""
    
    @staticmethod
    def render(result: PredictionResult):
        """Render ML result card"""
        
        if not result.is_valid:
            st.error(f"❌ {result.error_message}")
            return
        
        # Main prediction
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.markdown("### 🤖 ML Screening Result")
            st.markdown(f"### {result.technique}")
        
        with col2:
            st.metric("Confidence", result.confidence_percentage)
        
        # Confidence level
        confidence_color = {
            "🟢 HIGH": "🟢",
            "🟡 MODERATE": "🟡",
            "🔴 LOW": "🔴"
        }
        
        st.markdown(f"**Confidence Level:** {result.display_confidence_level}")
        
        # Low confidence warning
        if result.should_warn_low_confidence():
            st.warning(
                "⚠️ **LOW CONFIDENCE** — ML prediction is uncertain. "
                "Engineering review is strongly recommended."
            )
        
        # Candidates
        st.markdown("#### Top Candidates")
        candidates_df = pd.DataFrame(
            result.get_top_candidates(5),
            columns=["Technique", "Probability"]
        )
        candidates_df["Probability"] = candidates_df["Probability"].apply(
            lambda x: f"{x:.1%}"
        )
        st.dataframe(candidates_df, use_container_width=True, hide_index=True)
        
        # Feature importance
        if result.feature_importance:
            st.markdown("#### Feature Importance")
            
            # Create bar chart data
            importance_df = pd.DataFrame(
                sorted(
                    result.feature_importance.items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:7],
                columns=["Feature", "Importance"]
            )
            
            st.bar_chart(importance_df.set_index("Feature"))
        
        # Model info
        with st.expander("📋 Model Information"):
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Model", result.model_name)
            col2.metric("Version", result.model_version)
            col3.metric("Features", "17")
            col4.metric("Classes", "9")


class EngineeringAssessmentCard:
    """Phase 4: Display engineering assessment"""
    
    @staticmethod
    def render(assessment: EngineeringAssessment):
        """Render engineering assessment card"""
        
        st.markdown("### ⚙️ Engineering Assessment")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.markdown(f"#### {assessment.technique}")
        
        with col2:
            st.metric("Compatibility", f"{assessment.compatibility_score:.0%}")
        
        st.markdown(f"**Level:** {assessment.compatibility_level}")
        
        # Satisfied criteria
        if assessment.satisfied_criteria:
            st.markdown("**✓ Satisfied Criteria:**")
            for criterion in assessment.satisfied_criteria:
                st.write(f"  {criterion}")
        
        # Violated criteria
        if assessment.violated_criteria:
            st.warning("**✗ Violated Criteria:**")
            for criterion in assessment.violated_criteria:
                st.write(f"  {criterion}")
        
        # Warnings
        if assessment.warnings:
            st.info("**⚠️ Cautions:**")
            for warning in assessment.warnings:
                st.write(f"  {warning}")
        
        # Recommendations
        if assessment.recommendations:
            st.markdown("**Recommendations:**")
            for rec in assessment.recommendations:
                st.write(f"  • {rec}")


class IntegratedDecisionCard:
    """Phase 4: Display integrated ML + engineering decision"""
    
    @staticmethod
    def render(assessment: IntegratedAssessment):
        """Render integrated decision card"""
        
        st.markdown("---")
        st.markdown("### 🎯 Integrated Assessment & Recommendation")
        
        # Decision box
        recommendation_color = {
            "🟢": "#00ff41",
            "🟡": "#ffaa00",
            "🔴": "#ff4444"
        }
        
        color = recommendation_color.get(assessment.recommendation_level, "#888888")
        
        st.markdown(
            f"""
            <div style="
                background-color: {color}22;
                border-left: 4px solid {color};
                padding: 16px;
                border-radius: 4px;
            ">
                <h3 style="margin: 0 0 8px 0;">
                    {assessment.recommendation_level} {assessment.recommendation_text.upper()}
                </h3>
                <p style="margin: 0;">
                    <strong>{assessment.ml_result.technique}</strong> — 
                    ML: {assessment.ml_result.confidence_percentage} | 
                    Engineering: {assessment.engineering_assessment.compatibility_score:.0%}
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        # Reasoning
        st.markdown("#### Reasoning")
        for reason in assessment.reasoning:
            st.write(reason)
        
        return assessment


class CandidateRanking:
    """Phase 4: Display ranked candidates"""
    
    @staticmethod
    def render(assessments: List[IntegratedAssessment]):
        """Render ranked candidates table"""
        
        st.markdown("### 📊 Candidate Ranking")
        
        # Prepare data
        ranking_data = []
        for assessment in assessments:
            ranking_data.append({
                "Technique": assessment.ml_result.technique,
                "ML": assessment.ml_result.confidence_percentage,
                "Engineering": f"{assessment.engineering_assessment.compatibility_score:.0%}",
                "Assessment": assessment.recommendation_level,
                "Decision": assessment.recommendation_text,
            })
        
        ranking_df = pd.DataFrame(ranking_data)
        st.dataframe(ranking_df, use_container_width=True, hide_index=True)


class SensitivityAnalysis:
    """Phase 4: Display sensitivity analysis"""
    
    @staticmethod
    def render(analysis_results: List[Dict]):
        """Render sensitivity analysis"""
        
        if not analysis_results:
            st.info("No sensitivity analysis data")
            return
        
        st.markdown("### 📈 Sensitivity Analysis")
        
        # Extract data
        param_name = analysis_results[0].get("parameter_name", "Parameter")
        param_values = [r["parameter_value"] for r in analysis_results]
        scores = [r["engineering_score"] for r in analysis_results]
        
        # Create dataframe
        analysis_df = pd.DataFrame({
            param_name: param_values,
            "Engineering Score": scores,
            "Recommendation": [r["recommendation"] for r in analysis_results]
        })
        
        st.line_chart(analysis_df.set_index(param_name)[["Engineering Score"]])
        
        st.dataframe(analysis_df, use_container_width=True, hide_index=True)


class DecisionMatrix:
    """Phase 4: Display decision matrix"""
    
    @staticmethod
    def render():
        """Display decision matrix explanation"""
        
        st.markdown("### 📋 Decision Matrix Logic")
        st.markdown("""
        The recommendation combines ML and Engineering assessments:
        
        | ML | Engineering | Assessment |
        |----|-------------|------------|
        | High | High | 🟢 Strong candidate |
        | High | Moderate | 🟡 Candidate |
        | High | Low | 🔴 Conflict |
        | Moderate | High | 🟡 Candidate |
        | Moderate | Moderate | 🟡 Review |
        | Low | High | 🟡 Engineering review |
        | Low | Low | 🔴 Weak |
        """)


class ModelStatus:
    """Display model and system status"""
    
    @staticmethod
    def render(model_info: Dict):
        """Render model status"""
        
        st.sidebar.markdown("### 🔧 System Status")
        
        if model_info.get("is_ready"):
            st.sidebar.success("✅ Model loaded")
        else:
            st.sidebar.error(f"❌ {model_info.get('error', 'Model not ready')}")
        
        with st.sidebar.expander("Model Info"):
            st.write(f"**Model:** {model_info.get('model_name')}")
            st.write(f"**Version:** {model_info.get('version')}")
            st.write(f"**Features:** {model_info.get('num_features')}")
            st.write(f"**Classes:** {model_info.get('num_classes')}")
