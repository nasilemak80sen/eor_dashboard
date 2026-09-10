"""Challenges and lessons page."""

from __future__ import annotations

import streamlit as st

from ui.components import insight_cards, section_title


def render() -> None:
    import app_2 as _app

    insight_cards([
        ("TECHNICAL", "Reservoir uncertainty", "Highlight subsurface and process uncertainties that can affect EOR performance."),
        ("FACILITIES", "Execution readiness", "Track injection, handling and surface constraints before progressing an option."),
        ("LEARNING", "Past experience", "Use lessons learned to shape what needs verification in the next screening cycle."),
    ])
    st.markdown("<div class='atlas-divider'></div>", unsafe_allow_html=True)

    risk_tab, lessons_tab = st.tabs(["Risk Landscape", "How to Use"])
    with risk_tab:
        section_title("Risk Landscape", "Technical, facilities, fluid-handling and execution constraints from the existing knowledge module.")
        try:
            _app.render_challenges_section()
        except Exception as exc:
            st.error(f"Challenge data could not be rendered: {exc}")
    with lessons_tab:
        section_title("How to Use", "Keep key risks visible before advancing an EOR option.")
        st.markdown("Review technical uncertainty, facility readiness and lessons learned alongside the screening result; they are supporting evidence, not a replacement for the engineering gate.")
