"""EOR Atlas PETRONAS-style application shell.

Recommended Streamlit entrypoint for the redesigned UI.
The existing hybrid_app module remains the engineering/ML execution layer;
this module only composes navigation and presentation around it.
"""

from __future__ import annotations

import streamlit as st

import hybrid_app as engine
from pages_ui import challenges, ceor, candidates, historical, insights, intelligence, overview, screening, system
from ui.app_shell import initialize_ui, render_shell_header, select_page


def _safe_services() -> dict:
    try:
        return engine.initialize_services()
    except Exception:
        engine._app.logger.exception("EOR Atlas services failed to initialize.")
        return {"model_service": None, "model_loaded": False, "workbook_sheets": {}}


def _system_state(services: dict) -> dict[str, bool]:
    workbook_ready = bool(services.get("workbook_sheets"))
    model_ready = bool(services.get("model_loaded"))
    try:
        workbook_ready = workbook_ready or bool(engine._app.settings.validate_paths().get("workbook"))
    except Exception:
        pass
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
        engine._app.logger.exception("UI page failed: %s", page)
        st.error(f"The {page.replace('_', ' ').title()} page could not be rendered.")
        with st.expander("Technical detail", expanded=False):
            st.code(str(exc))


def main() -> None:
    initialize_ui()
    services = _safe_services()
    page = select_page(_system_state(services))
    render_shell_header()
    _render_page(page, services)


if __name__ == "__main__":
    main()
