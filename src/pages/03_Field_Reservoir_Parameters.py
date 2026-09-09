"""Standalone Field / Reservoir Parameters page for src/app_2.py entrypoint."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from candidate_analytics.ui import render_field_reservoir_parameters_tab
from config.settings import settings


st.set_page_config(
    page_title="EOR Atlas — Field / Reservoir Parameters",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="collapsed",
)


render_field_reservoir_parameters_tab(
    workbook_path=str(Path(settings.workbook_path)),
)
