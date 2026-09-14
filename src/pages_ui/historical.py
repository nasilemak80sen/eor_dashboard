"""Historical EOR knowledge page."""

from __future__ import annotations

import streamlit as st

from ui.components import insight_cards, kpi_cards, section_title


def render() -> None:
    import app_2 as _app

    kpi_cards([
        ("Historical Studies", 128, "Knowledge-base reference"),
        ("Saved Runs", "Live", "Application database"),
        ("Decision Use", "Context", "Supporting evidence only"),
    ])
    insight_cards([
        ("LOOK BACK", "What was screened?", "Review prior saved runs and the engineering context captured with them."),
        ("COMPARE", "What can inform today?", "Use historical evidence to challenge assumptions, not replace current screening."),
        ("HAND-OFF", "What happens next?", "Return to Candidates or Screening when a current reservoir decision is required."),
    ])
    st.markdown("<div class='atlas-divider'></div>", unsafe_allow_html=True)

    history_tab, detail_tab = st.tabs(["Screening History", "Saved Run Detail"])
    with history_tab:
        section_title("Screening History", "Recent decisions captured by the application database.")
        try:
            _app.render_database_summary_section()
        except Exception as exc:
            st.info("Screening history is temporarily unavailable. Check System & Model for runtime health.")
            st.caption(str(exc))
    with detail_tab:
        section_title("Saved Run Detail", "Inspect the engineering context and outcome of a selected historical run.")
        try:
            _app.render_saved_run_detail_section()
        except Exception as exc:
            st.info("Saved-run detail is temporarily unavailable. Check System & Model for runtime health.")
            st.caption(str(exc))
