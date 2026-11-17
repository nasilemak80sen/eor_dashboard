"""Application shell, global search and presentation helpers for EOR Atlas."""
from __future__ import annotations
import streamlit as st
from ui.components import page_header
from ui.navigation import render_sidebar, render_sidebar_status, render_top_nav
from ui.theme import inject_theme

PAGE_SEARCH_ITEMS = (
    {"label": "Executive Overview", "page": "overview", "keywords": "portfolio overview map command centre"},
    {"label": "Portfolio Explorer", "page": "candidates", "keywords": "candidate reservoir field portfolio explorer"},
    {"label": "EOR Screening", "page": "screening", "keywords": "engineering gate excel screening"},
    {"label": "Hybrid Intelligence", "page": "intelligence", "keywords": "catboost model decision fusion hybrid"},
    {"label": "EOR Insights", "page": "insights", "keywords": "opportunity analytics prioritisation"},
    {"label": "Historical EOR", "page": "historical", "keywords": "knowledge history report card saved runs"},
    {"label": "R&D Laboratory", "page": "ceor", "keywords": "ceor chemical eor wag laboratory experiments"},
    {"label": "Challenges & Lessons", "page": "challenges", "keywords": "risk lessons challenge register"},
    {"label": "System & Model", "page": "system", "keywords": "health governance diagnostics model"},
)

def initialize_ui() -> None:
    """Apply the shared light-canvas, PETRONAS-inspired application styling."""
    inject_theme()
    st.markdown(
        """
        <style>
        .status-strip > span:first-child { color:#344054 !important; }
        .status-strip { background:#F6FBFA !important; }
        .stTabs [role="tab"] { padding:.72rem 1rem; border-radius:10px 10px 0 0; }
        .stTabs [role="tab"] p { font-weight:650; }
        .stTabs [role="tab"][aria-selected="true"] { background:#EAF7F6; color:#0F4B4A; }
        div[data-testid="stVerticalBlock"] > div:has(> div[data-testid="stHorizontalBlock"]) { min-width:0; }
        .atlas-shell-kicker { color:#00A19C;font-size:.68rem;font-weight:750;letter-spacing:.11em;text-transform:uppercase; }
        .atlas-shell-name { color:#19333C;font-size:.86rem;font-weight:650;margin-top:.18rem; }
        .atlas-shell-version { display:inline-block;padding:.42rem .7rem;border:1px solid #E2E8F0;border-radius:999px;background:#fff;color:#64748B;font-size:.68rem;font-weight:650;white-space:nowrap; }
        @media(max-width:900px) {
            .page-title { font-size:1.55rem !important; }
            .page-subtitle { font-size:.86rem !important; }
            .block-container { padding-left:1rem !important; padding-right:1rem !important; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

def _search_catalog(query: str, services: dict | None) -> list[dict]:
    """Search page destinations and the already-loaded portfolio register."""
    needle = query.strip().casefold()
    if not needle:
        return []
    results: list[dict] = []
    for item in PAGE_SEARCH_ITEMS:
        if needle in f"{item['label']} {item['keywords']}".casefold():
            results.append({"label": f"Page · {item['label']}", "page": item["page"], "kind": "page"})
    workbook = (services or {}).get("workbook_sheets", {})
    frame = workbook.get("PROP_updatedNov25_v2") if isinstance(workbook, dict) else None
    if frame is not None and hasattr(frame, "columns") and hasattr(frame, "iterrows"):
        columns = {str(column).strip().casefold(): column for column in frame.columns}
        field_column = columns.get("field")
        reservoir_column = columns.get("reservoir")
        if field_column is not None and reservoir_column is not None:
            subset = frame[[field_column, reservoir_column]].drop_duplicates()
            for _, row in subset.iterrows():
                field = str(row.get(field_column, "")).strip()
                reservoir = str(row.get(reservoir_column, "")).strip()
                if field.casefold() in {"", "nan", "none"}:
                    field = "Unspecified field"
                if reservoir.casefold() in {"", "nan", "none"}:
                    continue
                if needle in field.casefold() or needle in reservoir.casefold():
                    results.append({
                        "label": f"Reservoir · {field} / {reservoir}",
                        "page": "candidates", "kind": "reservoir",
                        "field": field, "reservoir": reservoir,
                    })
                if len(results) >= 20:
                    break
    return results[:20]

def _open_search_result(result: dict) -> None:
    st.session_state["atlas_page"] = result["page"]
    # Defer clearing the widget key until the next run, before st.text_input
    # is instantiated. This avoids Streamlit's post-instantiation state guard.
    st.session_state["_clear_atlas_global_search"] = True
    st.session_state.pop("atlas_global_search_result", None)
    if result.get("kind") == "reservoir":
        # Clear conflicting live filters so the searched record is visible immediately.
        for key in (
            "candidate_injected_fluid", "candidate_status", "candidate_api",
            "candidate_porosity", "candidate_perm", "candidate_temperature",
            "candidate_oil_column", "candidate_viscosity",
            "candidate_analytics_selected_reservoir",
        ):
            st.session_state.pop(key, None)
        st.session_state["candidate_global_search_selection"] = {
            "field": result.get("field"), "reservoir": result.get("reservoir"),
        }
    st.rerun()

def render_shell_header(services: dict | None = None) -> None:
    """Render top identity row and global page, field and reservoir search."""
    identity_col, search_col, version_col = st.columns([1.05, 2.3, 0.8], vertical_alignment="center")
    with identity_col:
        st.markdown(
            '<div class="atlas-shell-kicker">PETRONAS RESERVOIR ENGINEERING</div>'
            '<div class="atlas-shell-name">EOR Atlas · Subsurface Intelligence</div>',
            unsafe_allow_html=True,
        )
    with search_col:
        if st.session_state.pop("_clear_atlas_global_search", False):
            st.session_state["atlas_global_search_query"] = ""
            st.session_state.pop("atlas_global_search_result", None)
        query = st.text_input(
            "Global search", key="atlas_global_search_query",
            placeholder="Search pages, fields or reservoirs...",
            label_visibility="collapsed",
        )
    with version_col:
        st.markdown('<div class="atlas-shell-version">ScreenTool v3</div>', unsafe_allow_html=True)
    if query.strip():
        results = _search_catalog(query, services)
        if not results:
            st.caption("No matching pages, fields or reservoirs were found in the currently loaded portfolio register.")
            return
        labels = [item["label"] for item in results]
        selected_label = st.selectbox("Search results", labels, key="atlas_global_search_result", label_visibility="collapsed")
        selected = next(item for item in results if item["label"] == selected_label)
        if st.button("Open result", key="atlas_global_search_open", type="primary"):
            _open_search_result(selected)

def select_page(system_state: dict[str, bool]) -> str:
    """Render grouped sidebar and return the selected route."""
    render_sidebar()
    selected = render_top_nav()
    render_sidebar_status(system_state=system_state)
    return selected

def render_page_intro(kicker: str, title: str, subtitle: str) -> None:
    page_header(kicker, title, subtitle)
