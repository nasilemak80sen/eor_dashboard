"""System and model governance page."""

from __future__ import annotations

import streamlit as st

from ui.components import kpi_cards, section_title, status_grid


def render(services: dict) -> None:
    import app_2 as _app

    try:
        path_status = _app.settings.validate_paths()
    except Exception:
        path_status = {}

    model_service = services.get("model_service")
    model_ready = bool(model_service is not None and model_service.is_loaded())
    workbook_ready = bool(path_status.get("workbook"))
    config_ready = bool(path_status.get("config"))

    kpi_cards([
        ("Excel Gate", "READY" if workbook_ready else "CHECK", "Workbook connection"),
        ("CatBoost", "READY" if model_ready else "CHECK", "Active model availability"),
        ("Decision Fusion", "READY", "Hybrid decision service"),
    ])
    st.markdown("<div class='atlas-divider'></div>", unsafe_allow_html=True)

    health_tab, model_tab, runtime_tab = st.tabs(["System Health", "Active Model", "Runtime Diagnostics"])

    with health_tab:
        section_title("System Health", "A compact operational view of the components required by the decision stack.")
        status_grid([
            ("Excel workbook", workbook_ready),
            ("ML configuration", config_ready),
            ("CatBoost model", model_ready),
            ("Decision Fusion", True),
        ])
        st.info("The sidebar is intentionally reserved for global navigation and system status. Local form reset controls remain on the pages that own the inputs.")

    with model_tab:
        section_title("Active Model", "Current production-compatible model metadata.")
        if model_ready:
            try:
                st.json(model_service.get_model_info())
            except Exception as exc:
                st.warning(f"Model metadata could not be displayed: {exc}")
        else:
            st.info("The CatBoost model is not currently available to the application.")
        section_title("V3 Training Readiness", "Engineering-aware CatBoost v2 remains isolated until it has independently labelled training data and validation.")
        st.caption("The live decision path remains Excel Gate → CatBoost → Decision Fusion.")

    with runtime_tab:
        section_title("Runtime Diagnostics", "Useful environment details without crowding the main workspace.")
        st.write(f"Environment: `{getattr(_app.settings, 'environment', 'unknown')}`")
        st.write(f"Workbook path: `{getattr(_app.settings, 'workbook_path', 'unknown')}`")
        st.write(f"Model loaded: `{model_ready}`")
