"""EOR Atlas PETRONAS-style application shell.

Recommended Streamlit entrypoint for the redesigned UI.
The existing hybrid_app module remains the engineering/ML execution layer;
this module only composes navigation and presentation around it.
"""

from __future__ import annotations

import logging

import streamlit as st

import hybrid_app as engine
from config.settings import settings
from pages_ui import challenges, ceor, candidates, historical, insights, intelligence, overview, screening, system
from ui.app_shell import initialize_ui, render_page_intro, render_shell_header, select_page

logger = logging.getLogger("eor_atlas")


PAGE_META = {
    "overview": ("PORTFOLIO OVERVIEW", "Executive Overview", "A decision-oriented view of the EOR portfolio, opportunity landscape and system readiness."),
    "candidates": ("PORTFOLIO DISCOVERY", "EOR Candidates", "Explore field and reservoir properties, isolate candidate populations and open a reservoir for screening."),
    "screening": ("ENGINEERING GATE", "EOR Screening", "Deterministic reservoir screening using the EOR Screening Tool 2026 v3 criteria."),
    "intelligence": ("ENGINEERING + ML", "Hybrid Intelligence", "Use the deterministic Excel Gate as the engineering anchor, then apply CatBoost and Decision Fusion."),
    "insights": ("DECISION VIEW", "EOR Insights", "Translate screening and portfolio data into an intuitive view of opportunity concentration and next actions."),
    "historical": ("KNOWLEDGE BASE", "Historical EOR", "Review previous EOR studies, saved screening runs and lessons available to inform current decisions."),
    "challenges": ("RISK & LESSONS", "Challenges & Lessons", "Capture technical, operational and execution risks so they remain visible alongside EOR opportunity."),
    "ceor": ("TECHNOLOGY", "CEOR Lab", "Explore fluid/fluid and fluid/rock technical evidence supporting chemical EOR decisions."),
    "system": ("PLATFORM GOVERNANCE", "System & Model", "Monitor application health, workbook connection and the active CatBoost configuration."),
}


@st.cache_resource(show_spinner=False)
def _safe_services() -> dict:
    """Initialize expensive production services once per Streamlit process."""
    try:
        return engine.initialize_services()
    except Exception:
        logger.exception("EOR Atlas services failed to initialize.")
        return {"model_service": None, "model_loaded": False, "workbook_sheets": {}}


def _system_state(services: dict) -> dict[str, bool]:
    workbook_ready = bool(services.get("workbook_sheets"))
    model_ready = bool(services.get("model_loaded"))
    try:
        from config.settings import settings
        workbook_ready = workbook_ready or bool(settings.validate_paths().get("workbook"))
    except Exception:
        logger.exception("Unable to validate EOR Atlas workbook path.")
    return {"workbook": workbook_ready, "model": model_ready}


def _render_page(page: str, services: dict) -> None:
    renderers = {
        "overview": overview.render,
        "candidates": candidates.render,
        "screening": screening.render,
        "intelligence": lambda: intelligence.render(services),
        "insights": lambda: insights.render(services),
        "historical": historical.render,
        "challenges": challenges.render,
        "ceor": ceor.render,
        "system": lambda: system.render(services),
    }
    renderer = renderers.get(page, overview.render)
    try:
        renderer()
    except Exception as exc:
        logger.exception("UI page failed: %s", page)
        st.error(f"The {page.replace('_', ' ').title()} page could not be rendered.")
        with st.expander("Technical detail", expanded=False):
            st.exception(exc)


def main() -> None:
    # This must be the first Streamlit command in the production entrypoint.
    st.set_page_config(
        page_title=settings.ui_config["page_title"],
        page_icon=settings.ui_config["page_icon"],
        layout=settings.ui_config["layout"],
        initial_sidebar_state=settings.ui_config.get("initial_sidebar_state", "collapsed"),
    )
    initialize_ui()
    services = _safe_services()
    page = select_page(_system_state(services))
    render_shell_header()
    kicker, title, subtitle = PAGE_META.get(page, PAGE_META["overview"])
    render_page_intro(kicker, title, subtitle)
    _render_page(page, services)


if __name__ == "__main__":
    main()
