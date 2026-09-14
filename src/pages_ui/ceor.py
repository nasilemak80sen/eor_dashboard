"""CEOR evidence workspace.

Fluid / Fluid explains whether injected chemistry behaves acceptably in the
fluid system. Fluid / Rock explains whether it survives rock interaction and
demonstrates recovery / Sor reduction. All evidence is workbook-backed.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from data.ceor_evidence import load_ceor_evidence
from ui.components import insight_cards, section_title

_FF_DESC = (
    "Laboratory fluid–fluid evidence: viscosity behaviour, phase stability and "
    "interfacial tension before interpreting reservoir performance."
)
_FR_DESC = (
    "Laboratory fluid–rock evidence: adsorption, core-flood recovery and Sor "
    "reduction to understand whether chemical EOR translates into reservoir response."
)


def _fmt_source(metadata: dict, requested: str) -> str:
    actual = metadata.get("source_map", {}).get(requested)
    return f"Source sheet: `{actual or requested}`"


def _render_rheology(df: pd.DataFrame) -> None:
    section_title("Rheology", "Apparent viscosity versus shear rate. Compare polymer behaviour across years and formulations.")
    if df.empty:
        st.warning("Vis_Shear contains no usable rheology records.")
        return
    years = sorted(df["Year"].dropna().astype(int).unique().tolist())
    polymers = sorted(df["Polymer"].dropna().astype(str).unique().tolist(), key=str.casefold)
    a, b = st.columns([1, 2])
    with a:
        selected_years = st.multiselect("Year", years, default=years, key="ceor_rheo_years")
    with b:
        selected_polymers = st.multiselect("Polymer type", polymers, default=polymers, key="ceor_rheo_polymers")
    work = df.copy()
    if selected_years:
        work = work[work["Year"].isin(selected_years)]
    if selected_polymers:
        work = work[work["Polymer"].isin(selected_polymers)]
    if work.empty:
        st.info("No rheology records match the selected filters.")
        return
    fig = px.line(
        work.sort_values(["Polymer", "Shear Rate"]),
        x="Shear Rate",
        y="Apparent Viscosity",
        color="Polymer",
        markers=True,
        hover_data=["Year"],
        labels={"Shear Rate": "Shear Rate (1/sec)", "Apparent Viscosity": "Apparent Viscosity"},
    )
    fig.update_layout(height=460, margin=dict(l=50, r=20, t=30, b=80), legend_title="Polymer")
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def _render_phase_chart(df: pd.DataFrame, title: str) -> None:
    if df.empty:
        st.info(f"{title}: no usable records in the workbook.")
        return

    work = df.copy()
    work["Precipitation"] = pd.to_numeric(work["Precipitation"], errors="coerce").fillna(0) * 100
    work["No Precipitation"] = pd.to_numeric(work["No Precipitation"], errors="coerce").fillna(0) * 100
    long = work.melt(
        id_vars=["Formulation"],
        value_vars=["No Precipitation", "Precipitation"],
        var_name="Outcome",
        value_name="Percent",
    )

    # Do not pass None into Plotly Express label configuration. Recent Plotly
    # releases can internally concatenate axis-label strings and raise:
    # TypeError: unsupported operand type(s) for +: 'NoneType' and 'str'.
    fig = px.bar(
        long,
        x="Percent",
        y="Formulation",
        color="Outcome",
        orientation="h",
        barmode="stack",
        text=long["Percent"].map(lambda value: f"{value:.0f}%" if value >= 8 else ""),
        labels={"Percent": "Share of test condition (%)"},
        title=str(title),
    )
    fig.update_layout(
        height=max(300, 90 + 42 * len(work)),
        margin=dict(l=30, r=20, t=50, b=45),
        legend_title="Phase behaviour",
        xaxis_title="Share of test condition (%)",
        yaxis_title="Formulation",
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def _render_ift_chart(df: pd.DataFrame, title: str) -> None:
    if df.empty:
        st.info(f"{title}: no usable records in the workbook.")
        return
    work = df.sort_values("IFT High", ascending=False).copy()
    low = pd.to_numeric(work["IFT Low"], errors="coerce")
    high = pd.to_numeric(work["IFT High"], errors="coerce")
    work["Range"] = (high - low).clip(lower=0)
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            y=work["Material"],
            x=work["Range"],
            base=low,
            orientation="h",
            customdata=work[["IFT Low", "IFT High", "Year"]].to_numpy(),
            hovertemplate=(
                "%{y}<br>IFT low: %{customdata[0]:.4g} dynes/cm<br>"
                "IFT high: %{customdata[1]:.4g} dynes/cm<br>Year: %{customdata[2]}<extra></extra>"
            ),
        )
    )
    fig.update_layout(
        title=str(title),
        xaxis_title="IFT (dynes/cm)",
        yaxis_title="Material",
        height=max(310, 100 + 36 * len(work)),
        margin=dict(l=25, r=20, t=50, b=55),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def _render_fluid_fluid(data: dict) -> None:
    metadata = data["metadata"]
    _render_rheology(data["Vis_Shear"])
    st.caption(_fmt_source(metadata, "Vis_Shear"))

    st.markdown("#### Phase Behaviour Test")
    st.caption("Three source panels are kept separate so the historical formulations remain traceable.")
    c1, c2 = st.columns(2)
    with c1:
        _render_phase_chart(data["PB_2003"], "PB_2003 — Phase Behaviour")
        _render_phase_chart(data["PB_2013_A"], "PB_2013_A — Phase Behaviour")
    with c2:
        _render_phase_chart(data["PB_2013_B"], "PB_2013_B — Phase Behaviour")
        actual = metadata.get("source_map", {}).get("PB_2013_B")
        if actual and actual != "PB_2013_B":
            st.caption(f"PB_2013_B is represented by repository sheet `{actual}` in this workbook revision.")

    st.markdown("#### Interfacial Tension Test")
    c1, c2 = st.columns(2)
    with c1:
        _render_ift_chart(data["IFT_sur_F"], "Surfactant IFT Range")
        st.caption(_fmt_source(metadata, "IFT_sur_F"))
    with c2:
        _render_ift_chart(data["IFT_sur_T"], "Polymer IFT Range")
        actual = metadata.get("source_map", {}).get("IFT_sur_T")
        if actual and actual != "IFT_sur_T":
            st.caption(f"Polymer IFT panel is sourced from repository sheet `{actual}` in this workbook revision.")


def _render_adsorption(df: pd.DataFrame, metadata: dict) -> None:
    section_title("Adsorption Test", "Explore adsorption behaviour by the dimensions actually present in the source workbook.")
    if df.empty:
        st.warning("Adsorption contains no usable records.")
        return

    year_values = sorted(df["Year"].dropna().astype(int).unique().tolist())
    field_values = sorted(df["Field"].dropna().astype(str).unique().tolist(), key=str.casefold)
    material_values = sorted(df["Material"].dropna().astype(str).unique().tolist(), key=str.casefold)
    temp_values = sorted(df["Temperature"].dropna().unique().tolist()) if "Temperature" in df else []
    polymer_values = sorted(df["Polymer Type"].dropna().astype(str).unique().tolist(), key=str.casefold) if "Polymer Type" in df else []

    cols = st.columns(4 if (temp_values or polymer_values) else 3)
    with cols[0]:
        selected_years = st.multiselect("Year", year_values, default=year_values, key="ceor_ads_years")
    with cols[1]:
        selected_fields = st.multiselect("Field", field_values, default=field_values, key="ceor_ads_fields")
    with cols[2]:
        selected_materials = st.multiselect("Surfactant / formulation", material_values, default=material_values, key="ceor_ads_materials")
    if temp_values or polymer_values:
        with cols[3]:
            selected_temp = st.multiselect("Temperature", temp_values, default=temp_values, key="ceor_ads_temp")
            selected_polymer = st.multiselect("Polymer type", polymer_values, default=polymer_values, key="ceor_ads_polymer")
    else:
        selected_temp = []
        selected_polymer = []

    work = df.copy()
    if selected_years:
        work = work[work["Year"].isin(selected_years)]
    if selected_fields:
        work = work[work["Field"].isin(selected_fields)]
    if selected_materials:
        work = work[work["Material"].isin(selected_materials)]
    if temp_values and selected_temp:
        work = work[work["Temperature"].isin(selected_temp)]
    if polymer_values and selected_polymer:
        work = work[work["Polymer Type"].isin(selected_polymer)]

    if work.empty:
        st.info("No adsorption records match the selected filters.")
        return

    fig = px.line(
        work.sort_values(["Material", "Days"]),
        x="Days",
        y="Adsorption c/cO",
        color="Material",
        markers=True,
        hover_data=["Year", "Field"],
        labels={"Days": "Days", "Adsorption c/cO": "Adsorption c/c₀"},
    )
    fig.update_layout(height=440, margin=dict(l=50, r=20, t=30, b=70), legend_title="Surfactant / formulation")
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    st.caption(_fmt_source(metadata, "adsorption"))


def _render_coreflood(df: pd.DataFrame, metadata: dict) -> None:
    section_title("Core Flood", "Compare waterflood recovery with chemical-EOR recovery contributions, then inspect the full source table.")
    if df.empty:
        st.warning("Coreflood contains no usable records.")
        return
    components = ["Water Flood", "AS", "Polymer", "Alkaline", "Surfactant", "SP", "ASP"]
    available = [c for c in components if c in df.columns and pd.to_numeric(df[c], errors="coerce").notna().any()]
    if available:
        chart = df[["Core sample", "Year"] + available].copy()
        for column in available:
            chart[column] = pd.to_numeric(chart[column], errors="coerce").fillna(0)
        long = chart.melt(id_vars=["Core sample", "Year"], value_vars=available, var_name="Recovery component", value_name="Recovery (% OOIP)")
        fig = px.bar(long, x="Core sample", y="Recovery (% OOIP)", color="Recovery component", barmode="stack", hover_data=["Year"])
        fig.update_layout(height=520, margin=dict(l=35, r=20, t=30, b=110), xaxis_tickangle=-55, legend_title="Recovery component")
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    else:
        st.info("No recovery contribution columns were found for the core-flood chart.")
    st.dataframe(df, use_container_width=True, hide_index=True, height=440)
    st.caption(_fmt_source(metadata, "Coreflood"))


def _render_sor(df: pd.DataFrame, metadata: dict) -> None:
    section_title("Sor Reduction From a Core Flood", "Residual-oil-saturation reduction is the direct rock-response performance readout from the core-flood evidence.")
    if df.empty:
        st.warning("No Sor-reduction records were resolved from the workbook. Check that the updated `Sor_F` sheet is included in the repository workbook.")
        return
    fig = px.bar(
        df.sort_values(["Core sample", "Method"]),
        x="Core sample",
        y="Sor Reduction (%)",
        color="Method",
        barmode="group",
        hover_data=["Year"],
        labels={"Sor Reduction (%)": "Sor reduction (%)"},
    )
    fig.update_layout(height=460, margin=dict(l=45, r=20, t=30, b=110), xaxis_tickangle=-55, legend_title="Method")
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    st.caption(f"Sor source: `{metadata.get('sor_source') or 'not resolved'}`")


def render() -> None:
    try:
        data = load_ceor_evidence()
    except Exception as exc:
        st.error("CEOR evidence could not be loaded from the repository workbook.")
        st.caption(str(exc))
        return

    metadata = data["metadata"]
    insight_cards([
        ("FLUID / FLUID", "Rheology → Phase → IFT", "Establish whether the injected chemistry remains workable and interfacially effective before moving to rock-response evidence."),
        ("FLUID / ROCK", "Adsorption → Core Flood → Sor", "Trace whether the chemistry survives rock interaction and delivers incremental recovery."),
        ("EVIDENCE", "Workbook-backed", "Every chart is sourced from the repository engineering workbook, with source-sheet labels shown beside the evidence."),
    ])
    st.markdown("<div class='atlas-divider'></div>", unsafe_allow_html=True)

    fluid_fluid_tab, fluid_rock_tab = st.tabs(["Fluid / Fluid", "Fluid / Rock"])

    with fluid_fluid_tab:
        section_title("CEOR — Fluid / Fluid Interaction", _FF_DESC)
        try:
            _render_fluid_fluid(data)
        except Exception as exc:
            st.error("The CEOR Fluid / Fluid section could not be rendered.")
            st.caption(f"Technical detail: {exc}")

    with fluid_rock_tab:
        section_title("CEOR — Fluid / Rock Interaction", _FR_DESC)
        try:
            _render_adsorption(data["adsorption"], metadata)
        except Exception as exc:
            st.error("The Adsorption section could not be rendered.")
            st.caption(f"Technical detail: {exc}")
        try:
            _render_coreflood(data["Coreflood"], metadata)
        except Exception as exc:
            st.error("The Core Flood section could not be rendered.")
            st.caption(f"Technical detail: {exc}")
        try:
            _render_sor(data["Sor_F"], metadata)
        except Exception as exc:
            st.error("The Sor Reduction section could not be rendered.")
            st.caption(f"Technical detail: {exc}")

    missing = metadata.get("missing_requested_sheets") or []
    if missing:
        with st.expander("Workbook source notes", expanded=False):
            st.write("Exact requested sheet names not found: " + ", ".join(str(name) for name in missing))
            st.write("Where an equivalent alias exists, the page uses it and shows the actual source sheet beside the chart.")
            st.code(metadata.get("workbook") or "")
