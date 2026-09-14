"""Portfolio EOR Insights page."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from ui.components import insight_cards, kpi_cards, section_title


def render(services: dict) -> None:
    workbook = services.get("workbook_sheets") or {}
    df = workbook.get("PROP_updatedNov25_v2") if isinstance(workbook, dict) else None

    analytics_tab, action_tab = st.tabs(["Opportunity Signals", "Recommended Actions"])
    with analytics_tab:
        if not isinstance(df, pd.DataFrame) or df.empty:
            st.info("Portfolio workbook analytics are unavailable in this session; Candidates and Screening remain available.")
            return

        rows = len(df)
        fields = int(df["Field"].nunique()) if "Field" in df.columns else 0
        rf = pd.to_numeric(df["RF Gap"], errors="coerce") if "RF Gap" in df.columns else pd.Series(dtype=float)
        cr_col = "CR volume potential" if "CR volume potential" in df.columns else "CR volume potential = RF Gap x STOIIP  (MMSTB)"
        cr = pd.to_numeric(df[cr_col], errors="coerce") if cr_col in df.columns else pd.Series(dtype=float)
        kpi_cards([
            ("Reservoirs", rows, "Current portfolio universe"),
            ("Fields", fields, "Distinct fields represented"),
            ("RF Gap", "—" if rf.dropna().empty else f"{rf.sum():,.1f}", "Aggregate recovery-gap signal"),
            ("CR Potential", "—" if cr.dropna().empty else f"{cr.sum():,.1f}", "Aggregate opportunity signal"),
        ])
        st.markdown("<div class='atlas-divider'></div>", unsafe_allow_html=True)

        left, right = st.columns([1.35, 1])
        with left:
            section_title("Opportunity Distribution", "Use the distribution to understand the breadth of recovery-gap opportunity before field prioritisation.")
            if not rf.dropna().empty:
                chart_df = pd.DataFrame({"Reservoir Rank": range(1, len(rf.dropna()) + 1), "RF Gap": rf.dropna().sort_values().reset_index(drop=True)})
                try:
                    import altair as alt
                    chart = alt.Chart(chart_df).mark_line().encode(x=alt.X("Reservoir Rank:Q", title="Reservoir rank"), y=alt.Y("RF Gap:Q", title="RF Gap"), tooltip=[alt.Tooltip("Reservoir Rank:Q"), alt.Tooltip("RF Gap:Q", format=",.1f")]).interactive()
                    st.altair_chart(chart, use_container_width=True)
                except Exception:
                    st.line_chart(chart_df.set_index("Reservoir Rank"))
        with right:
            section_title("Field Prioritisation", "Use the ranked field view to identify where the signal is concentrated.")
            if {"Field", "RF Gap"}.issubset(df.columns):
                ranked = df[["Field", "RF Gap"]].copy()
                ranked["RF Gap"] = pd.to_numeric(ranked["RF Gap"], errors="coerce")
                ranked = ranked.dropna().groupby("Field", as_index=False)["RF Gap"].sum().sort_values("RF Gap", ascending=False).head(12)
                try:
                    import altair as alt
                    chart = alt.Chart(ranked).mark_bar().encode(x=alt.X("RF Gap:Q", title="Aggregate RF Gap"), y=alt.Y("Field:N", sort="-x", title=None), tooltip=["Field", alt.Tooltip("RF Gap:Q", format=",.1f")]).properties(height=420).interactive()
                    st.altair_chart(chart, use_container_width=True)
                except Exception:
                    st.dataframe(ranked, use_container_width=True, hide_index=True)

        st.divider()
        section_title("Decision Signals", "A portfolio signal is not yet an EOR recommendation; the next step is engineering validation.")
        insight_cards([
            ("HIGH GAP", "Prioritise the tail", "Start with fields/reservoirs carrying the strongest recovery-gap signal, then validate data quality."),
            ("SPATIAL", "Check concentration", "Use Candidate Location to see whether opportunity is clustered geographically."),
            ("ENGINEERING", "Validate feasibility", "Move selected reservoirs into the deterministic Engineering Gate before hybrid ranking."),
        ])

    with action_tab:
        section_title("Recommended Action Path", "Keep the next action tied to evidence already visible in the dashboard.")
        actions = pd.DataFrame({
            "Priority": ["1", "2", "3"],
            "Action": ["Identify high-opportunity reservoirs", "Run deterministic EOR screening", "Review hybrid recommendation and engineering basis"],
            "Decision Owner": ["Reservoir Engineering", "EOR / Reservoir Engineering", "EOR / Reservoir Engineering"],
            "Dashboard hand-off": ["EOR Candidates", "EOR Screening", "Hybrid Intelligence"],
        })
        st.dataframe(actions, use_container_width=True, hide_index=True)
