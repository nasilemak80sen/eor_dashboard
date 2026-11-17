"""Executive Overview page and visual benchmark for EOR Atlas."""

from __future__ import annotations

from html import escape

import pandas as pd
import streamlit as st

from ui.components import kpi_cards, metric_cards, section_title


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


def _render_primary_kpis(
    *,
    fields: int,
    reservoirs: int,
    rf_gap_total: float | None,
    mapped_fields: int,
    eor_methods: int,
) -> None:
    """Establish the page's primary and supporting KPI hierarchy."""
    section_title(
        "Portfolio at a glance",
        "Start with the size of the screening universe, then use the map and opportunity signals to choose where to look closer.",
    )
    kpi_cards(
        [
            ("Fields", fields, "Portfolio coverage"),
            ("Reservoirs", reservoirs, "Screening universe"),
            (
                "RF Gap",
                "—" if rf_gap_total is None else f"{rf_gap_total:,.1f}",
                "Workbook aggregate; not a project-level forecast",
            ),
        ]
    )

    supporting_left, supporting_right = st.columns(2)
    with supporting_left:
        metric_cards(
            [("Mapped fields", mapped_fields, "Coordinate-enriched field records")],
            columns=1,
            tone="blue",
        )
    with supporting_right:
        metric_cards(
            [("EOR methods", eor_methods, "Distinct methods in the field map")],
            columns=1,
            tone="accent",
        )


def _render_source_availability(workbook_ready: bool, map_ready: bool) -> None:
    """Show only source availability states that are checked on this page."""
    items = [
        ("Portfolio workbook", workbook_ready),
        ("Field coordinates", map_ready),
    ]
    html = []
    for label, ready in items:
        status = "Available" if ready else "Needs attention"
        state_class = "ready" if ready else "warning"
        html.append(
            f'<div class="atlas-overview-status">'
            f'<span class="atlas-overview-status-label">{escape(label)}</span>'
            f'<span class="atlas-overview-status-value {state_class}">{status}</span>'
            f"</div>"
        )
    st.markdown(
        '<div class="atlas-overview-status-grid">' + "".join(html) + "</div>",
        unsafe_allow_html=True,
    )


def _render_spatial_snapshot(map_df: pd.DataFrame) -> None:
    fields, methods = _map_summary(map_df)
    if fields.empty:
        st.warning(
            "The workbook map sheet does not contain the expected field and coordinate structure."
        )
        return

    section_title(
        "Portfolio geography",
        "Explore the field footprint on the interactive 3D Earth. Select a field to focus the map, or leave the full portfolio in view.",
    )
    focus_col, context_col = st.columns([1.05, 2.2], vertical_alignment="bottom")
    focus_options = ["All fields"] + sorted(fields["Field"].tolist(), key=str.casefold)
    with focus_col:
        focus = st.selectbox(
            "Field focus",
            focus_options,
            key="overview_spatial_focus",
        )
    visible = fields if focus == "All fields" else fields.loc[fields["Field"] == focus].copy()

    with context_col:
        scope_label = (
            "All mapped fields"
            if focus == "All fields"
            else f"Focused field: {focus}"
        )
        st.markdown(
            f'<div class="atlas-overview-map-context">'
            f'<span class="atlas-overview-map-context-label">CURRENT MAP SCOPE</span>'
            f'<span class="atlas-overview-map-context-value">{escape(scope_label)}</span>'
            f'<span class="atlas-overview-map-context-note">{len(visible):,} mapped fields · {int(map_df.shape[0]):,} map records</span>'
            f"</div>",
            unsafe_allow_html=True,
        )

    if visible.empty:
        st.info("No mapped fields are available for the selected focus.")
        return

    if focus == "All fields":
        globe_lat, globe_lon, globe_height = 4.2, 102.0, 12000000
    else:
        globe_lat = float(visible.iloc[0]["Latitude"])
        globe_lon = float(visible.iloc[0]["Longitude"])
        globe_height = 5000000

    from ui.openglobus import render_openglobus_map

    # Keep the WebGL component visible in the page flow, never inside hidden tabs.
    # Its field payload, details, camera height and rendering options are unchanged.
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
        subtitle="Interactive 3D field map with EOR-method coverage and field-level details.",
        height=620,
        camera_height=globe_height,
        show_labels=False,
    )

    st.caption(
        "Each marker represents a mapped field. Marker size reflects the number of distinct EOR methods. "
        "Select a marker to inspect the field and fly to its location. Zoom in to separate nearby fields."
    )


