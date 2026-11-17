"""Grouped sidebar navigation and live service-status display for EOR Atlas."""
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
    NavItem("ceor", "R&D", "🧪"),
    NavItem("system", "System", "⚙"),
)

NAV_GROUPS = (
    ("WORKSPACE", ("overview", "candidates")),
    ("ENGINEERING", ("screening", "intelligence", "insights")),
    ("KNOWLEDGE & R&D", ("historical", "ceor", "challenges")),
    ("GOVERNANCE", ("system",)),
)
NAV_DISPLAY_LABELS = {
    "overview": "Overview", "candidates": "Portfolio Explorer",
    "screening": "EOR Screening", "intelligence": "Hybrid Intelligence",
    "insights": "EOR Insights", "historical": "Historical EOR",
    "challenges": "Challenges & Lessons", "ceor": "R&D Laboratory",
    "system": "System & Model",
}

def render_sidebar() -> None:
    """Render persistent product identity at the top of the sidebar."""
    st.sidebar.markdown(
        """
        <div class="atlas-brand">
            <div class="atlas-brand-mark">EA</div>
            <div>
                <div class="atlas-brand-title">EOR ATLAS</div>
                <div class="atlas-brand-subtitle">Subsurface Intelligence Platform</div>
            </div>
        </div>
        <div class="atlas-sidebar-caption">PETRONAS RESERVOIR ENGINEERING</div>
        """,
        unsafe_allow_html=True,
    )

def render_top_nav() -> str:
    """Compatibility name retained; renders grouped primary sidebar navigation."""
    current = st.session_state.get("atlas_page", "overview")
    item_by_key = {item.key: item for item in NAV_ITEMS}
    selected = current
    for group_label, keys in NAV_GROUPS:
        st.sidebar.markdown(f'<div class="nav-section-label">{group_label}</div>', unsafe_allow_html=True)
        for key in keys:
            item = item_by_key[key]
            label = NAV_DISPLAY_LABELS.get(key, item.label)
            if st.sidebar.button(
                f"{item.icon}  {label}",
                key=f"sidebar_nav_{item.key}",
                use_container_width=True,
                type="primary" if item.key == current else "secondary",
            ):
                selected = item.key
    if selected != current:
        st.session_state["atlas_page"] = selected
        st.rerun()
    return selected

def _status_state(*, workbook: bool, model: bool) -> list[tuple[str, str, str]]:
    if workbook and model:
        return [("Excel Gate", "READY", "status-ok"), ("CatBoost", "READY", "status-ok"), ("Decision Fusion", "READY", "status-ok")]
    if workbook or model:
        return [
            ("Excel Gate", "READY" if workbook else "CHECK", "status-ok" if workbook else "status-check"),
            ("CatBoost", "READY" if model else "CHECK", "status-ok" if model else "status-check"),
            ("Decision Fusion", "CHECK", "status-check"),
        ]
    return [("Excel Gate", "CHECK", "status-check"), ("CatBoost", "CHECK", "status-check"), ("Decision Fusion", "MISSING", "status-warning")]

def render_sidebar_status(*, system_state: dict[str, bool] | None = None) -> None:
    """Render status from the same runtime checks used by the application shell."""
    state = system_state or {}
    rows = _status_state(workbook=bool(state.get("workbook")), model=bool(state.get("model")))
    st.sidebar.markdown('<div class="nav-section-label">PLATFORM STATUS</div>', unsafe_allow_html=True)
    for label, status_text, status_class in rows:
        st.sidebar.markdown(
            f'<div class="sidebar-status-row"><span>{label}</span><span class="{status_class}">{status_text}</span></div>',
            unsafe_allow_html=True,
        )

def render_sidebar_status_legacy(*, system_state: dict[str, bool] | None = None) -> None:
    """Compatibility alias for legacy callers."""
    render_sidebar_status(system_state=system_state)
