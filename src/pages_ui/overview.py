"""Executive Overview page."""
from __future__ import annotations
import pandas as pd
import streamlit as st
from ui.components import insight_cards,kpi_cards,section_title
from ui.decision import view_mode
try: import pydeck as pdk
except Exception: pdk=None


def _find_column(df:pd.DataFrame,aliases:tuple[str,...])->str|None:
    normalized={str(c).strip().lower().replace("_"," "):c for c in df.columns}
    for alias in aliases:
        key=alias.strip().lower().replace("_"," ")
        if key in normalized:return normalized[key]
    return None


def _map_summary(map_df:pd.DataFrame)->tuple[pd.DataFrame,pd.DataFrame]:
    field_col=_find_column(map_df,("field","field name","field_name")); method_col=_find_column(map_df,("types of eor","eor method","eor_method","method")); lat_col=_find_column(map_df,("latitude","lat")); lon_col=_find_column(map_df,("longitude","long","lon","lng"))
    if not all([field_col,method_col,lat_col,lon_col]):return pd.DataFrame(),pd.DataFrame()
    work=map_df[[field_col,method_col,lat_col,lon_col]].copy(); work.columns=["Field","EOR Method","Latitude","Longitude"]; work["Field"]=work["Field"].astype(str).str.strip(); work["EOR Method"]=work["EOR Method"].astype(str).str.strip(); work["Latitude"]=pd.to_numeric(work["Latitude"],errors="coerce"); work["Longitude"]=pd.to_numeric(work["Longitude"],errors="coerce"); work=work[(work["Field"]!="")&(work["EOR Method"]!="")].copy()
    field_summary=work.dropna(subset=["Latitude","Longitude"]).groupby("Field",as_index=False).agg(Latitude=("Latitude","mean"),Longitude=("Longitude","mean"),Methods=("EOR Method","nunique")); method_table=work.groupby("EOR Method")["Field"].nunique().sort_values(ascending=False).rename("Fields").reset_index()
    if not method_table.empty and not field_summary.empty:method_table["Mapped Field Share (%)"]=(method_table["Fields"]/field_summary["Field"].nunique()*100).round(1)
    return field_summary,method_table


def _render_spatial_snapshot(map_df:pd.DataFrame)->None:
    section_title("Portfolio Snapshot","Geography first, then field-level EOR evidence."); fields,methods=_map_summary(map_df)
    if fields.empty:st.warning("The workbook map sheet does not contain the expected field and coordinate structure.");return
    c1,c2,c3=st.columns(3); c1.metric("Mapped fields",len(fields)); c2.metric("EOR methods",int(methods["EOR Method"].nunique()) if not methods.empty else 0); c3.metric("Mapped coordinates",int(map_df.shape[0]))
    left,right=st.columns([2.2,1])
    with left:
        mode=st.radio("Spatial view",["Heatmap","Scatter"],horizontal=True,key="overview_spatial_mode"); focus_options=["All fields"]+sorted(fields["Field"].tolist(),key=str.casefold); focus=st.selectbox("Field focus",focus_options,key="overview_spatial_focus"); visible=fields if focus=="All fields" else fields.loc[fields["Field"]==focus]; center_lat=float(visible["Latitude"].mean()); center_lon=float(visible["Longitude"].mean())
        if pdk is None:st.info("PyDeck is not available for the spatial view.")
        elif mode=="Heatmap":
            layer=pdk.Layer("HeatmapLayer",data=visible,get_position="[Longitude, Latitude]",get_weight="Methods",radius_pixels=55,intensity=1.1,threshold=0.08); st.pydeck_chart(pdk.Deck(map_style="light",initial_view_state=pdk.ViewState(latitude=center_lat,longitude=center_lon,zoom=5.0 if len(visible)<10 else 4.4,pitch=12),layers=[layer]),use_container_width=True,height=520); st.caption("Heat intensity represents EOR-method coverage concentration by mapped field.")
        else:
            layer=pdk.Layer("ScatterplotLayer",data=visible,get_position="[Longitude, Latitude]",get_radius=12000,radius_min_pixels=5,radius_max_pixels=18,get_fill_color="[0,161,156,200]",pickable=True,auto_highlight=True); tooltip={"html":"<b>{Field}</b><br/>Distinct EOR methods: {Methods}","style":{"backgroundColor":"#182230","color":"white"}}; st.pydeck_chart(pdk.Deck(map_style="light",initial_view_state=pdk.ViewState(latitude=center_lat,longitude=center_lon,zoom=5.0 if len(visible)<10 else 4.4,pitch=5),layers=[layer],tooltip=tooltip),use_container_width=True,height=520); st.caption("Each point is a mapped field. Hover to inspect EOR-method breadth.")
    with right:
        section_title("EOR Method Coverage","Unique mapped fields associated with each method."); st.dataframe(methods,use_container_width=True,hide_index=True,height=520) if not methods.empty else st.info("No EOR method records are available.")


