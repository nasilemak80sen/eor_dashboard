"""R&D laboratory page with CEOR field filtering and a separate WAG category."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from data.rd_lab_evidence import load_st_jos_ceor
from data.baronia_wag_evidence import load_baronia_wag
from data.ceor_evidence import load_ceor_evidence
from pages_ui.ceor import (
    _render_adsorption as _render_primary_adsorption,
    _render_coreflood as _render_primary_coreflood,
    _render_fluid_fluid as _render_primary_fluid_fluid,
    _render_sor as _render_primary_sor,
)


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
        formulation = st.selectbox("Formulation", formulations, index=formulations.index("7") if "7" in formulations else 0, key="rd_phase_formulation")
    with col2:
        validated_only = st.checkbox("Validated points only", value=False, key="rd_phase_validated")
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
        df, y="Surfactant", x="Adsorption (%)", color="Surfactant",
        orientation="h", text=df["Adsorption (%)"].map(lambda x: f"{x:.0f}%"),
        hover_data=["Sample", "Year", "Days", "Adsorption (mg/g, source note)", "Source note"],
        labels={"Adsorption (%)": "Adsorption ratio (%)"},
        color_discrete_sequence=["#0F9D91", "#D97706"],
    )
    fig.update_layout(
        height=260, showlegend=False,
        margin=dict(l=20, r=12, t=18, b=42), template="plotly_white",
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

    factors = data["recovery_factors"]
    if not factors.empty:
        st.markdown("**Reported recovery factor**")
        factor_fig = px.scatter(
            factors, x="Core sample", y="Recovery factor (%)",
            color="Method", symbol="Method", hover_data=["Year"],
            labels={"Recovery factor (%)": "Recovery factor (%)"},
        )
        factor_fig.update_layout(
            height=280, margin=dict(l=25, r=12, t=18, b=45),
            template="plotly_white", legend_title="Reported method",
        )
        st.plotly_chart(factor_fig, use_container_width=True, config={"displayModeBar": False})
        st.caption(
            "Recovery factor is kept separate from the reported chemical-stage recovery "
            "(% OOIP); the two source metrics are not added together."
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




def _wag_lookup(frame: pd.DataFrame, key: str, *, key_col: str, value_col: str):
    if frame.empty or key_col not in frame.columns or value_col not in frame.columns:
        return None
    rows = frame.loc[frame[key_col].astype(str).str.strip().str.casefold() == key.casefold()]
    return rows.iloc[0][value_col] if not rows.empty else None


def _wag_display(value, unit: str = "") -> str:
    if value is None or pd.isna(value):
        return "Not reported"
    if isinstance(value, (int, float)):
        body = f"{value:,.2f}".rstrip("0").rstrip(".")
    else:
        body = str(value)
    return f"{body} {unit}".strip()


def _render_wag_performance(data: dict) -> None:
    recovery = data["recovery_curve"]
    cycles = data["cycle_recovery"]
    production = data["production_curve"]

    st.markdown("#### Coreflood recovery performance")
    if recovery.empty:
        st.info("No oil-recovery-versus-PV records were found.")
    else:
        fig = px.line(
            recovery.sort_values("PV Injected"),
            x="PV Injected", y="Oil Recovery (%)", markers=True,
            hover_data=["Oil Recovery (Fraction)", "Injection Phase"],
            labels={"PV Injected": "Pore volumes injected (PV)", "Oil Recovery (%)": "Oil recovery (% OOIP)"},
        )
        fig.add_hline(y=64, line_dash="dot", annotation_text="Summary waterflood: 64%")
        fig.add_hline(y=87, line_dash="dash", annotation_text="Reported final recovery: 87%")
        fig.update_layout(height=370, template="plotly_white", margin=dict(l=35, r=15, t=30, b=40))
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        st.caption("The source curve marks 65% at the end of primary waterflood, while the summary reports 64%. Both are retained.")

    left, right = st.columns(2)
    with left:
        st.markdown("#### Incremental recovery by injection stage")
        if not cycles.empty:
            post_wf = cycles.loc[~cycles["Injection Cycle"].astype(str).str.casefold().eq("primary waterflood")]
            cycle_fig = px.bar(
                post_wf, x="Injection Cycle", y="Incremental Recovery (%)",
                color="Injection Cycle", hover_data=["PV Start", "PV End", "Recovery at End (%)"],
                labels={"Incremental Recovery (%)": "Incremental recovery (percentage points)"},
            )
            cycle_fig.update_layout(height=340, template="plotly_white", showlegend=False, margin=dict(l=20, r=10, t=25, b=70))
            cycle_fig.update_xaxes(tickangle=-25)
            st.plotly_chart(cycle_fig, use_container_width=True, config={"displayModeBar": False})
        else:
            st.info("No injection-cycle recovery table was found.")
    with right:
        st.markdown("#### Cumulative production")
        if not production.empty:
            long = production.melt(
                id_vars=["PV Injected", "Injection Phase"],
                value_vars=["Cumulative Oil (cc)", "Cumulative Gas (cc)", "Cumulative Water (cc)"],
                var_name="Produced phase", value_name="Cumulative volume (cc)",
            )
            fig = px.line(long, x="PV Injected", y="Cumulative volume (cc)", color="Produced phase", markers=True)
            fig.update_layout(height=340, template="plotly_white", margin=dict(l=20, r=10, t=25, b=40))
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        else:
            st.info("No cumulative production records were found.")

    with st.expander("View recovery and production source records"):
        st.dataframe(recovery, use_container_width=True, hide_index=True)
        st.dataframe(cycles, use_container_width=True, hide_index=True)
        st.dataframe(production, use_container_width=True, hide_index=True)


def _render_wag_injection_model(data: dict) -> None:
    design = data["design_parameters"]
    st.markdown("#### Injection design")
    cards = [
        ("Injection rate", "Injection Rate", "cc/min"),
        ("Initial waterflood", "First Waterflood", "PV"),
        ("Gas slug / cycle", "Gas Slug Size", "PV"),
        ("Water slug / cycle", "Water Slug Size", "PV"),
        ("WAG cycles", "Number of WAG Cycles", "cycles"),
        ("System temperature", "System Temperature", "°C"),
        ("Pore pressure / BPR", "Pore Pressure / BPR", "psig"),
        ("Watercut at WAG start", "Watercut at WAG Start", "%"),
    ]
    cols = st.columns(4)
    for i, (label, key, unit) in enumerate(cards):
        value = _wag_lookup(design, key, key_col="Parameter", value_col="Value")
        cols[i % 4].metric(label, _wag_display(value, unit))

    st.caption("Equal 0.2 PV gas and water slugs imply a 1:1 per-cycle slug-size ratio. The separate WAG Ratio cell is time-formatted and is withheld pending source confirmation.")

    gas = data["gas_composition"]
    if not gas.empty:
        st.markdown("#### Baronia export-gas composition")
        fig = px.bar(gas.sort_values("Mol%"), x="Mol%", y="Component", orientation="h", hover_data=["Notes"])
        fig.update_layout(height=430, template="plotly_white", margin=dict(l=25, r=15, t=20, b=35))
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        st.caption(f"{len(gas)} components total {data['metadata']['gas_composition_total_mol_pct']:.2f} mol% excluding the explicit Total row.")

    left, right = st.columns(2)
    with left:
        st.markdown("#### WAGHYSTR hysteresis parameters")
        st.dataframe(data["hysteresis_model"], use_container_width=True, hide_index=True)
        st.markdown("#### Land trapped-gas correlation")
        st.dataframe(data["trapped_gas"], use_container_width=True, hide_index=True)
    with right:
        st.markdown("#### Corey relative-permeability parameters")
        st.dataframe(data["corey_parameters"], use_container_width=True, hide_index=True)
        st.markdown("#### Simulation model properties")
        st.dataframe(data["simulation_properties"], use_container_width=True, hide_index=True)


def _render_wag_field_core(data: dict) -> None:
    left, right = st.columns(2)
    with left:
        st.markdown("#### Reservoir properties · RV2")
        st.dataframe(data["reservoir_properties"], use_container_width=True, hide_index=True)
        st.markdown("#### Composite core properties")
        st.dataframe(data["composite_core"], use_container_width=True, hide_index=True)
    with right:
        st.markdown("#### Fluid properties · RV2")
        st.dataframe(data["fluid_properties"], use_container_width=True, hide_index=True)
        st.markdown("#### Special core analysis (SCAL)")
        st.dataframe(data["scal_summary"], use_container_width=True, hide_index=True)

    cores = data["core_samples"]
    if not cores.empty:
        st.markdown("#### BN-69 RV2 routine core analysis")
        fig = px.scatter(
            cores, x="Kh (md)", y="Porosity (%)", color="Facies", symbol="Selected",
            hover_data=["Sample", "Depth (ft)", "Kv (md)", "Kv/Kh"],
            labels={"Kh (md)": "Horizontal permeability (mD)"},
        )
        fig.update_layout(height=360, template="plotly_white", margin=dict(l=25, r=15, t=20, b=40))
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        selected = cores.loc[cores["Selected"].astype(str).str.strip().str.casefold().eq("yes")]
        st.caption(f"{len(cores)} core samples listed; {len(selected)} selected plugs are identified for the composite experiment.")
    with st.expander("View core samples and facies descriptions"):
        st.dataframe(cores, use_container_width=True, hide_index=True)
        st.dataframe(data["facies"], use_container_width=True, hide_index=True)


def _render_wag_quality(data: dict) -> None:
    issues = data["quality_issues"]
    if not issues.empty:
        high = int(issues["Severity"].eq("High").sum())
        review = int(issues["Severity"].eq("Review").sum())
        st.warning(f"Workbook QA identified {len(issues)} issues: {high} high-priority and {review} requiring review. Source values are preserved, not silently corrected.")
        st.dataframe(issues, use_container_width=True, hide_index=True)
    else:
        st.success("No automated workbook consistency flags were triggered.")

    with st.expander("Recovery values reported by each workbook section"):
        st.markdown("**Coreflood recovery summary**")
        st.dataframe(data["recovery_summary"], use_container_width=True, hide_index=True)
        st.markdown("**IWAG Results sheet**")
        st.dataframe(data["iwag_recovery"], use_container_width=True, hide_index=True)
        st.markdown("**EOR ATLAS Summary sheet**")
        st.dataframe(data["summary_metrics"], use_container_width=True, hide_index=True)

    with st.expander("Raw saturation values · not suitable as a physical profile"):
        st.caption("Out-of-range saturation values are retained for audit but are not plotted as saturation evolution.")
        st.dataframe(
            data["recovery_curve"][["PV Injected", "Oil Saturation (%)", "Water Saturation (%)", "Gas Saturation (%)"]],
            use_container_width=True, hide_index=True,
        )
    with st.expander("Material balance and source details"):
        st.dataframe(data["material_balance"], use_container_width=True, hide_index=True)
        st.write({
            "Workbook": data["metadata"]["workbook_name"],
            "Source report": data["metadata"]["source_report"],
            "Worksheets": data["metadata"]["sheets"],
            "Gas composition total (excluding Total row)": data["metadata"]["gas_composition_total_mol_pct"],
        })


def _render_wag() -> None:
    st.markdown("### Baronia · Water Alternating Gas (IWAG)")
    st.caption("Baronia workbook supplied: WAG_Copy.xlsx · Original workbook reference: Baronia_WAG_Data_EOR_ATLAS 1.xlsx")
    try:
        data = load_baronia_wag()
    except FileNotFoundError:
        st.info("The unlocked workbook is not stored in this public repository. Upload your working copy below, or place it at data/WAG_Copy.xlsx locally.")
        uploaded = st.file_uploader(
            "Upload the unlocked Baronia WAG workbook",
            type=["xlsx"],
            key="rd_baronia_wag_upload",
            help="The workbook is read for this session and is not committed to GitHub.",
        )
        if uploaded is None:
            return
        try:
            data = load_baronia_wag(workbook_bytes=uploaded.getvalue(), workbook_name=uploaded.name)
        except Exception as exc:
            st.error("The uploaded Baronia workbook could not be parsed.")
            with st.expander("Technical detail"):
                st.exception(exc)
            return
    except Exception as exc:
        st.error("Baronia WAG evidence could not be loaded.")
        with st.expander("Technical detail"):
            st.exception(exc)
        return

    field_name = _wag_lookup(data["summary_field"], "Field Name", key_col="Item", value_col="Value")
    target = _wag_lookup(data["summary_metrics"], "Target Reservoir", key_col="Metric", value_col="Value")
    stoiip = _wag_lookup(data["summary_metrics"], "STOIIP (RV2)", key_col="Metric", value_col="Value")
    wf = _wag_lookup(data["recovery_summary"], "Waterflood Recovery", key_col="Recovery Stage", value_col="Value")
    final = _wag_lookup(data["recovery_summary"], "IWAG Recovery (Total)", key_col="Recovery Stage", value_col="Value")
    increment = _wag_lookup(data["recovery_summary"], "IWAG Incremental Recovery", key_col="Recovery Stage", value_col="Value")

    st.caption(f"{field_name or 'Baronia'} · {target or 'RV2'} reservoir · Source: {data['metadata']['source_report']}")
    kpis = st.columns(5)
    kpis[0].metric("STOIIP", _wag_display(stoiip))
    kpis[1].metric("Waterflood recovery", _wag_display(wf, "% OOIP"))
    kpis[2].metric("WF + IWAG recovery", _wag_display(final, "% OOIP"))
    kpis[3].metric("IWAG increment · summary", _wag_display(increment, "pp"))
    kpis[4].metric("Core samples", str(data["metadata"]["core_samples"]))

    if not data["quality_issues"].empty:
        st.caption(f"Source QA: {data['metadata']['quality_issue_count']} issues. Review the Data Quality tab before relying on recovery values.")

    performance, injection, field_core, quality = st.tabs(["IWAG Performance", "Injection & Model", "Field & Core", "Data Quality"])
    with performance:
        _render_wag_performance(data)
    with injection:
        _render_wag_injection_model(data)
    with field_core:
        _render_wag_field_core(data)
    with quality:
        _render_wag_quality(data)




ALL_FIELDS_LABEL = "All fields"


def _ceor_field_options(field_names: list[str]) -> list[str]:
    """Build the selector from CEOR field-register entries and explicit lab tags."""
    normalized = {
        "St. Joseph" if value.casefold().replace(".", "").strip() == "st joseph" else value.strip()
        for value in field_names
        if value and value.strip()
    }
    return [ALL_FIELDS_LABEL, *sorted(normalized, key=str.casefold)]


def _field_rows(frame: pd.DataFrame, field: str) -> pd.DataFrame:
    if frame.empty or "Field" not in frame.columns:
        return frame.iloc[0:0].copy()
    values = frame["Field"].astype("string").str.strip()
    return frame.loc[values.str.casefold() == field.casefold()].copy()


def _render_thermal_field(df: pd.DataFrame, field: str) -> None:
    """Render thermal measurements only when the source row names the field."""
    work = _field_rows(df, field)
    st.markdown("#### Thermal polymer response")
    if work.empty:
        st.info(f"No field-tagged thermal polymer measurements are available for {field}.")
        return

    _metric_row([
        ("Tests", str(work["Test"].nunique()), "Distinct test identifiers in the Thermal sheet"),
        ("Polymer types", str(work["Polymer"].nunique()), "Polymer types tested for this field"),
        ("Temperature", f"{work['Temperature (°C)'].dropna().max():g} °C" if work["Temperature (°C)"].notna().any() else "Not reported", "Maximum recorded test temperature"),
        ("Concentrations", str(work["Polymer concentration (ppm)"].nunique()), "Distinct polymer concentrations recorded"),
    ])
    metric = "Viscosity (cP)" if work["Viscosity (cP)"].notna().any() else "Viscosity reduction (%)"
    fig = px.line(
        work.sort_values("Time (days)"),
        x="Time (days)",
        y=metric,
        color="Polymer",
        line_dash="Test",
        markers=True,
        hover_data=[
            "Year", "Field", "Analog", "Polymer concentration (ppm)",
            "Temperature (°C)", "Viscosity reduction (%)",
        ],
        labels={"Time (days)": "Exposure time (days)", metric: metric},
    )
    fig.update_layout(
        height=350,
        template="plotly_white",
        margin=dict(l=35, r=15, t=25, b=40),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    with st.expander("View thermal source records"):
        st.dataframe(work, use_container_width=True, hide_index=True)


def _render_thermal_all_fields(df: pd.DataFrame) -> None:
    """Show field-tagged thermal tests together while retaining field identity."""
    work = df.dropna(subset=["Field"]).copy()
    if work.empty:
        return
    work["Field"] = work["Field"].astype(str).str.strip()
    st.markdown("### Thermal polymer response · all tagged fields")
    st.caption(
        "These records carry a Field value in the Thermal worksheet. Colour identifies "
        "the field; measurements are not averaged across fields."
    )
    metric = "Viscosity (cP)" if work["Viscosity (cP)"].notna().any() else "Viscosity reduction (%)"
    fig = px.line(
        work.sort_values("Time (days)"),
        x="Time (days)",
        y=metric,
        color="Field",
        line_dash="Polymer",
        markers=True,
        hover_data=[
            "Test", "Year", "Polymer", "Analog",
            "Polymer concentration (ppm)", "Temperature (°C)",
        ],
        labels={"Time (days)": "Exposure time (days)", metric: metric},
    )
    fig.update_layout(
        height=390,
        template="plotly_white",
        margin=dict(l=35, r=15, t=25, b=40),
        legend_title="Field / polymer",
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    st.caption(f"{len(work):,} thermal records across {work['Field'].nunique()} explicitly tagged fields.")
    with st.expander("View all field-tagged thermal records"):
        st.dataframe(work, use_container_width=True, hide_index=True)


def _render_field_register(data: dict, field: str) -> None:
    records = data.get("field_map", pd.DataFrame())
    if records.empty:
        return
    rows = records.loc[records["Field"].astype(str).str.casefold() == field.casefold()]
    if not rows.empty:
        with st.expander("Field register and study references"):
            st.dataframe(
                rows[["Field", "EOR type", "Year", "Study type"]].drop_duplicates(),
                use_container_width=True,
                hide_index=True,
            )


def _load_st_jos_supplement() -> dict | None:
    """Load St. Joseph evidence only when its field is selected."""
    try:
        return load_st_jos_ceor()
    except FileNotFoundError:
        uploaded = st.file_uploader(
            "Upload the St. Joseph supplemental CEOR workbook",
            type=["xlsx"],
            key="rd_st_jos_upload",
            help="Used only for St. Joseph. The primary CEOR workbook remains the repository dataset.",
        )
        if uploaded is None:
            st.info(
                "St. Joseph is present in the field register, but its supplemental workbook "
                "is not available in this checkout. Upload the St. Joseph workbook to show "
                "its additional field-specific measurements."
            )
            return None
        try:
            return load_st_jos_ceor(uploaded.getvalue())
        except Exception as exc:
            st.error("The St. Joseph supplemental workbook could not be loaded.")
            with st.expander("Technical detail"):
                st.exception(exc)
            return None
    except Exception as exc:
        st.error("The St. Joseph supplemental workbook could not be loaded.")
        with st.expander("Technical detail"):
            st.exception(exc)
        return None


def _render_ceor_all_fields(data: dict) -> None:
    """Render the primary workbook as the portfolio-wide CEOR evidence source."""
    fluid_fluid, fluid_rock = st.tabs(["Fluid–Fluid", "Fluid–Rock"])
    with fluid_fluid:
        st.markdown("### Primary CEOR experimental evidence")
        st.caption(
            "Source: EOR_Screening_Tool_2026.xlsx. The Vis_Shear, phase-behaviour and "
            "IFT worksheets do not carry a Field column, so they are shown as shared "
            "laboratory evidence and are not assigned to a field through the map sheet."
        )
        _render_primary_fluid_fluid(data)
        if not data.get("thermal", pd.DataFrame()).empty:
            st.divider()
            _render_thermal_all_fields(data["thermal"])

    with fluid_rock:
        st.markdown("### Field-tagged adsorption")
        st.caption(
            "The Adsorption worksheet carries its own Field values. Use its filters to "
            "compare only the source-tagged observations."
        )
        _render_primary_adsorption(data["adsorption"], data["metadata"])

        st.divider()
        st.markdown("### Core-flood and Sor evidence · field not specified")
        st.caption(
            "Coreflood and Sor_f identify core samples and years but do not contain a "
            "Field column. They are kept visible as shared laboratory evidence, not "
            "assigned to a field by matching years or sample names."
        )
        _render_primary_coreflood(data["Coreflood"], data["metadata"])
        _render_primary_sor(data["Sor_F"], data["metadata"])

    field_map = data.get("field_map", pd.DataFrame())
    if not field_map.empty:
        with st.expander("CEOR field register"):
            st.dataframe(
                field_map[["Field", "EOR type", "Year", "Study type"]]
                .drop_duplicates()
                .sort_values(["Field", "Year"], kind="stable"),
                use_container_width=True,
                hide_index=True,
            )


def _render_ceor_field(data: dict, field: str, st_jos_data: dict | None) -> None:
    field_map = data.get("field_map", pd.DataFrame())
    thermal = _field_rows(data.get("thermal", pd.DataFrame()), field)
    adsorption = _field_rows(data.get("adsorption", pd.DataFrame()), field)

    _render_field_register(data, field)
    fluid_fluid, fluid_rock = st.tabs(["Fluid–Fluid", "Fluid–Rock"])

    with fluid_fluid:
        if field.casefold() == "st. joseph" and st_jos_data is not None:
            st.markdown("### St. Joseph supplemental evidence")
            st.caption(
                "Source: St_Jos CEOR (Shared) (1).xlsx. This is supplementary "
                "St. Joseph evidence, not the master CEOR dataset."
            )
            _render_fluid_fluid(st_jos_data)
        if not thermal.empty:
            st.divider()
            _render_thermal_field(data["thermal"], field)
        elif field.casefold() != "st. joseph":
            st.info(
                f"No primary-workbook Thermal measurements are explicitly tagged to {field}."
            )

        st.divider()
        st.markdown("### Shared primary Fluid–Fluid evidence")
        st.caption(
            "The primary Vis_Shear, phase-behaviour and IFT rows do not specify a Field. "
            "They are shown as shared experimental evidence and must not be interpreted "
            "as measurements from the selected field."
        )
        _render_primary_fluid_fluid(data)

    with fluid_rock:
        if field.casefold() == "st. joseph" and st_jos_data is not None:
            st.markdown("### St. Joseph supplemental Fluid–Rock evidence")
            st.caption("Source: St_Jos CEOR (Shared) (1).xlsx.")
            _render_fluid_rock(st_jos_data)

        st.markdown("### Primary Adsorption evidence")
        if adsorption.empty:
            st.info(f"No Adsorption observations in the primary workbook are tagged to {field}.")
        else:
            _render_primary_adsorption(adsorption, data["metadata"])

        st.divider()
        st.markdown("### Shared primary Core-flood and Sor evidence")
        st.caption(
            "The primary Coreflood and Sor_f worksheets do not identify a Field. "
            "They are retained here as shared laboratory evidence, not attributed "
            "to the selected field."
        )
        _render_primary_coreflood(data["Coreflood"], data["metadata"])
        _render_primary_sor(data["Sor_F"], data["metadata"])


def _render_ceor() -> None:
    try:
        data = load_ceor_evidence()
    except Exception as exc:
        st.error("The primary CEOR workbook could not be loaded.")
        with st.expander("Technical detail"):
            st.exception(exc)
        return

    field_names = list(data["metadata"].get("fields") or [])
    fields = _ceor_field_options(field_names)
    selected_field = st.selectbox(
        "Field",
        fields,
        index=0,
        key="rd_ceor_field",
        help=(
            "The field list comes from CEOR entries in the workbook's map sheet plus "
            "explicit Field tags in Thermal and Adsorption. Field-unlabeled experiments "
            "remain shared evidence; the map is not used to infer their field."
        ),
    )

    st.caption(f"CEOR evidence · **{selected_field}**")
    if selected_field == ALL_FIELDS_LABEL:
        _render_ceor_all_fields(data)
        return

    st_jos_data = _load_st_jos_supplement() if selected_field.casefold() == "st. joseph" else None
    _render_ceor_field(data, selected_field, st_jos_data)


def render() -> None:
    st.markdown("## R&D Laboratory")
    st.caption(
        "Explore CEOR and Water Alternating Gas evidence by field and experimental interaction."
    )
    method = st.radio(
        "Laboratory method",
        options=["CEOR", "WAG"],
        index=0,
        horizontal=True,
        key="rd_method",
        label_visibility="collapsed",
        format_func=lambda value: (
            "CEOR · Chemical EOR" if value == "CEOR"
            else "WAG · Water Alternating Gas"
        ),
    )
    if method == "WAG":
        _render_wag()
        return
    _render_ceor()
