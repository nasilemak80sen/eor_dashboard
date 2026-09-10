"""CEOR laboratory page."""

from __future__ import annotations

import streamlit as st

from ui.components import insight_cards, section_title


def render() -> None:
    import app_2 as _app

    insight_cards([
        ("FLUID / FLUID", "Rheology & phase behaviour", "Review viscosity, retention, phase stability and IFT indicators."),
        ("FLUID / ROCK", "Rock interaction", "Review adsorption, core-flood increments and Sor reduction."),
        ("INTERPRET", "Technical evidence", "Use laboratory evidence as supporting context alongside the engineering gate."),
    ])
    st.markdown("<div class='atlas-divider'></div>", unsafe_allow_html=True)

    fluid_fluid_tab, fluid_rock_tab = st.tabs(["Fluid / Fluid", "Fluid / Rock"])
    with fluid_fluid_tab:
        section_title("Fluid / Fluid Analysis", "Fluid compatibility, rheology and phase behaviour.")
        try:
            _app.render_fluid_fluid_section()
        except Exception as exc:
            st.error(f"CEOR Fluid / Fluid analysis could not be rendered: {exc}")
    with fluid_rock_tab:
        section_title("Fluid / Rock Analysis", "Rock–fluid interaction and core-flood evidence.")
        try:
            _app.render_fluid_rock_section()
        except Exception as exc:
            st.error(f"CEOR Fluid / Rock analysis could not be rendered: {exc}")
