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
    services_ready = bool(services)

    kpi_cards([
        ("Excel Gate", "READY" if workbook_ready else "CHECK", "Workbook connection"),
        ("CatBoost", "READY" if model_ready else "CHECK", "Active model availability"),
        ("Decision Fusion", "READY", "Hybrid decision service"),
        ("Services", "CACHED" if services_ready else "CHECK", "Reused across UI reruns"),
    ])
    st.markdown("<div class='atlas-divider'></div>", unsafe_allow_html=True)

    insight_cards([
        ("HEALTH", "Can the stack run?", "Workbook, configuration and model readiness are checked before production workflows."),
        ("EXECUTION", "When does it compute?", "Input widgets collect values without executing the decision stack; explicit submit actions start engineering or hybrid calculations."),
        ("GOVERNANCE", "What is authoritative?", "The Excel Gate remains the deterministic engineering anchor ahead of CatBoost and Decision Fusion."),
    ])

    health_tab, model_tab, workflow_tab, runtime_tab = st.tabs([
        "System Health",
        "Active Model",
        "Decision Workflow",
        "Runtime Diagnostics",
    ])

    with health_tab:
        section_title("System Health", "The minimum components required by the production decision path.")
        status_grid([
            ("Excel workbook", workbook_ready),
            ("ML configuration", config_ready),
            ("CatBoost model", model_ready),
            ("Decision Fusion", True),
            ("Cached services", services_ready),
        ])
        st.info("Candidate exploration is descriptive. EOR Screening is deterministic. Hybrid Intelligence adds CatBoost only after the engineering gate. Local reset controls remain page-owned.")

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
        st.caption("The active production model is a compatibility bridge; do not train on ScreenTool-generated labels.")

    with workflow_tab:
        section_title("Decision Workflow", "This is the business-logic contract implemented by the production dashboard.")
        workflow = [
            ("1", "Candidate Discovery", "Filter and compare reservoir records; no EOR recommendation is executed."),
            ("2", "Excel Gate", "Run deterministic EOR criteria only after the user submits the completed reservoir form."),
            ("3", "CatBoost", "Generate model probabilities only during an explicit Hybrid Intelligence submission."),
            ("4", "Decision Fusion", "Combine engineering and model signals, while hard engineering failures remain excluded."),
            ("5", "Decision Review", "Inspect recommendation, ranking, engineering status and model context."),
        ]
        st.dataframe(
            workflow,
            use_container_width=True,
            hide_index=True,
            column_config={
                "0": "Stage",
                "1": "Business Layer",
                "2": "Behaviour",
            },
        )

    with runtime_tab:
        section_title("Runtime Diagnostics", "Compact technical details for troubleshooting, not the primary decision workflow.")
        st.write(f"Environment: `{getattr(_app.settings, 'environment', 'unknown')}`")
        st.write(f"Workbook path: `{getattr(_app.settings, 'workbook_path', 'unknown')}`")
        st.write(f"Model loaded: `{model_ready}`")
        st.write("Service lifecycle: cached at the application-shell level to avoid repeated model/workbook loading on ordinary Streamlit reruns.")
