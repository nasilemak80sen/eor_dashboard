"""Challenges and lessons page."""

from __future__ import annotations

import streamlit as st

from ui.components import insight_cards, section_title


def render() -> None:
    import app_2 as _app

    insight_cards([
        ("RISK", "Make constraints visible", "Keep technical, facilities and execution risks alongside opportunity rather than after the decision."),
        ("LEARN", "Use prior experience", "Lessons learned should challenge assumptions and highlight what needs verification."),
        ("ACT", "Close the loop", "Carry material risks into the next screening or project-planning step."),
    ])
    st.markdown("<div class='atlas-divider'></div>", unsafe_allow_html=True)

    risk_tab, lessons_tab = st.tabs(["Risk Landscape", "How to Use"])
    with risk_tab:
        section_title("Risk Landscape", "Technical, facilities, fluid-handling and execution constraints from the existing knowledge module.")
        try:
            _app.render_challenges_section()
        except Exception as exc:
            st.error("Challenge data could not be rendered. Review System & Model for application health.")
            st.caption(str(exc))
    with lessons_tab:
        section_title("How to Use", "Keep risks visible before advancing an EOR option.")
        st.markdown("Review technical uncertainty, facility readiness and lessons learned alongside the screening result. Treat them as supporting evidence and project-readiness context, not as a replacement for the deterministic engineering gate.")
