"""Executive Overview page."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from ui.components import insight_cards, kpi_cards, page_header, section_title


def render() -> None:
    import app_2 as _app

    page_header(
        "Portfolio Overview",
        "Executive Overview",
        "A decision-oriented view of the EOR portfolio, opportunity landscape and system readiness.",
    )

    kpi_cards([
        ("Fields", 41, "Portfolio coverage"),
        ("Reservoirs", 600, "Screening universe"),
        ("Potential Candidates", 18, "Current opportunity pool"),
        ("Historical Studies", 128, "Knowledge base"),
        ("RF Gap", "1.31", "MMstb opportunity indicator"),
    ])

    st.markdown("<div class='atlas-divider'></div>", unsafe_allow_html=True)
    col1, col2 = st.columns([1.7, 1])
    with col1:
        section_title("Field Opportunity Map", "Portfolio locations and opportunity signals.")
        try:
            _app.render_executive_overview_section()
        except Exception as exc:
            st.warning(f"Overview map is temporarily unavailable: {exc}")
    with col2:
        section_title("What to do next")
        insight_cards([
            ("DISCOVER", "Find candidates", "Use EOR Candidates to narrow the portfolio to reservoirs worth screening."),
            ("SCREEN", "Run the engineering gate", "Use deterministic ScreenTool v3 results before considering ML recommendations."),
            ("DECIDE", "Review hybrid ranking", "Use Hybrid Intelligence to combine engineering compatibility with CatBoost probability."),
        ])

    st.markdown("<div class='atlas-divider'></div>", unsafe_allow_html=True)
    section_title("Decision Journey", "Move from portfolio discovery to engineering-backed recommendation.")
    journey = pd.DataFrame({
        "Stage": ["Portfolio", "Candidate", "Engineering Gate", "Hybrid Intelligence", "Insight"],
        "Purpose": [
            "See where the opportunity is",
            "Identify reservoirs for review",
            "Test deterministic feasibility",
            "Rank methods with ML support",
            "Translate results into actions",
        ],
    })
    st.dataframe(journey, use_container_width=True, hide_index=True)
