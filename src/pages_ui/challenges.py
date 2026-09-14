"""Challenges + lessons-learned decision workspace."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from data.challenges import load_challenges
from ui.components import kpi_cards, section_title

try:
    import pydeck as pdk
except Exception:
    pdk = None


FIELD_MAP_ALIASES = {
    "field": ("field", "field name", "field_name"),
    "latitude": ("latitude", "lat"),
    "longitude": ("longitude", "long", "lon", "lng"),
}


def _find_column(df: pd.DataFrame, aliases: tuple[str, ...]) -> str | None:
    normalized = {str(column).strip().lower().replace("_", " "): column for column in df.columns}
    for alias in aliases:
        key = alias.strip().lower().replace("_", " ")
        if key in normalized:
            return normalized[key]
    return None


def _load_field_coordinates() -> pd.DataFrame:
    """Reuse the exact workbook map source used by Executive Overview."""
    try:
        import app_2 as _app

        workbook = _app.WorkbookRepository.load_workbook()
        map_df = workbook.get("map") if isinstance(workbook, dict) else None
        if not isinstance(map_df, pd.DataFrame) or map_df.empty:
            return pd.DataFrame()

        field_col = _find_column(map_df, FIELD_MAP_ALIASES["field"])
        lat_col = _find_column(map_df, FIELD_MAP_ALIASES["latitude"])
        lon_col = _find_column(map_df, FIELD_MAP_ALIASES["longitude"])
        if not all([field_col, lat_col, lon_col]):
            return pd.DataFrame()

        coords = map_df[[field_col, lat_col, lon_col]].copy()
        coords.columns = ["Field", "Latitude", "Longitude"]
        coords["Field"] = coords["Field"].astype(str).str.strip()
        coords["Latitude"] = pd.to_numeric(coords["Latitude"], errors="coerce")
        coords["Longitude"] = pd.to_numeric(coords["Longitude"], errors="coerce")
        coords = coords.dropna(subset=["Latitude", "Longitude"])
        return coords.groupby("Field", as_index=False).agg(
            Latitude=("Latitude", "mean"),
            Longitude=("Longitude", "mean"),
        )
    except Exception:
        return pd.DataFrame()


def _render_spatial_atlas(frame: pd.DataFrame, selected_field: str) -> None:
    """Render a 3D field challenge-intensity view using Overview's coordinates."""
    if pdk is None:
        st.info("PyDeck is not available for the 3D spatial view.")
        return

    coords = _load_field_coordinates()
    if coords.empty:
        st.warning("The Overview field-coordinate dataset is unavailable, so the spatial challenge view cannot be plotted.")
        return

    counts = frame.groupby("Field", as_index=False).agg(
        Challenges=("Challenge", "count"),
        Areas=("Area", "nunique"),
    )
    plot_df = coords.merge(counts, on="Field", how="inner")
    if selected_field != "All fields":
        plot_df = plot_df.loc[plot_df["Field"] == selected_field].copy()

    if plot_df.empty:
        st.info("No mapped challenge records match the selected field.")
        return

    plot_df["Elevation"] = (plot_df["Challenges"] * 55000).clip(lower=25000)
    focus = plot_df.iloc[0] if len(plot_df) == 1 else plot_df.loc[plot_df["Challenges"].idxmax()]
    zoom = 6.2 if len(plot_df) == 1 else 4.7

    layer = pdk.Layer(
        "ColumnLayer",
        data=plot_df,
        get_position="[Longitude, Latitude]",
        get_elevation="Elevation",
        elevation_scale=1,
        radius=18000 if len(plot_df) < 8 else 12000,
        get_fill_color="[0, 161, 156, 215]",
        pickable=True,
        auto_highlight=True,
    )
    tooltip = {
        "html": "<b>{Field}</b><br/>Challenge records: {Challenges}<br/>Challenge areas: {Areas}",
        "style": {"backgroundColor": "#182230", "color": "white"},
    }
    deck = pdk.Deck(
        map_style="light",
        initial_view_state=pdk.ViewState(
            latitude=float(focus["Latitude"]),
            longitude=float(focus["Longitude"]),
            zoom=zoom,
            pitch=52,
            bearing=-8,
        ),
        layers=[layer],
        tooltip=tooltip,
    )
    st.pydeck_chart(deck, use_container_width=True, height=560)
    st.caption("Column height represents the number of recorded challenge items for each mapped field; it is a digest signal, not a risk score.")


