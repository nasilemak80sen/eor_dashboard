from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

try:
    import pydeck as pdk
except Exception:
    pdk = None

from .analysis import CandidateAnalysis, GROUP_COLUMNS
from .repository import CandidateRepository, CandidateDataError


@st.cache_resource(show_spinner=False)
def get_candidate_repository(workbook_path: str) -> CandidateRepository:
    return CandidateRepository(workbook_path=workbook_path)


@st.cache_data(show_spinner=False)
def load_candidate_dataframe(workbook_path: str) -> pd.DataFrame:
    repository = CandidateRepository(workbook_path=workbook_path)
    return repository.load()


def _range_slider(
    analysis: CandidateAnalysis,
    label: str,
    column: str,
    key: str,
) -> tuple[float, float] | None:
    bounds = analysis.numeric_bounds(column)
    if bounds is None:
        st.caption(f"{label}: no usable data")
        return None

    low, high = bounds
    if low == high:
        st.number_input(
            label,
            value=low,
            disabled=True,
            key=f"{key}_fixed",
        )
        return low, high

    return st.slider(
        label,
        min_value=float(low),
        max_value=float(high),
        value=(float(low), float(high)),
        key=key,
    )


def _multiselect(
    analysis: CandidateAnalysis,
    label: str,
    column: str,
    key: str,
    default_all: bool = True,
) -> list[str]:
    options = analysis.categorical_options(column)
    default = options if default_all else []
    return st.multiselect(label, options, default=default, key=key)


def _safe_metric_value(value: Any, suffix: str = "") -> str:
    if value is None or pd.isna(value):
        return "—"

    try:
        value = float(value)

        if abs(value) >= 1_000_000:
            return f"{value / 1_000_000:,.1f}M{suffix}"

        if abs(value) >= 1_000:
            return f"{value / 1_000:,.1f}K{suffix}"

        return f"{value:,.1f}{suffix}"

    except (TypeError, ValueError):
        return str(value)


