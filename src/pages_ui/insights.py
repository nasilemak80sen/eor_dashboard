"""Portfolio EOR Insights page."""
from __future__ import annotations
import pandas as pd
import streamlit as st
from ui.components import insight_cards,kpi_cards,section_title
from ui.decision import view_mode


def render(services:dict)->None:
    workbook=services.get("workbook_sheets") or {}; df=workbook.get("PROP_updatedNov25_v2") if isinstance(workbook,dict) else None
    if not isinstance(df,pd.DataFrame) or df.empty:
        st.info("Portfolio workbook analytics are unavailable in this session; Candidates and Screening remain available."); return
    mode=view_mode("insights_view_mode")
    rows=len(df); fields=int(df["Field"].nunique()) if "Field" in df.columns else 0; rf=pd.to_numeric(df["RF Gap"],errors="coerce") if "RF Gap" in df.columns else pd.Series(dtype=float); cr_col="CR volume potential" if "CR volume potential" in df.columns else "CR volume potential = RF Gap x STOIIP  (MMSTB)"; cr=pd.to_numeric(df[cr_col],errors="coerce") if cr_col in df.columns else pd.Series(dtype=float)
    kpi_cards([("Reservoirs",rows,"Current portfolio universe"),("Fields",fields,"Distinct fields represented"),("RF Gap","—" if rf.dropna().empty else f"{rf.sum():,.1f}","Aggregate recovery-gap signal"),("CR Potential","—" if cr.dropna().empty else f"{cr.sum():,.1f}","Aggregate opportunity signal")]); st.markdown("<div class='atlas-divider'></div>",unsafe_allow_html=True)
    analytics_tab,action_tab=st.tabs(["Opportunity Signals","Recommended Actions"])
    with analytics_tab:
        left,right=st.columns([1.35,1])
        with left:
            section_title("Opportunity Distribution","Understand breadth before prioritising individual fields.")
            if not rf.dropna().empty:
                chart_df=pd.DataFrame({"Reservoir Rank":range(1,len(rf.dropna())+1),"RF Gap":rf.dropna().sort_values().reset_index(drop=True)})
                try:
                    import altair as alt
                    chart=alt.Chart(chart_df).mark_line().encode(x=alt.X("Reservoir Rank:Q",title="Reservoir rank"),y=alt.Y("RF Gap:Q",title="RF Gap"),tooltip=[alt.Tooltip("Reservoir Rank:Q"),alt.Tooltip("RF Gap:Q",format=",.1f")]).interactive(); st.altair_chart(chart,use_container_width=True)
                except Exception:st.line_chart(chart_df.set_index("Reservoir Rank"))
        with right:
            section_title("Field Prioritisation","Select the strongest portfolio signals, then validate them at reservoir level.")
            if {"Field","RF Gap"}.issubset(df.columns):
                ranked=df[["Field","RF Gap"]].copy(); ranked["RF Gap"]=pd.to_numeric(ranked["RF Gap"],errors="coerce"); ranked=ranked.dropna().groupby("Field",as_index=False)["RF Gap"].sum().sort_values("RF Gap",ascending=False).head(12)
                try:
                    import altair as alt
                    chart=alt.Chart(ranked).mark_bar().encode(x=alt.X("RF Gap:Q",title="Aggregate RF Gap"),y=alt.Y("Field:N",sort="-x",title=None),tooltip=["Field",alt.Tooltip("RF Gap:Q",format=",.1f")]).properties(height=420).interactive(); st.altair_chart(chart,use_container_width=True)
                except Exception:st.dataframe(ranked,use_container_width=True,hide_index=True)
        st.divider(); section_title("Decision Signals","Portfolio analytics identify where to investigate; they do not replace deterministic engineering screening.")
        if mode=="Leadership":
            insight_cards([("OPPORTUNITY","Prioritise concentration","Focus on fields carrying the strongest recovery-gap and volume signals."),("SHORTLIST","Move to candidates","Retain specific reservoirs for comparison before screening."),("DECISION","Validate first","Treat Engineering Screening as the feasibility gate before ML ranking.")])
        else:
            insight_cards([("HIGH GAP","Prioritise the tail","Start with fields/reservoirs carrying the strongest recovery-gap signal."),("SPATIAL","Check concentration","Use Candidate Location to see whether opportunity is clustered geographically."),("ENGINEERING","Validate feasibility","Move selected reservoirs into the deterministic Engineering Gate before hybrid ranking.")])
    with action_tab:
        section_title("Recommended Action Path","Every portfolio signal should lead to a concrete dashboard hand-off.")
        actions=pd.DataFrame({"Priority":["1","2","3","4"],"Action":["Identify high-opportunity reservoirs","Build a candidate shortlist","Run deterministic EOR screening","Review hybrid recommendation and engineering basis"],"Decision Owner":["Reservoir Engineering","Reservoir Engineering","EOR / Reservoir Engineering","EOR / Reservoir Engineering"],"Dashboard hand-off":["EOR Candidates","EOR Candidates","EOR Screening","Hybrid Intelligence"]})
        st.dataframe(actions,use_container_width=True,hide_index=True)
