"""Application shell helpers for EOR Atlas."""

from __future__ import annotations

import streamlit as st

from ui.components import page_header
from ui.navigation import render_sidebar
from ui.theme import inject_theme


def initialize_ui() -> None:
    """Apply the visual system before rendering page content."""
    inject_theme()
    st.markdown(
        """
        <style>
        /* Shared UX polish: keep status text readable on light surfaces. */
        .status-strip > span:first-child { color:#344054 !important; }
        .status-strip { background:#F6FBFA !important; }
        .stTabs [role="tab"] { padding:.72rem 1rem; border-radius:10px 10px 0 0; }
        .stTabs [role="tab"] p { font-weight:650; }
        .stTabs [role="tab"][aria-selected="true"] { background:#EAF7F6; color:#0F4B4A; }
        div[data-testid="stVerticalBlock"] > div:has(> div[data-testid="stHorizontalBlock"]) { min-width:0; }
        @media (max-width:900px) {
            .page-title { font-size:1.55rem !important; }
            .page-subtitle { font-size:.86rem !important; }
            .block-container { padding-left:1rem !important; padding-right:1rem !important; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_shell_header() -> None:
    st.markdown(
        """
        <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:1rem;margin-bottom:1rem;">
            <div>
                <div style="font-size:.7rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:#00A19C;">PETRONAS RESERVOIR ENGINEERING</div>
                <div style="font-size:.82rem;color:#64748B;margin-top:.2rem;">EOR Atlas • Enhanced Oil Recovery Decision Support</div>
            </div>
            <div style="padding:.42rem .7rem;border:1px solid #E2E8F0;border-radius:999px;background:#fff;color:#64748B;font-size:.68rem;font-weight:600;">ScreenTool v3</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def select_page(system_state: dict[str, bool]) -> str:
    return render_sidebar(system_state=system_state)


def render_page_intro(kicker: str, title: str, subtitle: str) -> None:
    page_header(kicker, title, subtitle)
