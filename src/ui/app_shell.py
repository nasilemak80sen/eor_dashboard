"""Application shell helpers for EOR Atlas."""

from __future__ import annotations

from typing import Any

import streamlit as st

from ui.components import page_header
from ui.navigation import render_sidebar
from ui.theme import inject_theme


def initialize_ui() -> None:
    """Apply the visual system before rendering page content."""
    inject_theme()


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
