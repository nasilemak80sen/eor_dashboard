"""Executive Overview page."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from ui.components import insight_cards, kpi_cards, section_title


def _find_column(df: pd.DataFrame, aliases: tuple[str, ...]) -> str | None:
    normalized = {str(c).strip().lower().replace("_", " "): c for c in df.columns}
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
    if not all([field_col, method_col, lat_col, lon_col]):
        return pd.DataFrame(), pd.DataFrame()

    work = map_df[[field_col, method_col, lat_col, lon_col]].copy()
    work.columns = ["Field", "EOR Method", "Latitude", "Longitude"]
    work["Field"] = work["Field"].astype(str).str.strip()
    work["EOR Method"] = work["EOR Method"].astype(str).str.strip()
    work["Latitude"] = pd.to_numeric(work["Latitude"], errors="coerce")
    work["Longitude"] = pd.to_numeric(work["Longitude"], errors="coerce")
    work = work[(work["Field"] != "") & (work["EOR Method"] != "")].copy()

    field_summary = (
        work.dropna(subset=["Latitude", "Longitude"])
        .groupby("Field", as_index=False)
        .agg(
            Latitude=("Latitude", "mean"),
            Longitude=("Longitude", "mean"),
            Methods=("EOR Method", "nunique"),
            **{"EOR Methods": ("EOR Method", lambda values: ", ".join(sorted(set(values))))},
        )
    )
    method_table = (
        work.groupby("EOR Method")["Field"]
        .nunique()
        .sort_values(ascending=False)
        .rename("Fields")
        .reset_index()
    )
    if not method_table.empty and not field_summary.empty:
        method_table["Mapped Field Share (%)"] = (
            method_table["Fields"] / field_summary["Field"].nunique() * 100
        ).round(1)
    return field_summary, method_table


def _render_spatial_snapshot(map_df: pd.DataFrame) -> None:
    from ui.openglobus import render_openglobus_map

    section_title(
        "Portfolio Snapshot",
        "Start with geography and concentration, then drill into field-level EOR evidence.",
    )
    fields, methods = _map_summary(map_df)
    if fields.empty:
        st.warning("The workbook map sheet does not contain the expected field and coordinate structure.")
        return

    c1, c2, c3 = st.columns(3)
    c1.metric("Mapped fields", len(fields))
    c2.metric("EOR methods", int(methods["EOR Method"].nunique()) if not methods.empty else 0)
    c3.metric("Mapped coordinates", int(map_df.shape[0]))

    left, right = st.columns([2.2, 1])
    with left:
        focus_options = ["All fields"] + sorted(fields["Field"].tolist(), key=str.casefold)
        focus = st.selectbox("Field focus", focus_options, key="overview_spatial_focus")
        visible = fields if focus == "All fields" else fields.loc[fields["Field"] == focus].copy()

        if visible.empty:
            st.info("No mapped fields are available for the selected focus.")
        else:
            render_openglobus_map(
                visible,
                latitude="Latitude",
                longitude="Longitude",
                name="Field",
                value="Methods",
                value_label="Distinct EOR methods",
                detail_columns=[
                    ("Distinct EOR methods", "Methods"),
                    ("EOR methods", "EOR Methods"),
                ],
                title="EOR Atlas · Portfolio Geography",
                subtitle="OpenGlobus 3D view of mapped fields and their EOR-method coverage.",
                height=560,
                camera_height=12000000 if focus == "All fields" else 5000000,
            )
            st.caption(
                "Each marker represents a mapped field. Marker size follows the number of distinct EOR methods; "
                "click a marker to inspect its EOR-method coverage."
            )

    with right:
        section_title("EOR Method Coverage", "Unique mapped fields associated with each method.")
        if methods.empty:
            st.info("No EOR method records are available.")
        else:
            st.dataframe(methods, use_container_width=True, hide_index=True, height=520)


def render() -> None:
    import app_2 as _app

    workbook = _app.WorkbookRepository.load_workbook()
    df = workbook.get("PROP_updatedNov25_v2") if isinstance(workbook, dict) else None
    map_df = workbook.get("map") if isinstance(workbook, dict) else None
    fields = int(df["Field"].nunique()) if isinstance(df, pd.DataFrame) and "Field" in df.columns else 0
    reservoirs = len(df) if isinstance(df, pd.DataFrame) else 0
    rf_gap_total = pd.to_numeric(df["RF Gap"], errors="coerce").sum() if isinstance(df, pd.DataFrame) and "RF Gap" in df.columns else None
    mapped, methods = _map_summary(map_df) if isinstance(map_df, pd.DataFrame) else (pd.DataFrame(), pd.DataFrame())

    kpi_cards([
        ("Fields", fields, "Portfolio coverage"),
        ("Reservoirs", reservoirs, "Screening universe"),
        ("Mapped fields", len(mapped), "Coordinate-enriched map"),
        ("EOR methods", int(methods["EOR Method"].nunique()) if not methods.empty else 0, "Mapped taxonomy"),
        ("RF Gap", "—" if rf_gap_total is None else f"{rf_gap_total:,.1f}", "Workbook aggregate"),
    ])

    st.markdown("<div class='atlas-divider'></div>", unsafe_allow_html=True)
    portfolio_tab, signals_tab, journey_tab = st.tabs(["Portfolio Snapshot", "Opportunity Signals", "Decision Journey"])

    with portfolio_tab:
        if isinstance(map_df, pd.DataFrame) and not map_df.empty:
            _render_spatial_snapshot(map_df)
        else:
            st.info("The workbook map sheet is unavailable in this session.")

    with signals_tab:
        left, right = st.columns([1.4, 1])
        with left:
            section_title("Opportunity Concentration", "Use field aggregation as a prioritisation signal, then validate at reservoir level.")
            if isinstance(df, pd.DataFrame) and not df.empty and {"Field", "RF Gap"}.issubset(df.columns):
                temp = df[["Field", "RF Gap"]].copy()
                temp["RF Gap"] = pd.to_numeric(temp["RF Gap"], errors="coerce")
                ranked = temp.dropna().groupby("Field")["RF Gap"].sum().sort_values(ascending=False).reset_index()
                try:
                    import altair as alt
                    chart = alt.Chart(ranked.head(12)).mark_bar().encode(
                        x=alt.X("RF Gap:Q", title="Aggregate RF Gap"),
                        y=alt.Y("Field:N", sort="-x", title=None),
                        tooltip=["Field", alt.Tooltip("RF Gap:Q", format=",.1f")],
                    ).properties(height=440).interactive()
                    st.altair_chart(chart, use_container_width=True)
                except Exception:
                    st.dataframe(ranked.head(12), use_container_width=True, hide_index=True)
            else:
                st.info("Field RF-gap data is unavailable.")
        with right:
            section_title("Decision Pulse", "The dashboard should always make the next decision step obvious.")
            insight_cards([
                ("01", "Discover", "Narrow candidate reservoirs and locate portfolio concentration."),
                ("02", "Screen", "Run the deterministic engineering gate on a selected reservoir."),
                ("03", "Decide", "Use hybrid intelligence only after engineering feasibility is established."),
            ])

    with journey_tab:
        section_title("Decision Journey", "A consistent evidence chain across the application.")
        journey = pd.DataFrame({
            "Stage": ["Portfolio", "Candidates", "Engineering Gate", "Hybrid Intelligence", "Insights"],
            "What the user sees": ["Where opportunity sits", "Which reservoirs are worth review", "Why techniques pass or fail", "How ML changes the ranking", "What to do next"],
        })
        st.dataframe(journey, use_container_width=True, hide_index=True)
