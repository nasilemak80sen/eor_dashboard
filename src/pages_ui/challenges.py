"""Challenges and lessons page."""

from __future__ import annotations

import streamlit as st

from ui.components import insight_cards, page_header, section_title


def render() -> None:
    import app_2 as _app

    page_header(
        "Risk & Lessons",
        "Challenges & Lessons",
        "Capture technical, operational and execution risks so they remain visible alongside EOR opportunity.",
    )
    insight_cards([
        ("TECHNICAL", "Reservoir uncertainty", "Highlight subsurface and process uncertainties that can affect EOR performance."),
        ("FACILITIES", "Execution readiness", "Track injection, handling and surface constraints before progressing an option."),
        ("LEARNING", "Past experience", "Use lessons learned to shape what needs verification in the next screening cycle."),
    ])
    st.markdown("<div class='atlas-divider'></div>", unsafe_allow_html=True)
    section_title("Risk Landscape", "Current challenge view from the existing EOR Atlas knowledge module.")
    try:
        _app.render_challenges_section()
    except Exception as exc:
        st.error(f"Challenge data could not be rendered: {exc}")
