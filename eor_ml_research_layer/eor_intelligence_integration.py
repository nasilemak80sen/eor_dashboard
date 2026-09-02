
"""
Example EOR Intelligence integration.

Keep EOR Screening deterministic and independent.
This panel adds research ML + fuzzy analysis without overriding screening.
"""

from pathlib import Path
from typing import Dict, Any

import pandas as pd
import streamlit as st

from ml.research_model_service import ResearchModelService, build_feature_row


@st.cache_resource
def load_research_model() -> ResearchModelService:
    service = ResearchModelService()
    service.load()
    return service


def render_eor_intelligence_research_panel(
    reservoir_inputs: Dict[str, Any],
    fuzzy_engine=None,
    fuzzy_techniques=None,
    fuzzy_values=None,
):
    st.subheader("🧠 EOR Intelligence — Research ML Layer")

    service = load_research_model()

    if not service.is_loaded:
        st.warning(
            "Research ML artifact is not available. "
            "Run the notebook research pipeline and export "
            "outputs/model_artifacts/eor_research_best.joblib."
        )
        return

    top3 = service.predict_top3_from_ranges(
        depth_min_ft=reservoir_inputs["depth_min_ft"],
        depth_max_ft=reservoir_inputs["depth_max_ft"],
        porosity_min_pct=reservoir_inputs["porosity_min_pct"],
        porosity_max_pct=reservoir_inputs["porosity_max_pct"],
        perm_min_md=reservoir_inputs["perm_min_md"],
        perm_max_md=reservoir_inputs["perm_max_md"],
        api_min=reservoir_inputs["api_min"],
        api_max=reservoir_inputs["api_max"],
        visc_min_cp=reservoir_inputs["visc_min_cp"],
        visc_max_cp=reservoir_inputs["visc_max_cp"],
        so_min_pct=reservoir_inputs["so_min_pct"],
        so_max_pct=reservoir_inputs["so_max_pct"],
        formation=reservoir_inputs["formation"],
    )

    st.markdown("### ML Top 3")
    ml_df = pd.DataFrame(
        [
            {"Rank": i + 1, "EOR Technique": name, "ML Probability": prob}
            for i, (name, prob) in enumerate(top3)
        ]
    )
    ml_df["ML Probability"] = ml_df["ML Probability"].map(lambda x: f"{x:.1%}")
    st.dataframe(ml_df, hide_index=True, use_container_width=True)

    st.caption(
        "These are learned ranking probabilities from the research model. "
        "They are not engineering feasibility gates and do not override deterministic screening."
    )

    if fuzzy_engine is not None and fuzzy_techniques is not None and fuzzy_values is not None:
        fuzzy_scores = fuzzy_engine.evaluate_all(
            fuzzy_techniques,
            reservoir_inputs["formation"],
            fuzzy_values,
        )

        fuzzy_df = (
            pd.DataFrame(
                [
                    {"EOR Technique": technique, "Fuzzy Suitability": score}
                    for technique, score in fuzzy_scores.items()
                ]
            )
            .sort_values("Fuzzy Suitability", ascending=False)
            .head(3)
        )
        fuzzy_df["Fuzzy Suitability"] = fuzzy_df["Fuzzy Suitability"].map(lambda x: f"{x:.1%}")

        st.markdown("### Fuzzy Top 3")
        st.dataframe(fuzzy_df, hide_index=True, use_container_width=True)

    st.markdown("### Model information")
    st.json(service.model_info())