def _render_summary_cards(
    analysis: CandidateAnalysis,
    dataframe: pd.DataFrame,
) -> None:

    summary = analysis.opportunity_summary(dataframe)

    candidate_reservoirs = summary.get("reservoirs", 0)
    fields = summary.get("fields", 0)
    stoiip = summary.get("STOIIP_total")
    cr_potential = summary.get("CR potential_total")

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.markdown(
            f"""
            <div class="exec-kpi-card">
                <div class="exec-kpi-label">
                    🛢️ Candidate Reservoirs
                </div>
                <div class="exec-kpi-value">
                    {candidate_reservoirs:,}
                </div>
                <div class="exec-kpi-subtext">
                    Reservoirs in current portfolio
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c2:
        st.markdown(
            f"""
            <div class="exec-kpi-card">
                <div class="exec-kpi-label">
                    🗺️ Fields
                </div>
                <div class="exec-kpi-value">
                    {fields:,}
                </div>
                <div class="exec-kpi-subtext">
                    Fields represented
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c3:
        st.markdown(
            f"""
            <div class="exec-kpi-card">
                <div class="exec-kpi-label">
                    📦 STOIIP
                </div>
                <div class="exec-kpi-value">
                    {_safe_metric_value(stoiip)}
                </div>
                <div class="exec-kpi-subtext">
                    MMSTB in current dataset
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c4:
        st.markdown(
            f"""
            <div class="exec-kpi-card">
                <div class="exec-kpi-label">
                    🚀 CR Volume Potential
                </div>
                <div class="exec-kpi-value">
                    {_safe_metric_value(cr_potential)}
                </div>
                <div class="exec-kpi-subtext">
                    MMSTB potential opportunity
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _render_scatter(
    analysis: CandidateAnalysis,
    dataframe: pd.DataFrame,
    x_column: str,
    y_column: str,
    group_by: str,
) -> None:
    scatter = analysis.prepare_scatter(
        dataframe,
        x_column,
        y_column,
        group_by,
    )

    if scatter.empty:
        st.warning(
            "No plottable records remain for the selected X/Y parameters. "
            "Try widening the filters or choosing parameters with more complete data."
        )
        return

    if x_column == y_column:
        st.info("X and Y use the same parameter. The chart is shown as a diagonal relationship.")

    chart_df = scatter[["__x", "__y", "__group"]].copy()
    chart_df.columns = ["X", "Y", "Group"]
    chart_df["Label"] = scatter["Field & Reservoir "] if "Field & Reservoir " in scatter else ""
    chart_df["Field"] = scatter["Field"] if "Field" in scatter else ""
    chart_df["Reservoir"] = scatter["Reservoir"] if "Reservoir" in scatter else ""
    chart_df["CR Potential"] = scatter["__size"]

    # Altair is deliberately used here instead of Streamlit's convenience
    # chart APIs to avoid the Altair/Streamlit version-sensitive bar_chart path.
    try:
        import altair as alt

        selection = alt.selection_point(fields=["Group"], bind="legend")
        chart = (
            alt.Chart(chart_df)
            .mark_circle(opacity=0.72)
            .encode(
                x=alt.X("X:Q", title=analysis.axis_label(x_column)),
                y=alt.Y("Y:Q", title=analysis.axis_label(y_column)),
                color=alt.Color("Group:N", title=group_by),
                size=alt.Size(
                    "CR Potential:Q",
                    title="CR Volume Potential",
                    scale=alt.Scale(range=[40, 650]),
                ),
                tooltip=[
                    alt.Tooltip("Field:N", title="Field"),
                    alt.Tooltip("Reservoir:N", title="Reservoir"),
                    alt.Tooltip("Group:N", title=group_by),
                    alt.Tooltip("X:Q", title=analysis.axis_label(x_column), format=",.2f"),
                    alt.Tooltip("Y:Q", title=analysis.axis_label(y_column), format=",.2f"),
                    alt.Tooltip("CR Potential:Q", title="CR Potential", format=",.2f"),
                ],
            )
            .add_params(selection)
            .transform_filter(selection)
            .properties(height=560)
            .interactive()
        )
        st.altair_chart(chart, use_container_width=True)
    except Exception as exc:
        st.warning(f"Interactive scatter rendering was unavailable: {exc}")
        st.scatter_chart(chart_df[["X", "Y"]], x="X", y="Y", use_container_width=True)


def _render_candidate_map(dataframe: pd.DataFrame) -> None:
    """Render a reactive field-oriented 3D candidate location map.

    Spatial axes are always longitude (X) and latitude (Y). The categorical
    Z dimension is represented by the Field grouping: each field is rendered
    as a 3D column at its reservoir locations, with column height reflecting
    the number of visible reservoirs in that field. This keeps the map
    conceptually aligned with the scatter plot's Field grouping.
    """
    st.subheader("Candidate Location Map")
    st.caption(
        "X = Longitude · Y = Latitude · Z = Field grouping. "
        "Map updates automatically with the candidate filters above. "
        "Hover a field column to inspect its reservoir portfolio."
    )

    if pdk is None:
        st.info("PyDeck is not available. The analytical table remains fully available below.")
        return

    required = {"LATITUDE", "LONGITUDE", "Field"}
    missing = sorted(required.difference(dataframe.columns))
    if missing:
        st.warning(f"Candidate location mapping is missing required columns: {', '.join(missing)}")
        return

    map_df = dataframe.dropna(subset=["LATITUDE", "LONGITUDE", "Field"]).copy()
    if map_df.empty:
        st.info("No latitude/longitude values are available for the current filter selection.")
        return

    map_df["Field"] = map_df["Field"].astype(str).str.strip()
    map_df = map_df[map_df["Field"] != ""].copy()
    if map_df.empty:
        st.info("No named fields are available for the current map selection.")
        return

    map_df["CR_Potential"] = pd.to_numeric(
        map_df.get("CR volume potential = RF Gap x STOIIP  (MMSTB)"),
        errors="coerce",
    ).fillna(0.0)
    map_df["STOIIP"] = pd.to_numeric(
        map_df.get("STOIIP_ARPR 1.1.2025"),
        errors="coerce",
    ).fillna(0.0)

    field_summary = (
        map_df.groupby("Field", dropna=False)
        .agg(
            Reservoirs=("Reservoir", "nunique"),
            Records=("Field", "size"),
            STOIIP=("STOIIP", "sum"),
            CR_Potential=("CR_Potential", "sum"),
            Latitude=("LATITUDE", "mean"),
            Longitude=("LONGITUDE", "mean"),
        )
        .reset_index()
        .sort_values(["Reservoirs", "Field"], ascending=[False, True])
        .reset_index(drop=True)
    )

    focus_options = ["All fields"] + field_summary["Field"].tolist()
    control_col, info_col = st.columns([1.2, 2.8])
    with control_col:
        focus_field = st.selectbox(
            "Map focus",
            focus_options,
            key="candidate_map_focus",
            help="Focus the 3D map on one field or show the full filtered portfolio.",
        )

    visible = map_df if focus_field == "All fields" else map_df.loc[map_df["Field"] == focus_field].copy()
    visible_fields = field_summary if focus_field == "All fields" else field_summary.loc[field_summary["Field"] == focus_field].copy()

    with info_col:
        st.markdown(
            f"**{len(visible):,} reservoirs** across **{visible['Field'].nunique():,} field(s)** with coordinates in the current view."
        )

    if visible.empty:
        st.info("The selected field has no coordinates in the current filter selection.")
        return

    # Stable, field-level colours keep the map and scatter grouping visually coherent.
    palette = [
        [0, 161, 156, 220],
        [32, 65, 154, 220],
        [191, 215, 48, 230],
        [253, 185, 36, 230],
        [118, 63, 152, 220],
        [14, 116, 144, 220],
        [33, 150, 83, 220],
        [214, 93, 14, 220],
        [91, 33, 182, 220],
        [0, 120, 140, 220],
    ]
    field_order = {field: index for index, field in enumerate(field_summary["Field"].tolist())}
    visible["Field_Index"] = visible["Field"].map(field_order).fillna(0).astype(int)
    visible["Field_Color"] = visible["Field_Index"].map(lambda index: palette[index % len(palette)])

    visible = visible.merge(
        visible_fields[["Field", "Reservoirs"]],
        on="Field",
        how="left",
        suffixes=("", "_Field"),
    )
    visible["Z_Elevation"] = visible["Reservoirs"].fillna(1).clip(lower=1).astype(float) * 18000.0

    tooltip = {
        "html": (
            "<b>{Field}</b><br/>"
            "Reservoir: {Reservoir}<br/>"
            "Field reservoirs: {Reservoirs}<br/>"
            "Temperature: {Temp (deg C)} °C<br/>"
            "Oil API: {Oil API}<br/>"
            "Permeability: {Avg Permeability (mD)} mD<br/>"
            "STOIIP: {STOIIP_ARPR 1.1.2025} MMSTB<br/>"
            "CR Potential: {CR_Potential} MMSTB"
        ),
        "style": {"backgroundColor": "#182230", "color": "white"},
    }

    center_lat = float(visible["LATITUDE"].mean())
    center_lon = float(visible["LONGITUDE"].mean())

    layers = [
        pdk.Layer(
            "ColumnLayer",
            data=visible,
            get_position="[LONGITUDE, LATITUDE]",
            get_elevation="Z_Elevation",
            elevation_scale=1,
            radius=2200,
            get_fill_color="Field_Color",
            pickable=True,
            auto_highlight=True,
            material=True,
            coverage=0.85,
        ),
        pdk.Layer(
            "ScatterplotLayer",
            data=visible,
            get_position="[LONGITUDE, LATITUDE]",
            get_fill_color=[255, 255, 255, 235],
            get_radius=650,
            radius_min_pixels=3,
            radius_max_pixels=9,
            pickable=True,
        ),
    ]

    st.pydeck_chart(
        pdk.Deck(
            map_style="light",
            initial_view_state=pdk.ViewState(
                latitude=center_lat,
                longitude=center_lon,
                zoom=4.2 if len(visible_fields) > 1 else 5.2,
                pitch=48,
                bearing=0,
            ),
            tooltip=tooltip,
            layers=layers,
        ),
        use_container_width=True,
        height=620,
    )

    summary_display = visible_fields[["Field", "Reservoirs", "STOIIP", "CR_Potential"]].copy()
    summary_display.columns = ["Field", "Reservoirs", "STOIIP (MMSTB)", "CR Potential (MMSTB)"]
    summary_display["STOIIP (MMSTB)"] = summary_display["STOIIP (MMSTB)"].round(1)
    summary_display["CR Potential (MMSTB)"] = summary_display["CR Potential (MMSTB)"].round(1)
    summary_display = summary_display.sort_values("Reservoirs", ascending=False)

    table_col, note_col = st.columns([2.4, 1])
    with table_col:
        st.dataframe(
            summary_display,
            use_container_width=True,
            hide_index=True,
            height=min(360, 72 + 42 * len(summary_display)),
        )
    with note_col:
        st.markdown(
            "**How to read the map**\n\n"
            "**X** — longitude\n\n"
            "**Y** — latitude\n\n"
            "**Z / Field** — each field is represented by its own column and colour. Column height scales with the number of visible reservoirs in that field.\n\n"
            "**Dot** — individual reservoir coordinate.\n\n"
            "Use the map focus selector to isolate one field."
        )


def _render_detail_panel(dataframe: pd.DataFrame) -> None:
    if dataframe.empty:
        return

    st.subheader("Selected Reservoir Detail")
    labels = dataframe["Field & Reservoir "].fillna("").astype(str).tolist()
    selected_label = st.selectbox(
        "Select a reservoir",
        labels,
        key="candidate_analytics_selected_reservoir",
    )

    selected = dataframe.loc[
        dataframe["Field & Reservoir "].astype(str) == selected_label
    ].head(1)
    if selected.empty:
        return

    row = selected.iloc[0]
    cols = st.columns(4)
    detail_fields = [
        ("Field", "Field"),
        ("Reservoir", "Reservoir"),
        ("Temperature (°C)", "Temp (deg C)"),
        ("Oil API", "Oil API"),
        ("Avg Porosity", "Avg Porosity"),
        ("Avg Permeability (mD)", "Avg Permeability (mD)"),
        ("Oil Viscosity (cP)", "Oil Viscosity (cP)"),
        ("Oil Column (ft)", "Oil Column (ft)"),
        ("STOIIP (MMSTB)", "STOIIP_ARPR 1.1.2025"),
        ("EUR (MMSTB)", "EUR_ARPR 1.1.2026"),
        ("RF Gap (%)", "RF Gap =Benchmark  RF - Field RF (%) "),
        ("CR Potential (MMSTB)", "CR volume potential = RF Gap x STOIIP  (MMSTB)"),
        ("Oil Producers", "Oil Producers"),
        ("Injectors", "Injectors"),
        ("Injected Fluid", "Injected Fluid"),
        ("Status", "Reservoir Producing Status"),
    ]

    for index, (label, column) in enumerate(detail_fields):
        with cols[index % 4]:
            value = row.get(column)
            if isinstance(value, (int, float)) and not pd.isna(value):
                st.metric(label, f"{value:,.2f}")
            else:
                st.metric(label, "—" if pd.isna(value) else str(value))

    with st.expander("Full engineering record", expanded=False):
        st.dataframe(
            pd.DataFrame([row]).drop(
                columns=[c for c in ["__candidate_key"] if c in row.index],
                errors="ignore",
            ),
            use_container_width=True,
            hide_index=True,
        )


def render_field_reservoir_parameters_tab(
    workbook_path: str | None = None,
) -> None:
    """Field / Reservoir Candidate Analytics feature."""
    path = str(workbook_path or CandidateRepository().workbook_path)

    st.header("🎯 EOR Candidate Screening")
    st.caption(
        "Standalone portfolio exploration of field and reservoir properties. "
        "This module does not run EOR screening, fuzzy suitability, or machine learning."
    )

    try:
        dataframe = load_candidate_dataframe(path)
    except CandidateDataError as exc:
        st.error(str(exc))
        return
    except Exception as exc:
        st.error(f"Candidate analytics could not load the workbook: {exc}")
        return

    analysis = CandidateAnalysis(dataframe)
    _render_summary_cards(analysis, dataframe)

    st.divider()
    st.subheader("Candidate Filters")

    with st.expander("Filter candidates", expanded=True):
        row1 = st.columns(2)
        with row1[0]:
            fluids = _multiselect(
                analysis,
                "Injected Fluid",
                "Injected Fluid",
                "candidate_injected_fluid",
            )
        with row1[1]:
            statuses = _multiselect(
                analysis,
                "Reservoir Producing Status",
                "Reservoir Producing Status",
                "candidate_status",
            )

        row2 = st.columns(3)
        with row2[0]:
            api_range = _range_slider(analysis, "Oil API", "Oil API", "candidate_api")
        with row2[1]:
            porosity_range = _range_slider(
                analysis, "Avg Porosity", "Avg Porosity", "candidate_porosity"
            )
        with row2[2]:
            permeability_range = _range_slider(
                analysis,
                "Avg Permeability (mD)",
                "Avg Permeability (mD)",
                "candidate_perm",
            )

        row3 = st.columns(3)
        with row3[0]:
            temperature_range = _range_slider(
                analysis,
                "Temperature (°C)",
                "Temp (deg C)",
                "candidate_temperature",
            )
        with row3[1]:
            oil_column_range = _range_slider(
                analysis,
                "Oil Column (ft)",
                "Oil Column (ft)",
                "candidate_oil_column",
            )
        with row3[2]:
            viscosity_range = _range_slider(
                analysis,
                "Oil Viscosity (cP)",
                "Oil Viscosity (cP)",
                "candidate_viscosity",
            )

    filtered = analysis.filter(
        injected_fluids=fluids,
        statuses=statuses,
        oil_api=api_range,
        porosity=porosity_range,
        permeability=permeability_range,
        temperature_c=temperature_range,
        oil_column=oil_column_range,
        viscosity=viscosity_range,
    )

    st.caption(f"Showing **{len(filtered):,}** of **{len(dataframe):,}** reservoirs")

    if filtered.empty:
        st.warning("No reservoirs match the selected filters.")
        return

    st.divider()
    graph_tab, location_tab = st.tabs(["Relationship Explorer", "Candidate Location"])

    with graph_tab:
        st.subheader("Graph Properties")
        controls = st.columns(3)
        axis_options = analysis.axis_options()

        default_x = "Temp (deg C)" if "Temp (deg C)" in axis_options else axis_options[0]
        default_y = (
            "CR volume potential = RF Gap x STOIIP  (MMSTB)"
            if "CR volume potential = RF Gap x STOIIP  (MMSTB)" in axis_options
            else axis_options[min(1, len(axis_options) - 1)]
        )

        with controls[0]:
            x_column = st.selectbox(
                "X-Axis Parameter",
                axis_options,
                index=axis_options.index(default_x),
                format_func=analysis.axis_label,
                key="candidate_x_axis",
            )
        with controls[1]:
            y_column = st.selectbox(
                "Y-Axis Parameter",
                axis_options,
                index=axis_options.index(default_y),
                format_func=analysis.axis_label,
                key="candidate_y_axis",
            )
        with controls[2]:
            group_by = st.selectbox(
                "Z Axis / Group",
                list(GROUP_COLUMNS.keys()),
                index=list(GROUP_COLUMNS.keys()).index("Field"),
                key="candidate_group_by",
                help="Field is the recommended grouping when you want the relationship chart and location map to read consistently.",
            )

        st.caption(
            "Marker size represents CR volume potential. Use the legend to focus the selected Field/Reservoir grouping. "
            "For a field-to-location comparison, keep Z Axis / Group = Field."
        )
        _render_scatter(analysis, filtered, x_column, y_column, group_by)

    with location_tab:
        _render_candidate_map(filtered)

    st.divider()
    st.subheader("Candidate Reservoir Table")
    table = analysis.table_view(filtered)
    st.dataframe(
        analysis.format_for_display(table),
        use_container_width=True,
        hide_index=True,
        height=480,
    )

    st.divider()
    _render_detail_panel(filtered)

    with st.expander("Data source & quality", expanded=False):
        repository = get_candidate_repository(path)
        source = repository.source_summary(dataframe)
        st.write(
            f"Source workbook: **{source['workbook']}**  \n"
            f"Primary sheet: **{source['primary_sheet']}**  \n"
            f"Coordinate enrichment: **{source['coordinate_sheet']}**  \n"
            f"Records: **{source['rows']:,}**  |  "
            f"Fields: **{source['fields']:,}**  |  "
            f"Records with coordinates: **{source['coordinates']:,}**"
        )
