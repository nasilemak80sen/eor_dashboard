"""Sidebar navigation for the EOR Atlas application shell."""

from __future__ import annotations

from dataclasses import dataclass

import streamlit as st


@dataclass(frozen=True)
class NavItem:
    key: str
    label: str
    icon: str
    section: str


NAV_ITEMS = (
    NavItem("overview", "Executive Overview", "🏠", "Overview"),
    NavItem("candidates", "EOR Candidates", "🎯", "Discovery"),
    NavItem("screening", "EOR Screening", "🔍", "Discovery"),
    NavItem("intelligence", "Hybrid Intelligence", "🧠", "Decision"),
    NavItem("insights", "EOR Insights", "📊", "Decision"),
    NavItem("historical", "Historical EOR", "📚", "Knowledge"),
    NavItem("challenges", "Challenges & Lessons", "⚠️", "Knowledge"),
    NavItem("ceor", "CEOR Lab", "🧪", "Technology"),
    NavItem("system", "System & Model", "⚙", "System"),
)


def _reset_input_state() -> None:
    """Clear all EOR input widgets and transient screening results."""
    prefixes = ("screening_", "intel_")
    keys_to_clear = [
        key
        for key in list(st.session_state.keys())
        if any(str(key).startswith(prefix) for prefix in prefixes)
    ]
    for key in keys_to_clear:
        del st.session_state[key]

    for key in ("excel_screening_result", "eor_intelligence_result"):
        st.session_state.pop(key, None)


def render_sidebar(*, system_state: dict[str, bool] | None = None) -> str:
    """Render the navigation and return the selected page key."""
    state = system_state or {}

    st.sidebar.markdown(
        """
        <div class="atlas-brand">
            <div class="atlas-brand-mark">EA</div>
            <div>
                <div class="atlas-brand-title">EOR ATLAS</div>
                <div class="atlas-brand-subtitle">Reservoir Engineering Decision Support</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    current = st.session_state.get("atlas_page", "overview")
    selected = current

    sections = []
    for item in NAV_ITEMS:
        if item.section not in sections:
            sections.append(item.section)

    for section in sections:
        st.sidebar.markdown(f'<div class="nav-section-label">{section}</div>', unsafe_allow_html=True)
        section_items = [item for item in NAV_ITEMS if item.section == section]
        for item in section_items:
            active = item.key == current
            button_label = f"{'▌ ' if active else ''}{item.icon}  {item.label}"
            if st.sidebar.button(
                button_label,
                key=f"nav_{item.key}",
                use_container_width=True,
                type="primary" if active else "secondary",
            ):
                selected = item.key
                st.session_state["atlas_page"] = item.key

    st.sidebar.markdown('<div style="height:.7rem"></div>', unsafe_allow_html=True)
    st.sidebar.markdown('<div class="nav-section-label">Workspace</div>', unsafe_allow_html=True)

    if st.sidebar.button(
        "↺  Reset EOR Inputs",
        key="sidebar_reset_eor_inputs",
        use_container_width=True,
        type="secondary",
        help="Reset EOR Screening and Hybrid Intelligence inputs to their defaults.",
    ):
        _reset_input_state()
        st.rerun()

    st.sidebar.caption("Reset only the EOR Screening and Hybrid Intelligence input state.")

    st.sidebar.markdown('<div style="height:.45rem"></div>', unsafe_allow_html=True)
    st.sidebar.markdown('<div class="nav-section-label">System Status</div>', unsafe_allow_html=True)
    status_items = (
        ("Excel Gate", bool(state.get("workbook"))),
        ("CatBoost", bool(state.get("model"))),
        ("Decision Fusion", True),
    )
    for label, ready in status_items:
        symbol = "●" if ready else "○"
        status = "READY" if ready else "CHECK"
        st.sidebar.markdown(
            f'<div style="display:flex;justify-content:space-between;font-size:.73rem;margin:.32rem 0;">'
            f'<span>{symbol}&nbsp; {label}</span><span style="opacity:.68;">{status}</span></div>',
            unsafe_allow_html=True,
        )

    st.sidebar.markdown('<div style="height:.35rem"></div>', unsafe_allow_html=True)
    st.sidebar.caption("EOR Atlas • ScreenTool v3 • Hybrid decision stack")

    return selected
