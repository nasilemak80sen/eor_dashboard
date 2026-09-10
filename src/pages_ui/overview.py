"""Executive Overview page."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from ui.components import insight_cards, kpi_cards, section_title


def render() -> None:
    import app_2 as _app

    workbook = _app.WorkbookRepository.load_workbook()
    df = workbook.get("PROP_updatedNov25_v2") if isinstance(workbook, dict) else None

    fields = 41
    reservoirs = 600
    rf_gap_total = None
    cr_total = None
    if isinstance(df, pd.DataFrame) and not df.empty:
        fields = int(df["Field"].nunique()) if "Field" in df.columns else fields
        reservoirs = len(df)
        if "RF Gap" in df.columns:
            rf_gap_total = pd.to_numeric(df["RF Gap"], errors="coerce").sum()
        if "CR volume potential" in df.columns:
            cr_total = pd.to_numeric(df["CR volume potential"], errors="coerce").sum()

    kpi_cards([
        ("Fields", fields, "Portfolio coverage"),
        ("Reservoirs", reservoirs, "Screening universe"),
        ("Potential Candidates", 18, "Current opportunity pool"),
        ("Historical Studies", 128, "Knowledge base"),
        ("RF Gap", "—" if rf_gap_total is None else f"{rf_gap_total:,.1f}", "Workbook aggregate"),
    ])

    st.markdown("<div class='atlas-divider'></div>", unsafe_allow_html=True)
    col1, col2 = st.columns([1.7, 1])
    with col1:
        section_title("Portfolio Snapshot", "High-level reservoir population and recovery opportunity signals.")
        if isinstance(df, pd.DataFrame) and not df.empty:
            chart_cols = [c for c in ["RF Gap", "CR volume potential"] if c in df.columns]
            if chart_cols:
                chart = df[chart_cols].apply(pd.to_numeric, errors="coerce").dropna(how="all").reset_index(drop=True)
                if not chart.empty:
                    st.line_chart(chart.head(100))
                else:
                    st.info("No plottable portfolio opportunity values are currently available.")
            else:
                st.info("Portfolio opportunity columns are unavailable in the loaded workbook.")
        else:
            st.info("The portfolio workbook is not available for this overview session.")
    with col2:
        section_title("What to do next", "Use the sidebar workflow to move from discovery to decision.")
        insight_cards([
            ("DISCOVER", "Find candidates", "Narrow the 600-reservoir population using the interactive candidate explorer."),
            ("SCREEN", "Run the engineering gate", "Test the selected reservoir against the deterministic ScreenTool v3 criteria."),
            ("DECIDE", "Review hybrid ranking", "Combine the engineering result and CatBoost probabilities through Decision Fusion."),
        ])

    st.markdown("<div class='atlas-divider'></div>", unsafe_allow_html=True)
    col3, col4 = st.columns(2)
    with col3:
        section_title("Opportunity Concentration", "Where recovery-gap signals are concentrated by field.")
        if isinstance(df, pd.DataFrame) and not df.empty and "Field" in df.columns and "RF Gap" in df.columns:
            field_gap = df.assign(**{"RF Gap": pd.to_numeric(df["RF Gap"], errors="coerce")}).groupby("Field")["RF Gap"].sum().sort_values(ascending=False).head(10)
            st.bar_chart(field_gap)
        else:
            st.info("Field RF-gap data is unavailable.")
    with col4:
        section_title("Decision Journey", "A simple workflow keeps engineering evidence ahead of recommendation.")
        journey = pd.DataFrame({
            "Stage": ["Portfolio", "Candidates", "Engineering Gate", "Hybrid Intelligence", "Insights"],
            "Purpose": [
                "See where the opportunity is",
                "Identify reservoirs for review",
                "Test deterministic feasibility",
                "Rank methods with ML support",
                "Translate results into actions",
            ],
        })
        st.dataframe(journey, use_container_width=True, hide_index=True)