def _render_field_story(field_frame: pd.DataFrame, selected_field: str) -> None:
    if field_frame.empty:
        st.info("No challenge records are available for the current selection.")
        return

    fields = field_frame["Field"].dropna().unique().tolist()
    if selected_field == "All fields":
        st.markdown("### Portfolio-wide lessons")
        st.caption("Start with themes, then open a field to read the detailed challenge-to-lesson chain.")
        theme = (
            field_frame.groupby("Area", as_index=False)
            .agg(Records=("Challenge", "count"), Fields=("Field", "nunique"))
            .sort_values(["Records", "Fields"], ascending=False)
        )
        st.dataframe(theme, use_container_width=True, hide_index=True)
        return

    st.markdown(f"### {selected_field} — challenge story")
    rows = field_frame.loc[field_frame["Field"] == selected_field].copy()
    for _, row in rows.iterrows():
        st.markdown(
            "<div style='border:1px solid #E4E7EC;border-radius:14px;padding:14px 16px;margin:0 0 12px;background:#FFFFFF;'>"
            f"<div style='font-size:.72rem;font-weight:700;color:#667085;letter-spacing:.04em;text-transform:uppercase;margin-bottom:6px;'>{row['Area']}</div>"
            f"<div style='font-size:1rem;font-weight:750;color:#111827;margin-bottom:8px;'>{row['Challenge']}</div>"
            f"<div style='font-size:.88rem;line-height:1.55;color:#475467;'><b>Lesson learnt:</b> {row['Lesson']}</div>"
            "</div>",
            unsafe_allow_html=True,
        )


def render() -> None:
    """Render the intuitive spatial challenge and lessons workspace."""
    try:
        frame, metadata = load_challenges()
    except Exception as exc:
        st.error(f"Challenge source data is unavailable: {exc}")
        return

    section_title(
        "Challenges + Lesson Learnt",
        "Translate past EOR experience into field-level context, execution awareness and practical lessons before advancing a screening decision.",
    )

    field_options = ["All fields"] + sorted(frame["Field"].unique().tolist(), key=str.casefold)
    area_options = ["All areas"] + sorted(frame["Area"].unique().tolist(), key=str.casefold)
    c1, c2, c3 = st.columns([1.4, 1.2, 1])
    with c1:
        selected_field = st.selectbox("Field", field_options, key="challenge_field_filter")
    with c2:
        selected_area = st.selectbox("Challenge area", area_options, key="challenge_area_filter")
    with c3:
        search_text = st.text_input("Search", placeholder="keyword in challenge or lesson", key="challenge_search")

    filtered = frame.copy()
    if selected_field != "All fields":
        filtered = filtered.loc[filtered["Field"] == selected_field]
    if selected_area != "All areas":
        filtered = filtered.loc[filtered["Area"] == selected_area]
    if search_text.strip():
        needle = search_text.strip().casefold()
        mask = (
            filtered["Challenge"].str.casefold().str.contains(needle, na=False)
            | filtered["Lesson"].str.casefold().str.contains(needle, na=False)
            | filtered["Area"].str.casefold().str.contains(needle, na=False)
        )
        filtered = filtered.loc[mask]

    unique_fields = filtered["Field"].nunique()
    unique_areas = filtered["Area"].nunique()
    kpi_cards([
        ("Challenge Records", len(filtered), "Items in current view"),
        ("Fields", unique_fields, "Fields represented"),
        ("Challenge Areas", unique_areas, "Distinct challenge themes"),
        ("Lessons", len(filtered), "One lesson paired to each record"),
    ])

    st.markdown("<div class='atlas-divider'></div>", unsafe_allow_html=True)

    spatial_tab, digest_tab, register_tab = st.tabs([
        "🌐 3D Spatial Atlas", "🧠 Digest the Lessons", "📚 Full Challenge Register",
    ])

    with spatial_tab:
        left, right = st.columns([1.9, 1])
        with left:
            section_title(
                "Field Challenge Landscape",
                "The same field coordinates used by Executive Overview, transformed into a 3D challenge-density view.",
            )
            _render_spatial_atlas(frame, selected_field)
        with right:
            section_title("What to Notice", "Use the spatial view as an orientation tool, not a risk score.")
            if selected_field == "All fields":
                top_fields = (
                    filtered.groupby("Field", as_index=False)
                    .agg(Challenges=("Challenge", "count"), Areas=("Area", "nunique"))
                    .sort_values("Challenges", ascending=False)
                    .head(8)
                )
                for _, row in top_fields.iterrows():
                    st.markdown(
                        f"**{row['Field']}**  \
"
                        f"{int(row['Challenges'])} challenge records · {int(row['Areas'])} areas"
                    )
            else:
                rows = filtered.loc[filtered["Field"] == selected_field]
                st.metric("Challenge records", len(rows))
                st.metric("Areas represented", rows["Area"].nunique())
                st.caption("Use the Digest tab to move from location to the actual challenge → lesson narrative.")

    with digest_tab:
        left, right = st.columns([1, 1.6])
        with left:
            section_title("Challenge Themes", "Where the knowledge burden is concentrated.")
            area_summary = (
                filtered.groupby("Area", as_index=False)
                .agg(Records=("Challenge", "count"), Fields=("Field", "nunique"))
                .sort_values("Records", ascending=False)
            )
            st.dataframe(area_summary, use_container_width=True, hide_index=True)
        with right:
            _render_field_story(filtered, selected_field)

    with register_tab:
        section_title(
            "Complete Challenge + Lesson Register",
            f"Full source-backed register from {metadata['source_name']} · {metadata['rows']} records. Use the filters above to narrow it, or expand this section for the complete dataset.",
        )
        st.dataframe(
            filtered.sort_values(["Field", "Area", "Challenge"], key=lambda col: col.astype(str).str.casefold()),
            use_container_width=True,
            hide_index=True,
            height=620,
        )
