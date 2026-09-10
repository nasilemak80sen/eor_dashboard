"""Portfolio EOR Insights page."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from ui.components import kpi_cards, section_title


def render(services: dict) -> None:
    workbook = services.get("workbook_sheets") or {}
    df = workbook.get("PROP_updatedNov25_v2") if isinstance(workbook, dict) else None

    analytics_tab, action_tab = st.tabs(["Opportunity Signals", "Recommended Actions"])

    with analytics_tab:
        if isinstance(df, pd.DataFrame) and not df.empty:
            rows = len(df)
            fields = int(df["Field"].nunique()) if "Field" in df.columns else 0
            rf_gap = pd.to_numeric(df["RF Gap"], errors="coerce").sum() if "RF Gap" in df.columns else None
            cr = pd.to_numeric(df["CR volume potential"], errors="coerce").sum() if "CR volume potential" in df.columns else None
            kpi_cards([
                ("Reservoirs", rows, "Current portfolio universe"),
                ("Fields", fields, "Distinct fields represented"),
                ("RF Gap", "—" if rf_gap is None else f"{rf_gap:,.1f}", "Workbook aggregate indicator"),
                ("CR Potential", "—" if cr is None else f"{cr:,.1f}", "Workbook opportunity indicator"),
            ])
            st.markdown("<div class='atlas-divider'></div>", unsafe_allow_html=True)
            col1, col2 = st.columns(2)
            with col1:
                section_title("RF Gap Distribution", "Sorted recovery-gap signal across the loaded reservoir population.")
                if "RF Gap" in df.columns:
                    chart_df = pd.to_numeric(df["RF Gap"], errors="coerce").dropna().sort_values().reset_index(drop=True)
                    st.line_chart(chart_df)
            with col2:
                section_title("Opportunity by Field", "Aggregate RF Gap by field for portfolio prioritisation.")
                if "Field" in df.columns and "RF Gap" in df.columns:
                    temp = df[["Field", "RF Gap"]].copy()
                    temp["RF Gap"] = pd.to_numeric(temp["RF Gap"], errors="coerce")
                    field_gap = temp.dropna(subset=["RF Gap"]).groupby("Field")["RF Gap"].sum().sort_values(ascending=False).head(12)
                    st.bar_chart(field_gap)
        else:
            st.info("Portfolio workbook analytics are unavailable in this session; Candidates and Screening remain available.")

    with action_tab:
        section_title("Recommended Action Path", "Move from portfolio opportunity to engineering evidence.")
        actions = pd.DataFrame({
            "Priority": ["1", "2", "3"],
            "Action": ["Identify high-opportunity reservoirs", "Run deterministic EOR screening", "Review hybrid recommendation and engineering basis"],
            "Decision Owner": ["Reservoir Engineering", "EOR / Reservoir Engineering", "EOR / Reservoir Engineering"],
        })
        st.dataframe(actions, use_container_width=True, hide_index=True)
