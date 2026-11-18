"""EOR Candidates page with a reactive portfolio/location workspace."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from ui.components import page_header, reset_button



def _numeric_or_zero(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(0.0, index=frame.index, dtype="float64")
    return pd.to_numeric(frame[column], errors="coerce").fillna(0.0)


def _render_reactive_location_map(dataframe: pd.DataFrame) -> None:
    from ui.openglobus import render_openglobus_map

    st.subheader("Candidate Location")
    st.caption(
        "Interactive OpenGlobus 3D Earth. Longitude = X · Latitude = Y. "
        "Use Field focus to isolate a field; click a reservoir marker for engineering context."
    )

    required = {"LATITUDE", "LONGITUDE", "Field", "Reservoir"}
    missing = sorted(required - set(dataframe.columns))
    if missing:
        st.warning(f"Location view is missing required columns: {', '.join(missing)}")
        return

    map_df = dataframe.copy()
    map_df["LATITUDE"] = pd.to_numeric(map_df["LATITUDE"], errors="coerce")
    map_df["LONGITUDE"] = pd.to_numeric(map_df["LONGITUDE"], errors="coerce")
    map_df = map_df.dropna(subset=["LATITUDE", "LONGITUDE", "Field", "Reservoir"]).copy()
    map_df["Field"] = map_df["Field"].astype(str).str.strip()
    map_df["Reservoir"] = map_df["Reservoir"].astype(str).str.strip()
    map_df = map_df[(map_df["Field"] != "") & (map_df["Reservoir"] != "")]
    if map_df.empty:
        st.info("No candidate coordinates remain after the current filters.")
        return

    fields = ["All fields"] + sorted(map_df["Field"].unique().tolist(), key=str.casefold)
    focus = st.selectbox("Field focus", fields, key="candidate_location_focus")
    visible = map_df if focus == "All fields" else map_df.loc[map_df["Field"] == focus].copy()

    visible["CR_Potential"] = _numeric_or_zero(
        visible, "CR volume potential = RF Gap x STOIIP  (MMSTB)"
    )
    visible["STOIIP"] = _numeric_or_zero(visible, "STOIIP_ARPR 1.1.2025")

    st.markdown(
        f"**{len(visible):,} reservoirs** · **{visible['Field'].nunique():,} fields** · "
        f"**{visible[['LATITUDE','LONGITUDE']].dropna().shape[0]:,} mapped**"
    )

    render_openglobus_map(
        visible,
        latitude="LATITUDE",
        longitude="LONGITUDE",
        name="Reservoir",
        value="CR_Potential",
        value_label="CR Potential (MMSTB)",
        detail_columns=[
            ("Field", "Field"),
            ("Temperature", "Temp (deg C)"),
            ("Oil API", "Oil API"),
            ("Permeability", "Avg Permeability (mD)"),
            ("STOIIP (MMSTB)", "STOIIP"),
            ("CR Potential (MMSTB)", "CR_Potential"),
            ("Producing Status", "Reservoir Producing Status"),
            ("Injected Fluid", "Injected Fluid"),
        ],
        title="EOR Atlas · Candidate Reservoirs",
        subtitle="OpenGlobus 3D reservoir locations from the filtered candidate portfolio.",
        height=620,
        camera_height=5000000 if focus != "All fields" else 12000000,
        show_labels=False,
    )

    st.caption(
        "Marker size follows CR volume potential where available. "
        "Click a marker for reservoir-level engineering context."
    )

    field_summary = (
        visible.groupby("Field", as_index=False)
        .agg(
            Reservoirs=("Reservoir", "nunique"),
            STOIIP=("STOIIP", "sum"),
            CR_Potential=("CR_Potential", "sum"),
        )
        .sort_values("STOIIP", ascending=False)
    )
    table_col, note_col = st.columns([2.5, 1])
    with table_col:
        display = field_summary.copy()
        display.columns = ["Field", "Reservoirs", "STOIIP (MMSTB)", "CR Potential (MMSTB)"]
        display["STOIIP (MMSTB)"] = display["STOIIP (MMSTB)"].round(1)
        display["CR Potential (MMSTB)"] = display["CR Potential (MMSTB)"].round(1)
        st.dataframe(
            display,
            use_container_width=True,
            hide_index=True,
            height=min(340, 78 + len(display) * 38),
        )
    with note_col:
        st.markdown(
            "**Map reading**\n\n"
            "**Globe** = geographic context.\n\n"
            "**Marker** = individual reservoir.\n\n"
            "**Marker size** = CR potential.\n\n"
            "**Field focus** = isolate one field.\n\n"
            "Every map update uses the same candidate filters above."
        )


def render() -> None:
    import app_2 as _app
    from candidate_analytics import ui as candidate_ui

    page_header(
        "WORKSPACE / PORTFOLIO",
        "Candidates",
        "Discover reservoir opportunities, compare property relationships and inspect field locations before entering an engineering decision workflow.",
    )
    action_col, _ = st.columns([1, 5])
    with action_col:
        reset_button(
            "↺ Reset candidate filters",
            prefixes="candidate_",
            key="candidates_reset_explorer",
        )

    try:
        candidate_ui._render_candidate_map = _render_reactive_location_map
        candidate_ui.render_field_reservoir_parameters_tab(show_header=False)
    except Exception as exc:
        _app.logger.exception("Candidate analytics failed")
        st.error(f"Candidate analytics could not be rendered: {exc}")
