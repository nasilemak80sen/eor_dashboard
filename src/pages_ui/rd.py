"""R&D laboratory page with CEOR field filtering and a separate WAG category."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from data.rd_lab_evidence import load_st_jos_ceor
from data.baronia_wag_evidence import load_baronia_wag
from data.ceor_evidence import load_ceor_evidence
from pages_ui.ceor import _render_compact_fluid_fluid, _render_compact_fluid_rock


def _metric_row(items: list[tuple[str, str, str]]) -> None:
    cols = st.columns(len(items))
    for col, (label, value, help_text) in zip(cols, items):
        with col:
            st.metric(label, value, help=help_text)


def _render_rheology(df: pd.DataFrame, meta: dict) -> None:
    """Render the original polymer-by-polymer viscosity/shear-rate comparison."""
    st.markdown("#### Rheology")
    st.caption("Apparent viscosity versus shear rate. Compare polymer behaviour across years and formulations.")
    if df.empty:
        st.info("No complete shear-rate/viscosity pairs are available.")
        return

    years = sorted(df["Year"].dropna().astype(int).unique().tolist())
    polymers = sorted(df["Polymer"].dropna().astype(str).unique().tolist(), key=str.casefold)
    left, right = st.columns([1, 2])
    with left:
        selected_years = st.multiselect("Year", years, default=years, key="rd_rheo_years")
    with right:
        selected_polymers = st.multiselect("Polymer type", polymers, default=polymers, key="rd_rheo_polymers")

    work = df.copy()
    if selected_years:
        work = work[work["Year"].isin(selected_years)]
    if selected_polymers:
        work = work[work["Polymer"].isin(selected_polymers)]
    if work.empty:
        st.info("No rheology records match the selected filters.")
        return

    fig = px.line(
        work.sort_values(["Polymer", "Shear rate (1/sec)"]),
        x="Shear rate (1/sec)",
        y="Apparent viscosity (cP)",
        color="Polymer",
        markers=True,
        hover_data=["Year"],
        labels={
            "Shear rate (1/sec)": "Shear Rate (1/sec)",
            "Apparent viscosity (cP)": "Apparent Viscosity",
        },
    )
    fig.update_layout(
        height=330, margin=dict(l=38, r=12, t=24, b=45),
        legend_title="Polymer", template="plotly_white",
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    st.caption(
        f"Source sheet: Vis_Shear · {len(work):,} plotted observations. "
        f"{meta['rheology_missing_shear_rate_rows']} rows without complete shear-rate/viscosity pairs are excluded."
    )


def _render_phase_chart(df: pd.DataFrame, title: str) -> None:
    """Keep each historical phase-behaviour source as its own stacked panel."""
    if df.empty:
        st.info(f"{title}: no usable records in the workbook.")
        return

    work = df.copy()
    work["Precipitation (%)"] = pd.to_numeric(work["Precipitation"], errors="coerce").fillna(0) * 100
    work["No Precipitation (%)"] = pd.to_numeric(work["No Precipitation"], errors="coerce").fillna(0) * 100
    long = work.melt(
        id_vars=["Formulation", "Test", "Remarks"],
        value_vars=["No Precipitation (%)", "Precipitation (%)"],
        var_name="Outcome",
        value_name="Percent",
    )
    fig = px.bar(
        long, x="Percent", y="Formulation", color="Outcome",
        orientation="h", barmode="stack",
        text=long["Percent"].map(lambda value: f"{value:.0f}%" if value >= 8 else ""),
        hover_data=["Test", "Remarks"],
        labels={"Percent": "Share of test condition (%)"},
        title=str(title),
    )
    fig.update_layout(
        height=max(230, min(430, 70 + 28 * len(work))),
        margin=dict(l=22, r=12, t=34, b=34),
        legend_title="Phase behaviour",
        xaxis_title="Share of test condition (%)",
        yaxis_title="Formulation",
        template="plotly_white",
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def _render_phase_tests(df: pd.DataFrame) -> None:
    st.markdown("#### Phase Behaviour Test")
    st.caption("Three source panels are kept separate so the historical formulations remain traceable.")
    if df.empty:
        st.info("No phase-behaviour screening tests were loaded.")
        return

    source_panels = [
        ("PB_2003", "PB_2003 — Phase Behaviour"),
        ("PB_2013_A", "PB_2013_A — Phase Behaviour"),
        ("PB_2013_S", "PB_2013_B — Phase Behaviour"),
    ]
    left, right = st.columns(2)
    for index, (source, title) in enumerate(source_panels):
        target = left if index in (0, 1) else right
        with target:
            _render_phase_chart(df[df["Source sheet"] == source].copy(), title)
            if source == "PB_2013_S":
                st.caption("PB_2013_B is represented by repository sheet PB_2013_S in this workbook revision.")

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
    """Restore the original horizontal IFT range chart (low-to-high)."""
    if df.empty:
        st.info(f"{title}: no usable records in the workbook.")
        return
    work = df.sort_values("IFT high (source)", ascending=False).copy()
    low = pd.to_numeric(work["IFT low (source)"], errors="coerce")
    high = pd.to_numeric(work["IFT high (source)"], errors="coerce")
    work["Range"] = (high - low).clip(lower=0)
    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=work["Material"], x=work["Range"], base=low,
        orientation="h",
        customdata=work[["IFT low raw", "IFT high raw", "Year"]].astype(str).to_numpy(),
        hovertemplate=(
            "%{y}<br>IFT low: %{customdata[0]} dynes/cm<br>"
            "IFT high: %{customdata[1]} dynes/cm<br>"
            "Year: %{customdata[2]}<extra></extra>"
        ),
    ))
    fig.update_layout(
        title=str(title), xaxis_title="IFT (dynes/cm)", yaxis_title="Material",
        height=max(230, min(430, 75 + 27 * len(work))),
        margin=dict(l=20, r=12, t=34, b=38),
        showlegend=False, template="plotly_white",
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
    st.markdown("#### Adsorption Test")
    st.caption("Explore adsorption behaviour by the dimensions actually present in the source workbook.")
    if df.empty:
        st.info("No St. Joseph adsorption records were found.")
        return

    years = sorted(df["Year"].dropna().astype(int).unique().tolist())
    fields = sorted(df["Field"].dropna().astype(str).unique().tolist(), key=str.casefold)
    materials = sorted(df["Surfactant"].dropna().astype(str).unique().tolist(), key=str.casefold)
    c1, c2, c3 = st.columns(3)
    with c1:
        selected_years = st.multiselect("Year", years, default=years, key="rd_ads_years")
    with c2:
        selected_fields = st.multiselect("Field", fields, default=fields, key="rd_ads_fields")
    with c3:
        selected_materials = st.multiselect("Surfactant / formulation", materials, default=materials, key="rd_ads_materials")

    work = df.copy()
    if selected_years:
        work = work[work["Year"].isin(selected_years)]
    if selected_fields:
        work = work[work["Field"].isin(selected_fields)]
    if selected_materials:
        work = work[work["Surfactant"].isin(selected_materials)]
    if work.empty:
        st.info("No adsorption records match the selected filters.")
        return

    fig = px.line(
        work.sort_values(["Surfactant", "Days"]),
        x="Days", y="Adsorption ratio", color="Surfactant",
        markers=True, hover_data=["Year", "Field", "Sample"],
        labels={"Days": "Days", "Adsorption ratio": "Adsorption c/c₀"},
    )
    fig.update_layout(
        height=330, margin=dict(l=38, r=12, t=24, b=45),
        legend_title="Surfactant / formulation", template="plotly_white",
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    st.caption("Source sheet: Adsorption (St_Jos)")
    with st.expander("View adsorption source records"):
        st.dataframe(work, use_container_width=True, hide_index=True)

def _render_coreflood(data: dict) -> None:
    st.markdown("#### Core Flood")
    st.caption("Compare waterflood recovery with chemical-EOR recovery contributions, then inspect the full source table.")
    water = data["waterflood"]
    if water.empty:
        st.info("No core-flood recovery records were found.")
        return

    components = ["Water Flood", "AS", "Polymer", "Alkaline", "Surfactant", "SP", "ASP"]
    available = [column for column in components if column in water.columns and pd.to_numeric(water[column], errors="coerce").notna().any()]
    if available:
        chart = water[["Core sample", "Year"] + available].copy()
        for column in available:
            chart[column] = pd.to_numeric(chart[column], errors="coerce").fillna(0)
        long = chart.melt(
            id_vars=["Core sample", "Year"], value_vars=available,
            var_name="Recovery component", value_name="Recovery (% OOIP)",
        )
        fig = px.bar(
            long, x="Core sample", y="Recovery (% OOIP)",
            color="Recovery component", barmode="stack", hover_data=["Year"],
        )
        fig.update_layout(
            height=340, margin=dict(l=28, r=12, t=24, b=62),
            xaxis_tickangle=-35, legend_title="Recovery component",
            template="plotly_white",
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    else:
        st.info("The imported core-flood sheet does not contain the original recovery-component columns.")

    with st.expander("View core-flood source records", expanded=False):
        st.dataframe(data["coreflood_summary"], use_container_width=True, hide_index=True)
        st.dataframe(water, use_container_width=True, hide_index=True)




def _render_sor(data: dict) -> None:
    st.markdown("#### Sor Reduction From a Core Flood")
    sor = data["sor_reduction"]
    if sor.empty:
        st.info("No Sor-reduction values were found.")
        return
    fig = px.bar(
        sor.sort_values(["Core sample", "Method"]),
        x="Core sample", y="Sor reduction (%)",
        color="Method", barmode="group", hover_data=["Year"],
        labels={"Sor reduction (%)": "Sor reduction (%)"},
    )
    fig.update_layout(
        height=330, margin=dict(l=35, r=12, t=24, b=62),
        xaxis_tickangle=-35, legend_title="Method", template="plotly_white",
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    st.caption("Sor source: Sor_f (StJoseph)")
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
OTHER_FIELD_LABEL = "Other · field mapping incomplete"


def _ceor_field_options(field_names: list[str], include_other: bool = False) -> list[str]:
    """Build a predictable field selector with an aggregate option first."""
    normalized = {
        "St. Joseph" if value.casefold().replace(".", "").strip() == "st joseph" else value.strip()
        for value in field_names
        if value and value.strip()
    }
    ordered = sorted(
        normalized,
        key=lambda value: (value.casefold() != "st. joseph", value.casefold()),
    )
    options = [ALL_FIELDS_LABEL, *ordered]
    if include_other:
        options.append(OTHER_FIELD_LABEL)
    return options


def _render_thermal_field(df: pd.DataFrame, field: str) -> None:
    """Render only thermal records explicitly tagged to the selected field."""
    work = df.loc[
        df["Field"].astype(str).str.strip().str.casefold() == field.casefold()
    ].copy()
    st.markdown("#### Thermal polymer response")
    if work.empty:
        st.info(f"No thermal polymer records are available for {field}.")
        return

    _metric_row([
        ("Tests", str(work["Test"].nunique()), "Distinct test identifiers in the Thermal sheet"),
        ("Polymer types", str(work["Polymer"].nunique()), "Polymer types tested for the selected field"),
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
        hover_data=["Year", "Analog", "Polymer concentration (ppm)", "Temperature (°C)", "Viscosity reduction (%)"],
        labels={"Time (days)": "Exposure time (days)", metric: metric},
    )
    fig.update_layout(height=350, template="plotly_white", margin=dict(l=35, r=15, t=25, b=40))
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
        "Field-tagged thermal tests are shown together for portfolio visibility. "
        "Colour identifies the source field; observations are not averaged across fields."
    )
    metric = "Viscosity (cP)" if work["Viscosity (cP)"].notna().any() else "Viscosity reduction (%)"
    fig = px.line(
        work.sort_values("Time (days)"),
        x="Time (days)",
        y=metric,
        color="Field",
        line_dash="Polymer",
        markers=True,
        hover_data=["Test", "Year", "Polymer", "Analog", "Polymer concentration (ppm)", "Temperature (°C)"],
        labels={"Time (days)": "Exposure time (days)", metric: metric},
    )
    fig.update_layout(height=390, template="plotly_white", margin=dict(l=35, r=15, t=25, b=40), legend_title="Field / polymer")
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    st.caption(f"{len(work):,} thermal records across {work['Field'].nunique()} explicitly named fields.")
    with st.expander("View all field-tagged thermal records"):
        st.dataframe(work, use_container_width=True, hide_index=True)


def _render_ceor_all_fields(
    field_data: dict,
    other_data: dict | None,
) -> None:
    """Aggregate the view, not the measurements: preserve source and field boundaries."""
    fluid_fluid, fluid_rock = st.tabs(["Fluid–Fluid", "Fluid–Rock"])

    with fluid_fluid:
        st.markdown("### St. Joseph")
        st.caption("Source: St_Jos CEOR (Shared) (1).xlsx")
        _render_fluid_fluid(field_data)

        thermal = field_data.get("thermal", pd.DataFrame())
        if not thermal.empty:
            st.divider()
            _render_thermal_all_fields(thermal)

        if other_data is not None:
            st.divider()
            st.markdown(f"### {OTHER_FIELD_LABEL}")
            st.caption("Source: EOR_Screening_Tool_2026.xlsx. Records are kept separate because field attribution is incomplete across its worksheets.")
            _render_compact_fluid_fluid(other_data)

    with fluid_rock:
        st.markdown("### St. Joseph")
        st.caption("Source: St_Jos CEOR (Shared) (1).xlsx")
        _render_fluid_rock(field_data)

        if other_data is not None:
            st.divider()
            st.markdown(f"### {OTHER_FIELD_LABEL}")
            st.caption("Source: EOR_Screening_Tool_2026.xlsx. These records are not attributed to St. Joseph.")
            _render_compact_fluid_rock(other_data)

        thermal_fields = sorted(
            field_data.get("thermal", pd.DataFrame()).get("Field", pd.Series(dtype="string"))
            .dropna().astype(str).str.strip().unique().tolist(),
            key=str.casefold,
        )
        if thermal_fields:
            st.divider()
            st.info(
                "No field-tagged fluid–rock adsorption, core-flood or Sor-reduction "
                "records are present for the other thermal fields: "
                + ", ".join(thermal_fields)
                + ". Those fields remain visible in Fluid–Fluid only until matching evidence is sourced."
            )


def _render_ceor() -> None:
    try:
        field_data = load_st_jos_ceor()
    except Exception as exc:
        st.error("CEOR field evidence could not be loaded.")
        with st.expander("Technical detail"):
            st.exception(exc)
        return

    try:
        other_data = load_ceor_evidence()
    except Exception:
        other_data = None

    other_available = other_data is not None
    fields = _ceor_field_options(
        list(field_data["metadata"].get("fields") or ["St. Joseph"]),
        include_other=other_available,
    )
    selected_field = st.selectbox(
        "Field",
        fields,
        index=0,
        key="rd_ceor_field",
        help="Choose All fields for an overall view. Field-specific evidence remains grouped by source field; Other contains records whose field mapping is incomplete.",
    )
    st.caption(f"CEOR evidence · **{selected_field}**")

    if selected_field == ALL_FIELDS_LABEL:
        _render_ceor_all_fields(field_data, other_data)
        return

    fluid_fluid, fluid_rock = st.tabs(["Fluid–Fluid", "Fluid–Rock"])
    if selected_field.casefold() == "st. joseph":
        with fluid_fluid:
            _render_fluid_fluid(field_data)
        with fluid_rock:
            _render_fluid_rock(field_data)
        with st.expander("Field data and source notes"):
            st.write({
                "Selected field": selected_field,
                "Source workbook": field_data["metadata"]["workbook_name"],
                "Rheology observations plotted": field_data["metadata"]["rheology_plot_rows"],
                "Phase points": field_data["metadata"]["phase_point_rows"],
                "Adsorption tests": field_data["metadata"]["adsorption_rows"],
                "Coreflood samples": field_data["metadata"]["coreflood_samples"],
            })
    elif selected_field == OTHER_FIELD_LABEL and other_data is not None:
        with fluid_fluid:
            _render_compact_fluid_fluid(other_data)
        with fluid_rock:
            _render_compact_fluid_rock(other_data)
        st.caption(
            "These records remain in the CEOR workspace, but the source workbook "
            "does not provide consistent field attribution across all worksheets."
        )
    else:
        with fluid_fluid:
            _render_thermal_field(field_data["thermal"], selected_field)
            st.caption(
                "Only records explicitly tagged to this field are shown. "
                "No St. Joseph measurements are carried across to another field."
            )
        with fluid_rock:
            st.info(
                f"No fluid–rock adsorption, core-flood or Sor-reduction records "
                f"are currently mapped to {selected_field}."
            )



def render() -> None:
    st.markdown("## R&D Laboratory")
    st.caption(
        "Explore CEOR and Water Alternating Gas evidence by field and experimental interaction."
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
        _render_wag()
        return
    _render_ceor()

