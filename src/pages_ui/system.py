"""System and model governance page."""

from __future__ import annotations

import streamlit as st

from ui.components import kpi_cards, page_header, section_title, status_grid


def render(services: dict) -> None:
    import app_2 as _app

    page_header(
        "Platform Governance",
        "System & Model",
        "Monitor the application health, workbook connection and active CatBoost configuration.",
    )

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

    col1, col2 = st.columns(2)
    with col1:
        section_title("System Health")
        status_grid([
            ("Excel workbook", workbook_ready),
            ("ML configuration", config_ready),
            ("CatBoost model", model_ready),
            ("Decision Fusion", True),
        ])
    with col2:
        section_title("Active Model")
        if model_ready:
            try:
                info = model_service.get_model_info()
                st.json(info)
            except Exception as exc:
                st.warning(f"Model metadata could not be displayed: {exc}")
        else:
            st.info("The CatBoost model is not currently available to the application.")

    st.markdown("<div class='atlas-divider'></div>", unsafe_allow_html=True)
    section_title("V3 Training Readiness")
    st.info("The engineering-aware CatBoost v2 pipeline is kept separate from the current production-compatible model. It should only be promoted after independent labeled-data validation.")

    with st.expander("Runtime diagnostics", expanded=False):
        st.write(f"Environment: `{getattr(_app.settings, 'environment', 'unknown')}`")
        st.write(f"Workbook path: `{getattr(_app.settings, 'workbook_path', 'unknown')}`")
        st.write(f"Model loaded: `{model_ready}`")
