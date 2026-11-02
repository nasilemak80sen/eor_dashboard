"""Compact R&D laboratory workspace for CEOR and WAG evidence.

Workbook-specific loaders are intentionally separate. St. Joseph and Baronia
are shown as registered sources until their exact column/unit schemas have
been inspected; no engineering values are inferred from filenames.
"""
from __future__ import annotations

import streamlit as st

from pages_ui.ceor import render as render_legacy_ceor

CEOR_WORKBOOK = "data/St_Jos CEOR (Shared) (1).xlsx"
WAG_WORKBOOK = "data/Baronia_WAG_Data_EOR_ATLAS 1.xlsx"


def _source_status(path: str) -> tuple[bool, str]:
    from pathlib import Path
    candidate = Path(__file__).resolve().parents[2] / path
    return candidate.is_file(), str(candidate)


def _render_source_card(label: str, path: str, methodology: str) -> None:
    exists, resolved = _source_status(path)
    col_a, col_b = st.columns([3, 1])
    with col_a:
        st.markdown(f"**{label}**")
        st.caption(f"{methodology} · `{path}`")
    with col_b:
        st.markdown("**AVAILABLE**" if exists else "**MISSING**")
    with st.expander("Workbook details", expanded=False):
        st.code(resolved)
        st.caption(
            "The source workbook is registered. Charting is enabled only after "
            "its worksheet names, measurement columns, units and test identifiers "
            "have been mapped and validated."
        )


def _render_ceor() -> None:
    fluid_fluid, fluid_rock = st.tabs(["Fluid–Fluid", "Fluid–Rock"])
    # Existing, validated CEOR evidence remains available in its own workspace.
    # The St. Joseph workbook is registered separately until schema mapping.
    with fluid_fluid:
        st.subheader("Fluid–Fluid")
        st.caption("Rheology, phase behaviour and interfacial-tension evidence.")
        _render_source_card(
            "St. Joseph · CEOR source workbook",
            CEOR_WORKBOOK,
            "Chemical EOR · Fluid–Fluid and related laboratory evidence",
        )
    with fluid_rock:
        st.subheader("Fluid–Rock")
        st.caption("Adsorption, core-flood recovery and residual-oil-saturation response.")
        _render_source_card(
            "St. Joseph · CEOR source workbook",
            CEOR_WORKBOOK,
            "Chemical EOR · Fluid–Rock laboratory evidence",
        )
    with st.expander("Existing CEOR evidence workspace", expanded=False):
        st.caption(
            "The pre-existing CEOR workbook remains available here during the "
            "St. Joseph schema-integration step."
        )
        render_legacy_ceor()


def _render_wag() -> None:
    st.subheader("WAG · Water Alternating Gas")
    st.caption(
        "Baronia laboratory evidence. Water and gas injection observations must "
        "be interpreted against the source cycle identifiers and measurement units."
    )
    _render_source_card(
        "Baronia · WAG source workbook",
        WAG_WORKBOOK,
        "Water injection · Gas injection · Alternating-cycle analysis",
    )


def render() -> None:
    st.markdown("## R&D Laboratory")
    st.caption(
        "Laboratory methods and field-specific evidence for Chemical EOR and "
        "Water Alternating Gas."
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
    else:
        _render_ceor()
