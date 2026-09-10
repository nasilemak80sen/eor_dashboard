"""EOR Candidates page."""

from __future__ import annotations

import streamlit as st

from ui.components import insight_cards, reset_button, section_title


def render() -> None:
    import app_2 as _app

    insight_cards([
        ("INTERACTIVE", "Explore the population", "Adjust fluid, producing status and engineering ranges to narrow the candidate universe."),
        ("VISUAL", "Read the relationships", "Use X/Y properties and grouping to see how reservoir characteristics distribute."),
        ("ACTION", "Move to screening", "A selected reservoir becomes the natural hand-off into deterministic EOR Screening."),
    ])
    st.markdown("<div class='atlas-divider'></div>", unsafe_allow_html=True)

    explore_tab, definitions_tab = st.tabs(["Candidate Explorer", "Data & Definitions"])

    with explore_tab:
        action_col, _ = st.columns([1, 4])
        with action_col:
            reset_button(
                "↺ Reset explorer",
                prefixes="candidate_",
                key="candidates_reset_explorer",
            )
        section_title("Candidate Explorer", "Field and reservoir parameters remain independent from the EOR decision engine.")
        try:
            _app.render_field_candidates_section()
        except Exception as exc:
            st.error(f"Candidate analytics could not be rendered: {exc}")

    with definitions_tab:
        section_title("How to use Candidate Explorer", "This workspace is for portfolio discovery only; it does not execute the Excel Gate, fuzzy suitability or machine learning.")
        st.markdown("""
        **Filters** narrow the reservoir population by production status, injected fluid and engineering ranges.

        **Graph Properties** lets you compare reservoir parameters and group points by a categorical dimension.

        **Selected Reservoir Detail** exposes the underlying engineering record for review before moving into EOR Screening.
        """)
