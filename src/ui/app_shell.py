"""Application shell helpers for EOR Atlas."""

from __future__ import annotations

import streamlit as st

from ui.components import page_header
from ui.navigation import render_sidebar, render_top_nav
from ui.theme import inject_theme


def initialize_ui() -> None:
    """Apply the visual system before rendering page content."""
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
        .atlas-top-nav-shell {
            position:sticky;
            top:0;
            z-index:999;
            background:rgba(247,248,250,.97);
            border-bottom:1px solid #E4E7EC;
            padding:.45rem 0 .55rem;
            margin:0 0 .85rem;
            backdrop-filter:blur(10px);
        }
        .atlas-top-nav-kicker {
            color:#667085;
            font-size:.58rem;
            font-weight:700;
            letter-spacing:.12em;
            text-transform:uppercase;
            margin:0 0 .3rem .1rem;
        }
        .atlas-top-nav-shell div[data-testid="stButton"] > button {
            min-height:2.2rem;
            padding:.35rem .5rem;
            border-radius:999px;
            font-size:.72rem;
            font-weight:650;
            white-space:nowrap;
            box-shadow:none;
        }
        .atlas-top-nav-shell div[data-testid="stButton"] > button[kind="secondary"] {
            background:#fff;
            color:#475467;
            border-color:#D0D5DD;
        }
        .atlas-top-nav-shell div[data-testid="stButton"] > button[kind="secondary"]:hover {
            background:#F9FAFB;
            color:#182230;
            border-color:#98A2B3;
        }
        .atlas-top-nav-shell div[data-testid="stButton"] > button[kind="primary"] {
            background:#EAF7F6;
            color:#0F4B4A;
            border-color:#8ED3CF;
            box-shadow:0 2px 6px rgba(0,161,156,.08);
        }
        .atlas-top-nav-shell div[data-testid="stButton"] > button[kind="primary"]:hover {
            background:#DFF4F2;
            color:#0F4B4A;
            border-color:#71C7C1;
        }
        @media(max-width:1100px) {
            .atlas-top-nav-shell { position:relative; }
            .atlas-top-nav-shell div[data-testid="stHorizontalBlock"] { flex-wrap:wrap; }
            .atlas-top-nav-shell div[data-testid="stButton"] > button { font-size:.68rem; }
        }
        @media(max-width:900px) {
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
    """Render primary top navigation and keep sidebar secondary."""
    render_sidebar(system_state=system_state)
    return render_top_nav()


def render_page_intro(kicker: str, title: str, subtitle: str) -> None:
    page_header(kicker, title, subtitle)
