"""Fast portfolio globe renderer for EOR Atlas.

This renderer intentionally uses Plotly's built-in geographic scene instead
of booting OpenGlobus on the default Overview page. That keeps the first
visualisation lightweight while preserving the same field-marker intent.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def build_portfolio_globe(
    dataframe: pd.DataFrame,
    *,
    latitude: str = "Latitude",
    longitude: str = "Longitude",
    name: str = "Field",
    value: str = "Methods",
    value_label: str = "Distinct EOR methods",
    height: int = 620,
    center_lat: float = 4.2,
    center_lon: float = 102.0,
) -> go.Figure:
    """Build a fast orthographic world-globe view from coordinate records."""

    if dataframe is None or dataframe.empty:
        raise ValueError("Portfolio globe requires at least one map record.")

    required = [latitude, longitude, name]
    missing = [column for column in required if column not in dataframe.columns]
    if missing:
        raise ValueError(
            "Portfolio globe is missing required columns: "
            + ", ".join(missing)
        )

    work = dataframe.copy()
    work[latitude] = pd.to_numeric(work[latitude], errors="coerce")
    work[longitude] = pd.to_numeric(work[longitude], errors="coerce")
    work[name] = work[name].fillna("").astype(str).str.strip()

    work = work.dropna(subset=[latitude, longitude])
    work = work[work[name] != ""].copy()

    if work.empty:
        raise ValueError("Portfolio globe has no valid coordinate records.")

    if value in work.columns:
        work["_marker_value"] = pd.to_numeric(
            work[value], errors="coerce"
        ).fillna(1)
    else:
        work["_marker_value"] = 1.0

    # Keep marker geometry stable even for zero/negative source values.
    work["_marker_value"] = work["_marker_value"].clip(lower=1)

    hover_columns: list[str] = []
    for column in ("Methods", "EOR Methods", "Latitude", "Longitude"):
        if column in work.columns:
            hover_columns.append(column)

    custom_columns = [name, *hover_columns]

    fig = px.scatter_geo(
        work,
        lat=latitude,
        lon=longitude,
        size="_marker_value",
        color="_marker_value",
        hover_name=name,
        custom_data=custom_columns,
        projection="orthographic",
        scope="world",
        size_max=24,
        color_continuous_scale=[
            [0.00, "#BFD730"],
            [0.35, "#00A19C"],
            [0.70, "#20419A"],
            [1.00, "#763F98"],
        ],
    )

    safe_height = max(520, int(height))

    fig.update_traces(
        marker={
            "opacity": 0.88,
            "sizemin": 7,
            "line": {"width": 1, "color": "#FFFFFF"},
        },
        hovertemplate=(
            "<b>%{customdata[0]}</b><br>"
            + (
                "Distinct EOR methods: %{customdata[1]}<br>"
                if "Methods" in hover_columns
                else ""
            )
            + (
                "EOR methods: %{customdata[2]}<br>"
                if "Methods" in hover_columns and "EOR Methods" in hover_columns
                else (
                    "EOR methods: %{customdata[1]}<br>"
                    if "Methods" not in hover_columns and "EOR Methods" in hover_columns
                    else ""
                )
            )
            + (
                "Latitude: %{customdata[3]:.4f}<br>"
                "Longitude: %{customdata[4]:.4f}"
                if len(custom_columns) >= 5
                else ""
            )
            + "<extra></extra>"
        ),
    )

    # A known stable rotation gives the globe a Malaysia/SEA-friendly default
    # while still allowing normal Plotly drag/rotate interactions.
    fig.update_geos(
        projection_type="orthographic",
        projection_rotation={
            "lon": float(center_lon),
            "lat": float(center_lat),
        },
        showland=True,
        landcolor="#E7EFEC",
        showocean=True,
        oceancolor="#DDEDF2",
        showcountries=True,
        countrycolor="#A8B8BD",
        showcoastlines=True,
        coastlinecolor="#82979C",
        showlakes=True,
        lakecolor="#DDEDF2",
        showframe=False,
        bgcolor="rgba(0,0,0,0)",
    )

    fig.update_layout(
        height=safe_height,
        margin={"l": 0, "r": 0, "t": 18, "b": 0},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Arial, sans-serif", "color": "#183238"},
        coloraxis_colorbar={
            "title": {"text": value_label},
            "orientation": "h",
            "x": 0.5,
            "xanchor": "center",
            "y": -0.01,
            "yanchor": "top",
            "len": 0.42,
            "thickness": 10,
        },
        showlegend=False,
    )

    return fig


def portfolio_globe_config() -> dict[str, Any]:
    """Return a restrained Plotly interaction configuration for the globe."""

    return {
        "displaylogo": False,
        "responsive": True,
        "scrollZoom": False,
        "modeBarButtonsToRemove": [
            "lasso2d",
            "select2d",
            "autoScale2d",
        ],
    }