def _render_method_coverage(methods: pd.DataFrame) -> None:
    section_title(
        "EOR method coverage",
        "Compare how many mapped fields are associated with each method. Coverage describes the source map, not engineering eligibility.",
    )
    if methods.empty:
        st.info("No EOR method records are available.")
        return

    coverage_cards = [
        (
            str(row["EOR Method"]),
            int(row["Fields"]),
            f'{float(row["Mapped Field Share (%)"]):.1f}% of mapped fields',
        )
        for _, row in methods.iterrows()
    ]
    metric_cards(coverage_cards, columns=min(4, len(coverage_cards)), tone="accent")


def _render_opportunity_concentration(df: pd.DataFrame | None) -> None:
    section_title(
        "Opportunity concentration",
        "Field-level RF Gap aggregation is a portfolio prioritisation signal. Validate individual reservoirs through the Engineering Gate before making a technical recommendation.",
    )
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


def _navigate_to_page(page: str) -> None:
    """Use the existing application route state for page-level shortcuts."""
    st.session_state["atlas_page"] = page
    st.rerun()


def _render_workflow_shortcuts() -> None:
    section_title(
        "Continue the engineering workflow",
        "Move from portfolio discovery to reservoir-level assessment. These shortcuts open existing pages and do not execute screening or model inference.",
    )
    actions = [
        (
            "01",
            "Discover candidates",
            "Filter the reservoir population and review field-level properties.",
            "candidates",
            "Explore candidates",
        ),
        (
            "02",
            "Run engineering screening",
            "Evaluate a selected reservoir using the deterministic Excel Gate.",
            "screening",
            "Open screening",
        ),
        (
            "03",
            "Review hybrid intelligence",
            "Inspect model-supported ranking after engineering feasibility is established.",
            "intelligence",
            "Open intelligence",
        ),
    ]
    columns = st.columns(3)
    for column, (step, title, description, page, button_label) in zip(columns, actions):
        with column:
            with st.container(border=True):
                st.markdown(f'<div class="atlas-overview-action-step">{step}</div>', unsafe_allow_html=True)
                st.markdown(f"**{title}**")
                st.caption(description)
                if st.button(
                    button_label,
                    key=f"overview_go_{page}",
                    use_container_width=True,
                ):
                    _navigate_to_page(page)


def render() -> None:
    import app_2 as _app

    # Keep the established workbook source and field/reservoir calculations.
    workbook = _app.WorkbookRepository.load_workbook()
    df = workbook.get("PROP_updatedNov25_v2") if isinstance(workbook, dict) else None
    map_df = workbook.get("map") if isinstance(workbook, dict) else None
    fields = int(df["Field"].nunique()) if isinstance(df, pd.DataFrame) and "Field" in df.columns else 0
    reservoirs = len(df) if isinstance(df, pd.DataFrame) else 0
    rf_gap_total = pd.to_numeric(df["RF Gap"], errors="coerce").sum() if isinstance(df, pd.DataFrame) and "RF Gap" in df.columns else None
    mapped, methods = _map_summary(map_df) if isinstance(map_df, pd.DataFrame) else (pd.DataFrame(), pd.DataFrame())

    _render_primary_kpis(
        fields=fields,
        reservoirs=reservoirs,
        rf_gap_total=rf_gap_total,
        mapped_fields=len(mapped),
        eor_methods=int(methods["EOR Method"].nunique()) if not methods.empty else 0,
    )

    workbook_ready = isinstance(workbook, dict)
    map_source_available = isinstance(map_df, pd.DataFrame) and not map_df.empty
    map_ready = not mapped.empty
    _render_source_availability(workbook_ready, map_ready)

    st.markdown("<div class='atlas-divider'></div>", unsafe_allow_html=True)

    # The WebGL map remains in a stable visible page container, outside tabs.
    if map_source_available:
        _render_spatial_snapshot(map_df)
    else:
        st.info("The workbook map sheet is unavailable in this session.")

    st.markdown("<div class='atlas-divider'></div>", unsafe_allow_html=True)
    _render_method_coverage(methods)

    st.markdown("<div class='atlas-divider'></div>", unsafe_allow_html=True)
    _render_opportunity_concentration(df)

    st.markdown("<div class='atlas-divider'></div>", unsafe_allow_html=True)
    _render_workflow_shortcuts()
