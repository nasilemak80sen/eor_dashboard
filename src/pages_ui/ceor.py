"""CEOR laboratory page."""

from __future__ import annotations

import streamlit as st

from ui.components import insight_cards, section_title


def render() -> None:
    import app_2 as _app

    mode = st.radio(
        "CEOR analysis area",
        ["Fluid / Fluid", "Fluid / Rock"],
        index=0,
        horizontal=True,
        key="ceor_lab_mode",
    )

    insight_cards([
        ("FLUID / FLUID", "Rheology & phase behaviour", "Review viscosity, retention, phase stability and IFT indicators."),
        ("FLUID / ROCK", "Rock interaction", "Review adsorption, core-flood increments and Sor reduction."),
        ("INTERPRET", "Technical evidence", "Use laboratory evidence as supporting context alongside the engineering gate."),
    ])
    st.markdown("<div class='atlas-divider'></div>", unsafe_allow_html=True)

    try:
        if mode == "Fluid / Rock":
            section_title("Fluid / Rock Analysis", "Rock–fluid interaction and core-flood evidence.")
            _app.render_fluid_rock_section()
        else:
            section_title("Fluid / Fluid Analysis", "Fluid compatibility, rheology and phase behaviour.")
            _app.render_fluid_fluid_section()
    except Exception as exc:
        st.error(f"CEOR analysis could not be rendered: {exc}")
