"""EOR Atlas — standalone Field / Reservoir Parameters explorer.

This Streamlit page is intentionally independent from the EOR Screening and
EOR Intelligence workflows. It only explores the engineering candidate
portfolio contained in the workbook.
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

# Make the existing src package importable when this page is launched by
# Streamlit from the repository root.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from candidate_analytics.ui import render_field_reservoir_parameters_tab
from config.settings import settings


st.set_page_config(
    page_title="EOR Atlas — Field / Reservoir Parameters",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="collapsed",
)


render_field_reservoir_parameters_tab(
    workbook_path=str(settings.workbook_path),
)
