"""Portfolio EOR Insights page."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from ui.components import kpi_cards, page_header, section_title


def render(services: dict) -> None:
    page_header(
        "Decision View",
        "EOR Insights",
        "Translate screening and portfolio data into an intuitive view of opportunity concentration and next actions.",
    )

    workbook = services.get("workbook_sheets") or {}
    df = workbook.get("PROP_updatedNov25_v2") if isinstance(workbook, dict) else None

    if isinstance(df, pd.DataFrame) and not df.empty:
        rows = len(df)
        fields = df.get("Field", pd.Series(dtype=object)).nunique()
        try:
            rf_gap = pd.to_numeric(df.get("RF Gap"), errors="coerce").sum()
        except Exception:
            rf_gap = None
        try:
            cr = pd.to_numeric(df.get("CR volume potential"), errors="coerce").sum()
        except Exception:
            cr = None
        kpi_cards([
            ("Reservoirs", rows, "Current portfolio universe"),
            ("Fields", fields, "Distinct fields represented"),
            ("RF Gap", "—" if rf_gap is None else f"{rf_gap:,.1f}", "Aggregate workbook indicator"),
            ("CR Potential", "—" if cr is None else f"{cr:,.1f}", "Workbook candidate potential"),
        ])

        st.markdown("<div class='atlas-divider'></div>", unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            section_title("RF Gap Distribution", "Where the portfolio appears to carry the largest recovery opportunity signal.")
            gap_col = "RF Gap"
            if gap_col in df.columns:
                chart_df = pd.DataFrame({gap_col: pd.to_numeric(df[gap_col], errors="coerce")}).dropna()
                if not chart_df.empty:
                    st.line_chart(chart_df.sort_values(gap_col).reset_index(drop=True))
                else:
                    st.info("RF Gap values are not available for a chart.")
            else:
                st.info("RF Gap column is not available in the loaded workbook.")
        with col2:
            section_title("Candidate Opportunity", "Reservoir counts by producing status from the candidate data source.")
            status_col = "Reservoir Producing Status"
            if status_col in df.columns:
                counts = df[status_col].fillna("Unknown").astype(str).value_counts()
                st.bar_chart(counts)
            else:
                st.info("Producing-status data is not available.")
    else:
        kpi_cards([
            ("Candidates", 18, "Current opportunity pool"),
            ("Techniques", 9, "Current ScreenTool taxonomy"),
            ("Priority", "Review", "Run screening for reservoir-level evidence"),
        ])
        st.info("Portfolio workbook analytics are unavailable in this session; the decision workflow remains available through Candidates and Screening.")

    st.markdown("<div class='atlas-divider'></div>", unsafe_allow_html=True)
    section_title("Recommended Action Path")
    actions = pd.DataFrame({
        "Priority": ["1", "2", "3"],
        "Action": ["Identify high-opportunity reservoirs", "Run deterministic EOR screening", "Review hybrid recommendation and engineering basis"],
        "Decision Owner": ["Reservoir Engineering", "EOR / Reservoir Engineering", "EOR / Reservoir Engineering"],
    })
    st.dataframe(actions, use_container_width=True, hide_index=True)
