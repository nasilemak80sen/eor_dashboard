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
        return f"{float(value):,.2f}{suffix}"
    except (TypeError, ValueError):
        return str(value)


def _render_summary_cards(analysis: CandidateAnalysis, dataframe: pd.DataFrame) -> None:
    summary = analysis.opportunity_summary(dataframe)
    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.metric("Candidate Reservoirs", f"{summary['reservoirs']:,}")
    with c2:
        st.metric("Fields", f"{summary['fields']:,}")
    with c3:
        st.metric(
            "STOIIP",
            _safe_metric_value(summary.get("STOIIP_total"), " MMSTB"),
        )
    with c4:
        st.metric(
            "CR Volume Potential",
            _safe_metric_value(summary.get("CR potential_total"), " MMSTB"),
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
    st.subheader("Candidate Location Map")

    if pdk is None:
        st.info("PyDeck is not available. The analytical table remains fully available below.")
        return

    map_df = dataframe.dropna(subset=["LATITUDE", "LONGITUDE"]).copy()
    if map_df.empty:
        st.info("No latitude/longitude values are available for the current filter selection.")
        return

    map_df["CR_Potential"] = pd.to_numeric(
        map_df.get("CR volume potential = RF Gap x STOIIP  (MMSTB)"),
        errors="coerce",
    ).fillna(0.0)
    map_df["Map_Radius"] = map_df["CR_Potential"].clip(lower=0.0)
    if float(map_df["Map_Radius"].max()) == 0.0:
        map_df["Map_Radius"] = 1.0

    tooltip = {
        "html": (
            "<b>{Field}</b><br/>"
            "Reservoir: {Reservoir}<br/>"
            "Temp: {Temp (deg C)} °C<br/>"
            "Oil API: {Oil API}<br/>"
            "Permeability: {Avg Permeability (mD)} mD<br/>"
            "STOIIP: {STOIIP_ARPR 1.1.2025} MMSTB<br/>"
            "CR Potential: {CR_Potential} MMSTB"
        ),
        "style": {"backgroundColor": "steelblue", "color": "white"},
    }

    center_lat = float(map_df["LATITUDE"].mean())
    center_lon = float(map_df["LONGITUDE"].mean())

    st.pydeck_chart(
        pdk.Deck(
            map_style="light",
            initial_view_state=pdk.ViewState(
                latitude=center_lat,
                longitude=center_lon,
                zoom=4.2,
                pitch=20,
            ),
            layers=[
                pdk.Layer(
                    "ScatterplotLayer",
                    data=map_df,
                    get_position="[LONGITUDE, LATITUDE]",
                    get_fill_color="[255, 120, 60, 210]",
                    get_radius="Map_Radius * 1000",
                    radius_min_pixels=5,
                    radius_max_pixels=24,
                    pickable=True,
                )
            ],
            tooltip=tooltip,
        ),
        use_container_width=True,
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
    """Render the standalone Field / Reservoir Candidate Analytics feature."""
    path = str(workbook_path or CandidateRepository().workbook_path)

    st.header("🎯 Field / Reservoir Parameters")
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
            "Z Axis (Categorical)",
            list(GROUP_COLUMNS.keys()),
            index=0,
            key="candidate_group_by",
        )

    st.caption(
        "Marker size represents CR volume potential where available. "
        "Use the legend to focus the selected Field/Reservoir grouping."
    )
    _render_scatter(analysis, filtered, x_column, y_column, group_by)

    st.divider()
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
