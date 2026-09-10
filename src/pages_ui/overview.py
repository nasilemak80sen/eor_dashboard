"""Executive Overview page."""

from __future__ import annotations

from html import escape

import pandas as pd
import streamlit as st

from ui.components import insight_cards, kpi_cards, section_title

try:
    import pydeck as pdk
except Exception:
    pdk = None


def _find_column(df: pd.DataFrame, aliases: tuple[str, ...]) -> str | None:
    normalized = {str(col).strip().lower().replace("_", " "): col for col in df.columns}
    for alias in aliases:
        key = alias.strip().lower().replace("_", " ")
        if key in normalized:
            return normalized[key]
    return None


def _map_summary(map_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    field_col = _find_column(map_df, ("field", "field name", "field_name"))
    method_col = _find_column(map_df, ("types of eor", "eor method", "eor_method", "method"))
    lat_col = _find_column(map_df, ("latitude", "lat"))
    lon_col = _find_column(map_df, ("longitude", "long", "lon", "lng"))

    if not field_col or not method_col or not lat_col or not lon_col:
        return pd.DataFrame(), pd.DataFrame()

    work = map_df[[field_col, method_col, lat_col, lon_col]].copy()
    work.columns = ["Field", "EOR Method", "Latitude", "Longitude"]
    work["Field"] = work["Field"].astype(str).str.strip()
    work["EOR Method"] = work["EOR Method"].astype(str).str.strip()
    work["Latitude"] = pd.to_numeric(work["Latitude"], errors="coerce")
    work["Longitude"] = pd.to_numeric(work["Longitude"], errors="coerce")
    work = work.replace({"Field": {"nan": ""}, "EOR Method": {"nan": ""}})
    work = work[(work["Field"] != "") & (work["EOR Method"] != "")].copy()

    def methods(values: pd.Series) -> str:
        return ", ".join(sorted(set(values.dropna().astype(str).str.strip())))

    fields = (
        work.dropna(subset=["Latitude", "Longitude"])
        .groupby("Field", as_index=False)
        .agg(
            Latitude=("Latitude", "mean"),
            Longitude=("Longitude", "mean"),
            EOR_Method_Count=("EOR Method", "nunique"),
            EOR_Methods=("EOR Method", methods),
        )
    )
    method_table = (
        work.groupby("EOR Method")["Field"]
        .nunique()
        .sort_values(ascending=False)
        .rename("Fields")
        .reset_index()
    )
    if not method_table.empty:
        method_table["Share of mapped fields"] = (
            method_table["Fields"] / fields["Field"].nunique() * 100.0
        ).round(1)
    return fields, method_table


def _render_spatial_snapshot(map_df: pd.DataFrame) -> None:
    section_title(
        "Portfolio Snapshot",
        "3D spatial view of mapped fields. Column height represents the number of distinct EOR methods associated with each field.",
    )
    field_summary, method_table = _map_summary(map_df)
    if field_summary.empty:
        st.warning("The map sheet does not contain the expected Field / EOR Method / LATITUDE / LONGITUDE columns.")
        return

    mapped_fields = int(field_summary["Field"].nunique())
    methods = int(method_table["EOR Method"].nunique()) if not method_table.empty else 0
    map_kpi_1, map_kpi_2 = st.columns(2)
    with map_kpi_1:
        st.metric("Mapped Fields", mapped_fields, "Unique fields in map sheet")
    with map_kpi_2:
        st.metric("EOR Methods", methods, "Distinct EOR types in map sheet")

    left, right = st.columns([1.8, 1])
    with left:
        if pdk is None:
            st.info("PyDeck is not available, so the spatial map cannot be rendered in 3D.")
        else:
            center_lat = float(field_summary["Latitude"].mean())
            center_lon = float(field_summary["Longitude"].mean())
            tooltip = {
                "html": (
                    "<b>{Field}</b><br/>"
                    "EOR methods: {EOR_Methods}<br/>"
                    "Distinct methods: {EOR_Method_Count}"
                ),
                "style": {"backgroundColor": "#102F37", "color": "white"},
            }
            st.pydeck_chart(
                pdk.Deck(
                    map_style="light",
                    initial_view_state=pdk.ViewState(
                        latitude=center_lat,
                        longitude=center_lon,
                        zoom=5.0,
                        pitch=50,
                        bearing=0,
                    ),
                    layers=[
                        pdk.Layer(
                            "ColumnLayer",
                            data=field_summary,
                            get_position="[Longitude, Latitude]",
                            get_elevation="EOR_Method_Count * 120000",
                            elevation_scale=1,
                            radius=14000,
                            get_fill_color="[0, 161, 156, 190]",
                            pickable=True,
                            auto_highlight=True,
                        )
                    ],
                    tooltip=tooltip,
                ),
                use_container_width=True,
                height=540,
            )
    with right:
        section_title("EOR Method Coverage", "Number of unique mapped fields associated with each EOR method.")
        if method_table.empty:
            st.info("No EOR method records are available.")
        else:
            display = method_table.copy()
            display.columns = ["EOR Method", "Fields", "Mapped Field Share (%)"]
            st.dataframe(display, use_container_width=True, hide_index=True, height=500)


def render() -> None:
    import app_2 as _app

    workbook = _app.WorkbookRepository.load_workbook()
    df = workbook.get("PROP_updatedNov25_v2") if isinstance(workbook, dict) else None
    map_df = workbook.get("map") if isinstance(workbook, dict) else None

    fields = int(df["Field"].nunique()) if isinstance(df, pd.DataFrame) and not df.empty and "Field" in df.columns else 41
    reservoirs = len(df) if isinstance(df, pd.DataFrame) and not df.empty else 600
    rf_gap_total = pd.to_numeric(df["RF Gap"], errors="coerce").sum() if isinstance(df, pd.DataFrame) and "RF Gap" in df.columns else None

    kpi_cards([
        ("Fields", fields, "Portfolio coverage"),
        ("Reservoirs", reservoirs, "Screening universe"),
        ("Mapped Fields", _map_summary(map_df)[0]["Field"].nunique() if isinstance(map_df, pd.DataFrame) and not map_df.empty and not _map_summary(map_df)[0].empty else "—", "EOR map sheet"),
        ("EOR Methods", _map_summary(map_df)[1]["EOR Method"].nunique() if isinstance(map_df, pd.DataFrame) and not map_df.empty and not _map_summary(map_df)[1].empty else "—", "Mapped EOR taxonomy"),
        ("RF Gap", "—" if rf_gap_total is None else f"{rf_gap_total:,.1f}", "Workbook aggregate"),
    ])

    st.markdown("<div class='atlas-divider'></div>", unsafe_allow_html=True)
    portfolio_tab, signals_tab, journey_tab = st.tabs(["Portfolio Snapshot", "Opportunity Signals", "Decision Journey"])

    with portfolio_tab:
        if isinstance(map_df, pd.DataFrame) and not map_df.empty:
            _render_spatial_snapshot(map_df)
        else:
            st.info("The EOR Screening Tool 2026 workbook map sheet is unavailable in this session.")

    with signals_tab:
        col1, col2 = st.columns(2)
        with col1:
            section_title("Opportunity Concentration", "Where recovery-gap signals are concentrated by field.")
            if isinstance(df, pd.DataFrame) and not df.empty and "Field" in df.columns and "RF Gap" in df.columns:
                temp = df.assign(**{"RF Gap": pd.to_numeric(df["RF Gap"], errors="coerce")})
                field_gap = temp.groupby("Field")["RF Gap"].sum().sort_values(ascending=False).head(10)
                st.bar_chart(field_gap)
            else:
                st.info("Field RF-gap data is unavailable.")
        with col2:
            section_title("What to do next", "Move from spatial opportunity to reservoir-level engineering evidence.")
            insight_cards([
                ("DISCOVER", "Find candidates", "Use the candidate explorer to isolate fields and reservoirs for review."),
                ("SCREEN", "Run the engineering gate", "Test the selected reservoir against ScreenTool v3 deterministic criteria."),
                ("DECIDE", "Review hybrid ranking", "Use CatBoost and Decision Fusion only after the engineering gate."),
            ])

    with journey_tab:
        section_title("Decision Journey", "Engineering evidence remains ahead of recommendation.")
        journey = pd.DataFrame({
            "Stage": ["Portfolio", "Candidates", "Engineering Gate", "Hybrid Intelligence", "Insights"],
            "Purpose": [
                "See where opportunity is concentrated",
                "Identify reservoirs for review",
                "Test deterministic feasibility",
                "Rank methods with ML support",
                "Translate results into actions",
            ],
        })
        st.dataframe(journey, use_container_width=True, hide_index=True)
