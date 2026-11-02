"""R&D laboratory page: St. Joseph CEOR and Baronia WAG."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from data.rd_lab_evidence import load_st_jos_ceor
from pages_ui.ceor import render_compact as render_legacy_ceor


def _metric_row(items: list[tuple[str, str, str]]) -> None:
    cols = st.columns(len(items))
    for col, (label, value, help_text) in zip(cols, items):
        with col:
            st.metric(label, value, help=help_text)


def _render_rheology(df: pd.DataFrame, meta: dict) -> None:
    st.markdown("#### Polymer rheology")
    st.caption(
        "Apparent viscosity against measured shear rate. Filter to one polymer and "
        "experimental condition before comparing curves."
    )
    if df.empty:
        st.info("No complete shear-rate/viscosity pairs are available.")
        return

    c1, c2, c3, c4 = st.columns(4)
    years = sorted(df["Year"].dropna().astype(int).unique().tolist())
    polymers = sorted(df["Polymer"].dropna().astype(str).unique().tolist())
    salinities = sorted(df["Salinity (mg/L TDS)"].dropna().unique().tolist())
    concentrations = sorted(df["Concentration (ppm)"].dropna().unique().tolist())
    with c1:
        year = st.selectbox("Year", ["All"] + years, key="rd_rheo_year")
    with c2:
        polymer = st.selectbox("Polymer", ["All"] + polymers, key="rd_rheo_polymer")
    with c3:
        selected_salinity = st.multiselect(
            "Salinity (mg/L TDS)", salinities, default=salinities, key="rd_rheo_salinity"
        )
    with c4:
        selected_concentration = st.multiselect(
            "Concentration (ppm)", concentrations, default=concentrations,
            key="rd_rheo_concentration",
        )

    work = df.copy()
    if year != "All":
        work = work[work["Year"] == year]
    if polymer != "All":
        work = work[work["Polymer"] == polymer]
    if selected_salinity:
        work = work[work["Salinity (mg/L TDS)"].isin(selected_salinity)]
    if selected_concentration:
        work = work[work["Concentration (ppm)"].isin(selected_concentration)]
    if work.empty:
        st.info("No rheology observations match the selected conditions.")
        return

    fig = px.line(
        work.sort_values("Shear rate (1/sec)"),
        x="Shear rate (1/sec)",
        y="Apparent viscosity (cP)",
        color="Salinity (mg/L TDS)",
        line_dash="Concentration (ppm)",
        facet_col="Year" if year == "All" else None,
        markers=True,
        hover_data=["Polymer", "Year", "Salinity (mg/L TDS)", "Concentration (ppm)"],
        labels={
            "Shear rate (1/sec)": "Shear rate (1/sec)",
            "Apparent viscosity (cP)": "Apparent viscosity (cP)",
        },
    )
    fig.update_layout(
        height=340, margin=dict(l=35, r=15, t=35, b=45),
        legend_title="Salinity / concentration", template="plotly_white",
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    st.caption(
        f"{len(work):,} plotted observations. {meta['rheology_missing_shear_rate_rows']} "
        "source rows lack shear rate and are not included in this curve."
    )


def _render_phase_tests(df: pd.DataFrame) -> None:
    st.markdown("#### Precipitation screening tests")
    if df.empty:
        st.info("No phase-behaviour screening tests were loaded.")
        return
    sources = {
        "2003 surfactant/polymer tests": "PB_2003",
        "2013 alkali/surfactant tests": "PB_2013_A",
        "2013 surfactant blend tests": "PB_2013_S",
    }
    selected = st.selectbox(
        "Test series", list(sources), key="rd_phase_test_series"
    )
    work = df[df["Source sheet"] == sources[selected]].copy()
    if work.empty:
        st.info("No tests in this series.")
        return
    work["Precipitation (%)"] = work["Precipitation"] * 100
    work["No precipitation (%)"] = work["No Precipitation"] * 100
    long = work.melt(
        id_vars=["Formulation", "Test", "Remarks"],
        value_vars=["No precipitation (%)", "Precipitation (%)"],
        var_name="Reported outcome",
        value_name="Reported share (%)",
    )
    fig = px.bar(
        long, x="Reported share (%)", y="Formulation", color="Reported outcome",
        orientation="h", barmode="stack",
        hover_data=["Test", "Remarks"],
        labels={"Reported share (%)": "Reported outcome share (%)"},
        color_discrete_sequence=["#9CA3AF", "#0F9D91"],
    )
    fig.update_layout(
        height=max(280, min(430, 105 + 23 * len(work))),
        margin=dict(l=20, r=12, t=18, b=42), template="plotly_white",
        legend_title="Source outcome",
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    st.caption(
        f"{len(work)} formulations/tests from {sources[selected]}. The percentages "
        "are displayed as recorded in the workbook; they are not reclassified as pass/fail."
    )
    with st.expander("View individual phase-test records"):
        st.dataframe(work, use_container_width=True, hide_index=True)


def _render_phase_diagram(df: pd.DataFrame) -> None:
    st.markdown("#### Salinity/solubilization phase diagram")
    if df.empty:
        st.info("No tidy phase-point records are available.")
        return
    formulations = sorted(df["Formulation"].dropna().unique().tolist(), key=str)
    col1, col2 = st.columns([2, 1])
    with col1:
        formulation = st.selectbox("Formulation", formulations, index=0, key="rd_phase_formulation")
    with col2:
        validated_only = st.checkbox("Validated points only", value=True, key="rd_phase_validated")
    work = df[df["Formulation"] == formulation].copy()
    if validated_only:
        work = work[work["Validated"].str.upper() == "Y"]
    if work.empty:
        st.info("No points match the selected validation filter.")
        return

    fig = px.scatter(
        work, x="TDS (wt%)", y="Solubilization (cc/cc)", color="Phase",
        symbol="Phase", hover_data=["Figure", "Page", "Validated"],
        color_discrete_sequence=["#0F9D91", "#D97706"],
    )
    marker_row = work.dropna(subset=["Intersection", "Type III region min", "Type III region max"])
    if not marker_row.empty:
        marker = marker_row.iloc[0]
        fig.add_vrect(
            x0=float(marker["Type III region min"]), x1=float(marker["Type III region max"]),
            fillcolor="#0F9D91", opacity=0.10, line_width=0,
            annotation_text="Reported Type III region", annotation_position="top left",
        )
        fig.add_vline(
            x=float(marker["Intersection"]), line_dash="dash", line_color="#0F766E",
            annotation_text=f"Intersection {marker['Intersection']:g} wt%",
        )
    fig.update_layout(
        height=340, margin=dict(l=35, r=15, t=28, b=42),
        template="plotly_white", legend_title="Phase",
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    st.caption(
        f"Formulation {formulation}: {len(work)} plotted points. "
        "The shaded region and intersection are shown only where reported in the source."
    )


def _render_ift_chart(df: pd.DataFrame, title: str) -> None:
    if df.empty:
        st.info(f"No {title.lower()} records were loaded.")
        return
    fig = go.Figure()
    for column, label, symbol in (
        ("IFT low (source)", "IFT low (as labelled in source)", "circle"),
        ("IFT high (source)", "IFT high (as labelled in source)", "triangle-up"),
    ):
        part = df.dropna(subset=[column])
        custom = part[["IFT low raw", "IFT high raw", "IFT high is censored"]].astype(str).to_numpy()
        fig.add_trace(go.Scatter(
            x=part[column], y=part["Material"], mode="markers", name=label,
            marker={"size": 10, "symbol": symbol},
            customdata=custom,
            hovertemplate=(
                "%{y}<br>Plotted value: %{x:.5g} dynes/cm"
                "<br>Source low: %{customdata[0]}"
                "<br>Source high: %{customdata[1]}"
                "<br>High value censored: %{customdata[2]}<extra></extra>"
            ),
        ))
    fig.update_xaxes(type="log", title="IFT (dynes/cm)")
    fig.update_yaxes(title="")
    fig.update_layout(
        title=title, height=max(290, 80 + 28 * len(df)),
        margin=dict(l=20, r=12, t=45, b=42),
        template="plotly_white", legend_title="Source column",
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def _render_ift(data: dict) -> None:
    st.markdown("#### Interfacial tension")
    left, right = st.columns(2)
    with left:
        _render_ift_chart(data["ift_surfactant"], "Surfactant IFT")
    with right:
        _render_ift_chart(data["ift_polymer"], "Polymer IFT")
    reversed_count = data["metadata"]["ift_polymer_reversed_bounds"]
    if reversed_count:
        st.warning(
            f"Source-data quality flag: {reversed_count} of {len(data['ift_polymer'])} "
            "polymer rows report 'IFT low' greater than 'IFT high'. Values are plotted "
            "under their original column labels and have not been swapped or corrected."
        )
    if data["ift_surfactant"]["IFT high is censored"].any():
        st.caption(
            "At least one surfactant IFT result is reported as a detection limit "
            "(for example, '<0.001'). The marker is placed at the stated limit and "
            "retains the original text in its hover details."
        )


def _render_fluid_fluid(data: dict) -> None:
    meta = data["metadata"]
    _metric_row([
        ("Rheology points", f"{meta['rheology_plot_rows']:,}", "Rows with both shear rate and apparent viscosity"),
        ("Phase formulations", str(meta["phase_formulations"]), "Distinct formulations in the tidy phase-point sheet"),
        ("Phase tests", str(meta["phase_test_rows"]), "Rows across PB_2003, PB_2013_A and PB_2013_S"),
        ("IFT records", str(meta["ift_rows"]), "Surfactant and polymer records combined"),
    ])
    rheology, phase, ift = st.tabs(["Rheology", "Phase behaviour", "IFT"])
    with rheology:
        _render_rheology(data["rheology_plot"], meta)
    with phase:
        tests, diagram = st.tabs(["Precipitation tests", "Phase diagram"])
        with tests:
            _render_phase_tests(data["phase_tests"])
        with diagram:
            _render_phase_diagram(data["phase_points"])
    with ift:
        _render_ift(data)


def _render_adsorption(df: pd.DataFrame) -> None:
    st.markdown("#### Static adsorption")
    if df.empty:
        st.info("No St. Joseph adsorption records were found.")
        return
    mean_ratio = df["Adsorption ratio"].mean()
    _metric_row([
        ("Test records", str(len(df)), "Source records in Adsorption (St_Jos)"),
        ("Mean adsorption", f"{mean_ratio:.0%}", "Mean reported c/c₀ ratio"),
        ("Test duration", f"{df['Days'].dropna().iloc[0]:g} days" if df["Days"].notna().any() else "Not stated", "Duration recorded in the source"),
    ])
    fig = px.bar(
        df, x="Surfactant", y="Adsorption (%)", color="Surfactant",
        text=df["Adsorption (%)"].map(lambda x: f"{x:.0f}%"),
        hover_data=["Sample", "Year", "Days", "Adsorption (mg/g, source note)", "Source note"],
        labels={"Adsorption (%)": "Adsorption ratio (%)"},
        color_discrete_sequence=["#0F9D91", "#D97706"],
    )
    fig.update_layout(
        height=300, showlegend=False,
        margin=dict(l=20, r=12, t=18, b=55), template="plotly_white",
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    st.caption("Only two St. Joseph static-adsorption tests are present. Avoid generalising these results beyond the tested formulations and conditions.")
    with st.expander("View adsorption source records"):
        st.dataframe(df, use_container_width=True, hide_index=True)


def _render_coreflood(data: dict) -> None:
    st.markdown("#### Core-flood recovery")
    water = data["waterflood"]
    if water.empty:
        st.info("No water-flood recovery records were found.")
        return
    mean_wf = water["Water flood recovery (% OOIP)"].mean()
    _metric_row([
        ("Core samples", str(water["Core sample"].nunique()), "Distinct core samples"),
        ("Mean waterflood recovery", f"{mean_wf:.1f}%", "Arithmetic mean of reported % OOIP values"),
        ("Treatment groups", str(water["Treatment type"].nunique()), "Treatment codes exactly as listed in the source summary"),
    ])
    fig = px.bar(
        water.sort_values("Water flood recovery (% OOIP)"),
        x="Water flood recovery (% OOIP)", y="Core sample",
        color="Treatment type", orientation="h",
        hover_data=["Year"],
        labels={"Water flood recovery (% OOIP)": "Water-flood recovery (% OOIP)"},
        color_discrete_sequence=px.colors.qualitative.Safe,
    )
    fig.update_layout(
        height=390, margin=dict(l=20, r=12, t=18, b=42),
        template="plotly_white", legend_title="Source treatment type",
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    stages = data["chemical_stage_recovery"]
    if not stages.empty:
        st.markdown("**Reported chemical-stage recovery**")
        stage_fig = px.scatter(
            stages, x="Core sample", y="Reported chemical-stage recovery (% OOIP)",
            color="Method", symbol="Method", hover_data=["Year"],
            labels={"Reported chemical-stage recovery (% OOIP)": "Reported recovery (% OOIP)"},
        )
        stage_fig.update_layout(
            height=280, margin=dict(l=25, r=12, t=18, b=45),
            template="plotly_white", legend_title="Method",
        )
        st.plotly_chart(stage_fig, use_container_width=True, config={"displayModeBar": False})
        st.caption(
            "Only the source's explicitly named Surfactant (S), Alkaline–surfactant (AS) "
            "and Polymer (P) chemical-stage recovery columns are included here. The "
            "AS,P recovery-factor column is not treated as an incremental recovery value."
        )
    with st.expander("View core-flood sample and formulation records"):
        st.dataframe(data["coreflood_summary"], use_container_width=True, hide_index=True)
        st.dataframe(water, use_container_width=True, hide_index=True)


def _render_sor(data: dict) -> None:
    st.markdown("#### Residual-oil-saturation reduction")
    sor = data["sor_reduction"]
    if sor.empty:
        st.info("No Sor-reduction values were found.")
        return
    method_summary = (
        sor.groupby("Method", as_index=False)
        .agg(Records=("Sor reduction (%)", "count"), Mean=("Sor reduction (%)", "mean"), Maximum=("Sor reduction (%)", "max"))
    )
    c1, c2 = st.columns([2, 1])
    with c1:
        fig = px.bar(
            sor.sort_values("Sor reduction (%)"),
            x="Sor reduction (%)", y="Core sample", color="Method",
            orientation="h", hover_data=["Year", "Source field"],
            labels={"Sor reduction (%)": "Sor reduction (%)"},
        )
        fig.update_layout(
            height=max(300, min(430, 115 + 22 * len(sor))),
            margin=dict(l=20, r=12, t=18, b=42), template="plotly_white",
            legend_title="Treatment method",
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    with c2:
        st.markdown("**Method summary**")
        summary = method_summary.copy()
        summary["Mean"] = summary["Mean"].map(lambda x: f"{x:.1f}%")
        summary["Maximum"] = summary["Maximum"].map(lambda x: f"{x:.1f}%")
        st.dataframe(summary, use_container_width=True, hide_index=True)
    st.caption(
        "The source contains 16 reported Sor-reduction records across five treatment "
        "labels. These are sparse, unbalanced groups; the method averages are descriptive, "
        "not a controlled ranking of efficacy."
    )
    with st.expander("View Sor-reduction source records"):
        st.dataframe(sor, use_container_width=True, hide_index=True)


def _render_fluid_rock(data: dict) -> None:
    _metric_row([
        ("Core-flood samples", str(data["metadata"]["coreflood_samples"]), "Distinct St. Joseph core samples"),
        ("Sor records", str(data["metadata"]["sor_records"]), "Non-empty source Sor-reduction measurements"),
        ("Adsorption tests", str(data["metadata"]["adsorption_rows"]), "Static adsorption records"),
        ("Treatment methods", str(data["coreflood_summary"]["Treatment type"].nunique()), "Treatment labels from the core-flood summary"),
    ])
    adsorption, coreflood, sor = st.tabs(["Adsorption", "Core flood", "Sor reduction"])
    with adsorption:
        _render_adsorption(data["adsorption"])
    with coreflood:
        _render_coreflood(data)
    with sor:
        _render_sor(data)


def _render_wag_locked() -> None:
    st.markdown("### Baronia · Water Alternating Gas")
    st.caption("WAG source workbook is registered separately from the CEOR evidence.")
    st.warning(
        "The Baronia workbook supplied in this conversation is an encrypted Excel "
        "container. Its worksheets and measurements cannot be read yet, so no WAG "
        "charts or values have been inferred. Please provide an unencrypted .xlsx "
        "copy or the workbook-open password."
    )
    st.info(
        "Once readable, the WAG analysis will be mapped to the actual sheet schema, "
        "including injection sequence/cycle, water and gas slug volumes, rates, "
        "pressure response and recovery metrics only where those fields exist."
    )


def render() -> None:
    st.markdown("## R&D Laboratory")
    st.caption(
        "Field-specific laboratory evidence, separated by EOR method and experimental interaction."
    )
    method = st.segmented_control(
        "Laboratory method",
        options=["CEOR", "WAG"],
        default="CEOR",
        key="rd_method",
        label_visibility="collapsed",
        format_func=lambda value: (
            "CEOR · Chemical EOR" if value == "CEOR"
            else "WAG · Water Alternating Gas"
        ),
    )
    if method == "WAG":
        _render_wag_locked()
        return

    data = None
    try:
        data = load_st_jos_ceor()
    except Exception as exc:
        st.error("St. Joseph CEOR evidence could not be loaded.")
        with st.expander("Technical detail"):
            st.exception(exc)
        return

    st.markdown("### St. Joseph · Chemical EOR")
    st.caption("Source: St_Jos CEOR (Shared) (1).xlsx · 2010–2013 laboratory evidence")
    submethod = st.segmented_control(
        "CEOR methodology",
        options=["Fluid–Fluid", "Fluid–Rock"],
        default="Fluid–Fluid",
        key="rd_ceor_submethod",
        label_visibility="collapsed",
    )
    if submethod == "Fluid–Rock":
        _render_fluid_rock(data)
    else:
        _render_fluid_fluid(data)

    with st.expander("Legacy CEOR evidence from the EOR Screening Tool workbook"):
        st.caption(
            "This preserves the pre-existing CEOR panels as a separate legacy source. "
            "It is not blended into St. Joseph field-level statistics."
        )
        render_legacy_ceor()

    meta = data["metadata"]
    with st.expander("Workbook and data-quality notes"):
        st.write({
            "Workbook": meta["workbook_name"],
            "Rheology source rows": meta["rheology_source_rows"],
            "Rheology rows plotted": meta["rheology_plot_rows"],
            "Rheology rows without shear rate": meta["rheology_missing_shear_rate_rows"],
            "Phase points": meta["phase_point_rows"],
            "Validated phase points": meta["phase_validated_rows"],
            "IFT rows with reversed polymer bounds": meta["ift_polymer_reversed_bounds"],
            "Missing required sheets": meta["missing_sheets"],
        })
