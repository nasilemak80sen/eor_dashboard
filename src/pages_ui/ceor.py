"""CEOR evidence workspace.

The page keeps the intent of the PDF CEOR pages but uses the repository
engineering workbook as its source of truth. Fluid/Fluid asks: "does the
injected chemistry behave well with the fluid system?" Fluid/Rock asks:
"does the chemistry survive rock interaction and demonstrate incremental
recovery / Sor reduction?".
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
    actual = metadata.get("source_map", {}).get(requested, requested)
    return f"Source sheet: `{actual}`"


def _render_rheology(df: pd.DataFrame) -> None:
    section_title("Rheology", "Apparent viscosity versus shear rate. Compare polymer behaviour across years and formulations.")
    if df.empty:
        st.warning("Vis_Shear contains no usable rheology records.")
        return
    year_options = sorted(df["Year"].dropna().astype(int).unique().tolist())
    polymer_options = sorted(df["Polymer"].dropna().astype(str).unique().tolist(), key=str.casefold)
    a, b = st.columns([1, 2])
    with a:
        years = st.multiselect("Year", year_options, default=year_options, key="ceor_rheo_years")
    with b:
        polymers = st.multiselect("Polymer type", polymer_options, default=polymer_options, key="ceor_rheo_polymers")
    work = df.copy()
    if years:
        work = work[work["Year"].isin(years)]
    if polymers:
        work = work[work["Polymer"].isin(polymers)]
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
        st.info(f"{title}: no records available in the repository workbook.")
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
    fig = px.bar(
        long,
        x="Percent",
        y="Formulation",
        color="Outcome",
        orientation="h",
        barmode="stack",
        text=long["Percent"].map(lambda x: f"{x:.0f}%" if x >= 8 else ""),
        labels={"Percent": "Share of test condition (%)", "Formulation": None},
        title=title,
    )
    fig.update_layout(height=max(300, 90 + 42 * len(work)), margin=dict(l=30, r=20, t=50, b=45), legend_title="Phase behaviour")
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def _render_ift_chart(df: pd.DataFrame, title: str) -> None:
    if df.empty:
        st.info(f"{title}: no records available in the repository workbook.")
        return
    work = df.sort_values("IFT High", ascending=False).copy()
    work["Range"] = work["IFT High"] - work["IFT Low"]
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            y=work["Material"],
            x=work["Range"],
            base=work["IFT Low"],
            orientation="h",
            customdata=work[["IFT Low", "IFT High", "Year"]],
            hovertemplate=(
                "%{y}<br>IFT low: %{customdata[0]:.4g} dynes/cm<br>"
                "IFT high: %{customdata[1]:.4g} dynes/cm<br>Year: %{customdata[2]}<extra></extra>"
            ),
        )
    )
    fig.update_layout(
        title=title,
        xaxis_title="IFT (dynes/cm)",
        yaxis_title=None,
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
    st.caption("Each panel shows the formulation-level split between precipitation and no-precipitation outcomes.")
    c1, c2 = st.columns(2)
    with c1:
        _render_phase_chart(data["PB_2003"], "PB_2003 — Phase Behaviour")
        _render_phase_chart(data["PB_2013_A"], "PB_2013_A — Phase Behaviour")
    with c2:
        _render_phase_chart(data["PB_2013_B"], "PB_2013_B — Phase Behaviour")
        actual = metadata.get("source_map", {}).get("PB_2013_B")
        if actual and actual != "PB_2013_B":
            st.caption(f"PB_2013_B is represented by repository sheet `{actual}` in the current workbook revision.")

    st.markdown("#### Interfacial Tension Test")
    c1, c2 = st.columns(2)
    with c1:
        _render_ift_chart(data["IFT_sur_F"], "Surfactant IFT Range")
        st.caption(_fmt_source(metadata, "IFT_sur_F"))
    with c2:
        _render_ift_chart(data["IFT_sur_T"], "Polymer IFT Range")
        actual = metadata.get("source_map", {}).get("IFT_sur_T")
        if actual and actual != "IFT_sur_T":
            st.caption(f"Polymer IFT panel is sourced from repository sheet `{actual}` in the current workbook revision.")


def _render_adsorption(df: pd.DataFrame, metadata: dict) -> None:
    section_title("Adsorption Test", "Track chemical retention on rock over time. Filter using the fields actually present in the Adsorption source.")
    if df.empty:
        st.warning("Adsorption contains no usable records.")
        return
    years = sorted(df["Year"].dropna().astype(int).unique().tolist())
    materials = sorted(df["Material"].dropna().astype(str).unique().tolist(), key=str.casefold)
    fields = sorted(df["Field"].dropna().astype(str).unique().tolist(), key=str.casefold)
    a, b, c = st.columns(3)
    with a:
        selected_years = st.multiselect("Year", years, default=years, key="ceor_ads_years")
    with b:
        selected_fields = st.multiselect("Field", fields, default=fields, key="ceor_ads_fields")
    with c:
        selected_materials = st.multiselect("Surfactant / formulation", materials, default=materials, key="ceor_ads_materials")
    work = df.copy()
    if selected_years:
        work = work[work["Year"].isin(selected_years)]
    if selected_fields:
        work = work[work["Field"].isin(selected_fields)]
    if selected_materials:
        work = work[work["Material"].isin(selected_materials)]
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

    context_temps = metadata.get("adsorption_context_temperatures", [])
    context_polymers = metadata.get("adsorption_context_polymer_types", [])
    if context_temps or context_polymers:
        st.caption(
            "Thermal-sheet context is available for year / temperature / polymer exploration, "
            "but those fields are not present on Adsorption itself and are therefore not used to fabricate adsorption links."
        )
    else:
        st.info("Temperature and polymer type are not columns in the repository Adsorption sheet; the chart is filtered only by the source fields available.")
    st.caption(_fmt_source(metadata, "adsorption"))


def _render_coreflood(df: pd.DataFrame) -> None:
    section_title("Core Flood", "Compare waterflood recovery with chemical-EOR recovery contributions, then inspect the complete core-flood register.")
    if df.empty:
        st.warning("Coreflood contains no usable records.")
        return
    components = ["Water Flood", "AS", "Polymer", "Alkaline", "Surfactant", "SP", "ASP"]
    available = [c for c in components if c in df.columns and pd.to_numeric(df[c], errors="coerce").notna().any()]
    chart = df[["Core sample", "Year"] + available].copy()
    for column in available:
        chart[column] = pd.to_numeric(chart[column], errors="coerce").fillna(0)
    long = chart.melt(id_vars=["Core sample", "Year"], value_vars=available, var_name="Recovery component", value_name="Recovery (% OOIP)")
    fig = px.bar(
        long,
        x="Core sample",
        y="Recovery (% OOIP)",
        color="Recovery component",
        barmode="stack",
        hover_data=["Year"],
    )
    fig.update_layout(height=520, margin=dict(l=35, r=20, t=30, b=110), xaxis_tickangle=-55, legend_title="Recovery component")
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    st.dataframe(df, use_container_width=True, hide_index=True, height=440)


def _render_sor(df: pd.DataFrame, metadata: dict) -> None:
    section_title("Sor Reduction From a Core Flood", "Residual-oil-saturation reduction is the direct rock-response performance readout from the core-flood evidence.")
    if df.empty:
        st.warning("Sor_F is unavailable and no Sor-reduction fields could be derived from Coreflood.")
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
    st.caption(f"Sor source: `{metadata.get('sor_source')}`")


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
        _render_fluid_fluid(data)
    with fluid_rock_tab:
        section_title("CEOR — Fluid / Rock Interaction", _FR_DESC)
        _render_adsorption(data["adsorption"], metadata)
        _render_coreflood(data["Coreflood"])
        _render_sor(data["Sor_F"], metadata)

    missing = metadata.get("missing_requested_sheets", [])
    if missing:
        with st.expander("Workbook source notes", expanded=False):
            st.write("The current repository workbook does not contain these exact requested sheet names: " + ", ".join(missing))
            st.write("Where a source-equivalent sheet exists, the page shows the actual repository sheet name. No missing source values are fabricated.")
            st.code(metadata.get("workbook", ""))