def render()->None:
    import app_2 as _app
    workbook=_app.WorkbookRepository.load_workbook(); df=workbook.get("PROP_updatedNov25_v2") if isinstance(workbook,dict) else None; map_df=workbook.get("map") if isinstance(workbook,dict) else None
    fields=int(df["Field"].nunique()) if isinstance(df,pd.DataFrame) and "Field" in df.columns else 0; reservoirs=len(df) if isinstance(df,pd.DataFrame) else 0; rf_gap_total=pd.to_numeric(df["RF Gap"],errors="coerce").sum() if isinstance(df,pd.DataFrame) and "RF Gap" in df.columns else None; mapped,methods=_map_summary(map_df) if isinstance(map_df,pd.DataFrame) else (pd.DataFrame(),pd.DataFrame())
    kpi_cards([("Fields",fields,"Portfolio coverage"),("Reservoirs",reservoirs,"Screening universe"),("Mapped fields",len(mapped),"Coordinate-enriched map"),("EOR methods",int(methods["EOR Method"].nunique()) if not methods.empty else 0,"Mapped taxonomy"),("RF Gap","—" if rf_gap_total is None else f"{rf_gap_total:,.1f}","Workbook aggregate")]); st.markdown("<div class='atlas-divider'></div>",unsafe_allow_html=True)
    mode=view_mode("overview_view_mode"); portfolio_tab,signals_tab,journey_tab=st.tabs(["Portfolio Snapshot","Opportunity Signals","Decision Journey"])
    with portfolio_tab:
        if isinstance(map_df,pd.DataFrame) and not map_df.empty:_render_spatial_snapshot(map_df)
        else:st.info("The workbook map sheet is unavailable in this session.")
    with signals_tab:
        left,right=st.columns([1.4,1])
        with left:
            section_title("Opportunity Concentration","Use field aggregation as a prioritisation signal, then validate at reservoir level.")
            if isinstance(df,pd.DataFrame) and not df.empty and {"Field","RF Gap"}.issubset(df.columns):
                temp=df[["Field","RF Gap"]].copy(); temp["RF Gap"]=pd.to_numeric(temp["RF Gap"],errors="coerce"); ranked=temp.dropna().groupby("Field")["RF Gap"].sum().sort_values(ascending=False).reset_index()
                try:
                    import altair as alt
                    chart=alt.Chart(ranked.head(12)).mark_bar().encode(x=alt.X("RF Gap:Q",title="Aggregate RF Gap"),y=alt.Y("Field:N",sort="-x",title=None),tooltip=["Field",alt.Tooltip("RF Gap:Q",format=",.1f")]).properties(height=440).interactive(); st.altair_chart(chart,use_container_width=True)
                except Exception:st.dataframe(ranked.head(12),use_container_width=True,hide_index=True)
            else:st.info("Field RF-gap data is unavailable.")
        with right:
            section_title("Next Decision","The dashboard should tell the user where to go next.")
            if mode=="Leadership":
                insight_cards([("01","Prioritise","Start with the strongest field-level recovery-gap signals."),("02","Shortlist","Open EOR Candidates and retain reservoirs for comparison."),("03","Validate","Run Engineering Screening before any hybrid recommendation.")])
            else:
                insight_cards([("01","Discover","Narrow candidate reservoirs and locate portfolio concentration."),("02","Screen","Run the deterministic engineering gate on a selected reservoir."),("03","Decide","Use hybrid intelligence only after engineering feasibility is established.")])
    with journey_tab:
        section_title("Decision Journey","A consistent evidence chain across the application.")
        journey=pd.DataFrame({"Stage":["Portfolio","Candidates","Engineering Gate","Hybrid Intelligence","Insights"],"User goal":["Where is opportunity?","Which reservoir should I review?","Is it technically feasible?","Which method ranks highest?","What should I do next?"]}); st.dataframe(journey,use_container_width=True,hide_index=True)
