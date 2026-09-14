"""EOR Candidates page with a reactive portfolio/location workspace."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from ui.components import insight_cards, reset_button, section_title

try:
    import pydeck as pdk
except Exception:
    pdk = None


def _render_reactive_location_map(dataframe: pd.DataFrame) -> None:
    st.subheader("Candidate Location")
    st.caption("Longitude = X · Latitude = Y. Switch between Heatmap for spatial concentration and Scatter for reservoir-level inspection.")
    if pdk is None:
        st.info("PyDeck is not available, so the location visualization cannot be rendered.")
        return

    required = {"LATITUDE", "LONGITUDE", "Field"}
    missing = sorted(required - set(dataframe.columns))
    if missing:
        st.warning(f"Location view is missing required columns: {', '.join(missing)}")
        return

    map_df = dataframe.copy()
    map_df["LATITUDE"] = pd.to_numeric(map_df["LATITUDE"], errors="coerce")
    map_df["LONGITUDE"] = pd.to_numeric(map_df["LONGITUDE"], errors="coerce")
    map_df = map_df.dropna(subset=["LATITUDE", "LONGITUDE", "Field"]).copy()
    if map_df.empty:
        st.info("No candidate coordinates remain after the current filters.")
        return
    map_df["Field"] = map_df["Field"].astype(str).str.strip()
    map_df = map_df[map_df["Field"] != ""].copy()

    c1, c2, c3 = st.columns([1.05, 1.15, 2.8])
    with c1:
        view_mode = st.radio("Map view", ["Heatmap", "Scatter"], horizontal=True, key="candidate_location_view_mode")
    fields = ["All fields"] + sorted(map_df["Field"].unique().tolist(), key=str.casefold)
    with c2:
        focus = st.selectbox("Field focus", fields, key="candidate_location_focus")
    with c3:
        st.markdown(f"**{len(map_df):,} reservoirs** · **{map_df['Field'].nunique():,} fields** · **{len(map_df.dropna(subset=['LATITUDE', 'LONGITUDE'])):,} mapped**")

    visible = map_df if focus == "All fields" else map_df.loc[map_df["Field"] == focus].copy()
    if visible.empty:
        st.info("No mapped reservoirs are available for the selected field.")
        return

    visible["CR_Potential"] = pd.to_numeric(visible.get("CR volume potential = RF Gap x STOIIP  (MMSTB)"), errors="coerce").fillna(0.0)
    visible["STOIIP"] = pd.to_numeric(visible.get("STOIIP_ARPR 1.1.2025"), errors="coerce").fillna(0.0)
    center_lat = float(visible["LATITUDE"].mean())
    center_lon = float(visible["LONGITUDE"].mean())
    tooltip = {
        "html": "<b>{Field}</b><br/>Reservoir: {Reservoir}<br/>Temp: {Temp (deg C)} °C<br/>Oil API: {Oil API}<br/>Permeability: {Avg Permeability (mD)} mD<br/>STOIIP: {STOIIP_ARPR 1.1.2025} MMSTB<br/>CR Potential: {CR_Potential} MMSTB",
        "style": {"backgroundColor": "#182230", "color": "white"},
    }

    if view_mode == "Heatmap":
        layer = pdk.Layer("HeatmapLayer", data=visible, get_position="[LONGITUDE, LATITUDE]", get_weight="STOIIP", radius_pixels=38, intensity=1.1, threshold=0.08, aggregation="SUM", pickable=True)
        caption = "Heat intensity is weighted by STOIIP, showing where portfolio volume is concentrated without overlapping bars."
        pitch = 18
    else:
        layer = pdk.Layer("ScatterplotLayer", data=visible, get_position="[LONGITUDE, LATITUDE]", get_radius=1800, radius_min_pixels=4, radius_max_pixels=14, get_fill_color=[0, 161, 156, 190], get_line_color=[255, 255, 255, 190], line_width_min_pixels=1, pickable=True, auto_highlight=True)
        caption = "Each point represents an individual reservoir coordinate. Hover a point for engineering context."
        pitch = 5

    st.pydeck_chart(pdk.Deck(map_style="light", initial_view_state=pdk.ViewState(latitude=center_lat, longitude=center_lon, zoom=5.0 if len(visible) < 120 else 4.4, pitch=pitch), layers=[layer], tooltip=tooltip), use_container_width=True, height=600)
    st.caption(caption)

    field_summary = visible.groupby("Field", as_index=False).agg(Reservoirs=("Reservoir", "nunique"), STOIIP=("STOIIP", "sum"), CR_Potential=("CR_Potential", "sum")).sort_values("STOIIP", ascending=False)
    table_col, note_col = st.columns([2.5, 1])
    with table_col:
        display = field_summary.copy()
        display.columns = ["Field", "Reservoirs", "STOIIP (MMSTB)", "CR Potential (MMSTB)"]
        display["STOIIP (MMSTB)"] = display["STOIIP (MMSTB)"].round(1)
        display["CR Potential (MMSTB)"] = display["CR Potential (MMSTB)"].round(1)
        st.dataframe(display, use_container_width=True, hide_index=True, height=min(340, 78 + len(display) * 38))
    with note_col:
        st.markdown("**Map reading**\n\nHeatmap = spatial concentration.\n\nScatter = reservoir-level detail.\n\nField focus = isolate one field.\n\nEvery map update uses the same candidate filters above.")


def render() -> None:
    import app_2 as _app
    from candidate_analytics import ui as candidate_ui

    insight_cards([
        ("FILTER", "Narrow the portfolio", "Filter by fluid, production state and engineering ranges; downstream visuals update from the same filtered set."),
        ("RELATE", "Understand relationships", "Compare engineering properties with the interactive scatter plot and Field grouping."),
        ("LOCATE", "See spatial concentration", "Use Heatmap for portfolio concentration or Scatter for reservoir-level location visibility."),
    ])
    st.markdown("<div class='atlas-divider'></div>", unsafe_allow_html=True)

    explore_tab, definitions_tab = st.tabs(["Candidate Explorer", "Data & Definitions"])
    with explore_tab:
        action_col, _ = st.columns([1, 4])
        with action_col:
            reset_button("↺ Reset explorer", prefixes="candidate_", key="candidates_reset_explorer")
        section_title("Candidate Explorer", "Portfolio discovery only — no Excel Gate, fuzzy suitability or ML is executed here.")
        try:
            candidate_ui._render_candidate_map = _render_reactive_location_map
            candidate_ui.render_field_reservoir_parameters_tab()
        except Exception as exc:
            _app.logger.exception("Candidate analytics failed")
            st.error(f"Candidate analytics could not be rendered: {exc}")

    with definitions_tab:
        section_title("How to read this workspace", "Use this page to discover candidates and spatial patterns before engineering screening.")
        st.markdown("**Filters** control the complete candidate population.\n\n**Relationship Explorer** compares engineering properties; marker size represents CR volume potential.\n\n**Candidate Location** uses longitude/latitude and offers a Heatmap or reservoir-level Scatter view.\n\n**Selected Reservoir Detail** is the hand-off point for reviewing a candidate before EOR Screening.")
