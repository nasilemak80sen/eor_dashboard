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


def render_sidebar(*, system_state: dict[str, bool] | None = None) -> str:
    """Render global navigation only; page-local input reset lives on each form page."""
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

    sections: list[str] = []
    for item in NAV_ITEMS:
        if item.section not in sections:
            sections.append(item.section)

    for section in sections:
        st.sidebar.markdown(
            f'<div class="nav-section-label">{section}</div>',
            unsafe_allow_html=True,
        )
        for item in (x for x in NAV_ITEMS if x.section == section):
            active = item.key == current
            label = f"{'▌ ' if active else ''}{item.icon}  {item.label}"
            if st.sidebar.button(
                label,
                key=f"nav_{item.key}",
                use_container_width=True,
                type="primary" if active else "secondary",
            ):
                selected = item.key
                st.session_state["atlas_page"] = item.key

    st.sidebar.markdown('<div style="height:.8rem"></div>', unsafe_allow_html=True)
    st.sidebar.markdown(
        '<div class="nav-section-label">System Status</div>',
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

    st.sidebar.markdown('<div style="height:.35rem"></div>', unsafe_allow_html=True)
    st.sidebar.caption("EOR Atlas • ScreenTool v3 • Hybrid decision stack")

    return selected
