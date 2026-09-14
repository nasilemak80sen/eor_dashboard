"""System and model governance page."""

from __future__ import annotations

import streamlit as st

from ui.components import kpi_cards, section_title, status_grid, insight_cards


def render(services: dict) -> None:
    import app_2 as _app

    try:
        path_status = _app.settings.validate_paths()
    except Exception:
        path_status = {}

    model_service = services.get("model_service")
    model_ready = bool(model_service is not None and model_service.is_loaded())
    workbook_ready = bool(path_status.get("workbook")) or bool(services.get("workbook_sheets"))
    config_ready = bool(path_status.get("config"))

    kpi_cards([
        ("Excel Gate", "READY" if workbook_ready else "CHECK", "Workbook connection"),
        ("CatBoost", "READY" if model_ready else "CHECK", "Active model availability"),
        ("Decision Fusion", "READY", "Hybrid decision service"),
        ("UI State", "Interactive", "Page-local controls and results"),
    ])
    st.markdown("<div class='atlas-divider'></div>", unsafe_allow_html=True)

    insight_cards([
        ("HEALTH", "Can the stack run?", "Workbook, configuration and model readiness are checked before production workflows."),
        ("MODEL", "What is active?", "Model metadata and production-compatible configuration are visible without exposing implementation clutter."),
        ("DIAGNOSTICS", "What changed?", "Runtime paths and state are available when troubleshooting is required."),
    ])

    health_tab, model_tab, runtime_tab = st.tabs(["System Health", "Active Model", "Runtime Diagnostics"])
    with health_tab:
        section_title("System Health", "The minimum components required by the production decision path.")
        status_grid([
            ("Excel workbook", workbook_ready),
            ("ML configuration", config_ready),
            ("CatBoost model", model_ready),
            ("Decision Fusion", True),
        ])
        st.info("Keep this page as the operational backstop. Candidate and Screening pages intentionally keep their own local reset controls.")

    with model_tab:
        section_title("Active Model", "Current production-compatible CatBoost metadata and training-readiness boundary.")
        if model_ready:
            try:
                st.json(model_service.get_model_info())
            except Exception as exc:
                st.warning(f"Model metadata could not be displayed: {exc}")
        else:
            st.warning("The active CatBoost model is unavailable; hybrid recommendations cannot use the production model.")
        section_title("V3 Training Readiness", "Engineering-aware CatBoost v2 stays isolated until independently labelled historical data and validation are available.")
        st.caption("Live production path: Excel Gate → CatBoost → Decision Fusion.")

    with runtime_tab:
        section_title("Runtime Diagnostics", "Compact technical details for troubleshooting, not the primary decision workflow.")
        st.write(f"Environment: `{getattr(_app.settings, 'environment', 'unknown')}`")
        st.write(f"Workbook path: `{getattr(_app.settings, 'workbook_path', 'unknown')}`")
        st.write(f"Model loaded: `{model_ready}`")
