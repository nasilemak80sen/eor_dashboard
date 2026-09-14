"""Primary top navigation and secondary sidebar status for EOR Atlas."""

from __future__ import annotations

from dataclasses import dataclass

import streamlit as st


@dataclass(frozen=True)
class NavItem:
    key: str
    label: str
    icon: str


NAV_ITEMS = (
    NavItem("overview", "Overview", "🏠"),
    NavItem("candidates", "Candidates", "🎯"),
    NavItem("screening", "Screening", "🔍"),
    NavItem("intelligence", "Hybrid", "🧠"),
    NavItem("insights", "Insights", "📊"),
    NavItem("historical", "Historical", "📚"),
    NavItem("challenges", "Challenges", "⚠️"),
    NavItem("ceor", "CEOR Lab", "🧪"),
    NavItem("system", "System", "⚙"),
)


def render_top_nav() -> str:
    """Render persistent pill-button navigation above every page."""
    current = st.session_state.get("atlas_page", "overview")

    st.markdown(
        '<div class="atlas-top-nav-shell"><div class="atlas-top-nav-kicker">EOR ATLAS</div>',
        unsafe_allow_html=True,
    )

    columns = st.columns(len(NAV_ITEMS))
    selected = current
    for column, item in zip(columns, NAV_ITEMS):
        with column:
            if st.button(
                f"{item.icon}  {item.label}",
                key=f"top_nav_{item.key}",
                use_container_width=True,
                type="primary" if item.key == current else "secondary",
            ):
                selected = item.key

    if selected != current:
        st.session_state["atlas_page"] = selected
        st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)
    return selected


def render_sidebar(*, system_state: dict[str, bool] | None = None) -> None:
    """Keep the sidebar as a secondary system/status panel only."""
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
        <div class="nav-section-label">SYSTEM STATUS</div>
        """,
        unsafe_allow_html=True,
    )

    for label, ready in (
        ("Excel Gate", bool(state.get("workbook"))),
        ("CatBoost", bool(state.get("model"))),
        ("Decision Fusion", True),
    ):
        status_class = "status-ok" if ready else "status-check"
        status_text = "READY" if ready else "CHECK"
        st.sidebar.markdown(
            f'<div class="sidebar-status-row"><span>{label}</span><span class="{status_class}">{status_text}</span></div>',
            unsafe_allow_html=True,
        )

    st.sidebar.caption("Secondary panel • system status and diagnostics")


def render_sidebar_status(*, system_state: dict[str, bool] | None = None) -> None:
    """Compatibility alias for legacy callers."""
    render_sidebar(system_state=system_state)
