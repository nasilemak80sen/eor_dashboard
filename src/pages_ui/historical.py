"""Historical EOR knowledge page."""

from __future__ import annotations

import streamlit as st

from ui.components import kpi_cards, section_title


def render() -> None:
    import app_2 as _app

    kpi_cards([
        ("Historical Studies", 128, "Knowledge-base reference"),
        ("Saved Runs", "Live", "Retrieved from the application database"),
        ("Decision Use", "Context", "Historical results support—not replace—current screening"),
    ])
    st.markdown("<div class='atlas-divider'></div>", unsafe_allow_html=True)

    history_tab, detail_tab = st.tabs(["Screening History", "Saved Run Detail"])
    with history_tab:
        section_title("Screening History", "Recent decisions captured by the application database.")
        try:
            _app.render_database_summary_section()
        except Exception as exc:
            st.info(f"Screening history is temporarily unavailable: {exc}")
    with detail_tab:
        section_title("Saved Run Detail", "Inspect a historical run and its engineering context.")
        try:
            _app.render_saved_run_detail_section()
        except Exception as exc:
            st.info(f"Saved-run detail is temporarily unavailable: {exc}")
