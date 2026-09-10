"""EOR Candidates page."""

from __future__ import annotations

import streamlit as st

from ui.components import insight_cards, section_title


def render() -> None:
    import app_2 as _app

    insight_cards([
        ("INTERACTIVE", "Explore the population", "Adjust fluid, producing status and engineering ranges to narrow the candidate universe."),
        ("VISUAL", "Read the relationships", "Use X/Y properties and grouping to see how reservoir characteristics distribute."),
        ("ACTION", "Move to screening", "A selected reservoir becomes the natural hand-off into deterministic EOR Screening."),
    ])
    st.markdown("<div class='atlas-divider'></div>", unsafe_allow_html=True)
    section_title("Candidate Explorer", "Field and reservoir parameters remain independent from the EOR decision engine.")
    try:
        _app.render_field_candidates_section()
    except Exception as exc:
        st.error(f"Candidate analytics could not be rendered: {exc}")
