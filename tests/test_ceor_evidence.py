from pathlib import Path

import pandas as pd

from data.ceor_evidence import (
    _derive_sor_from_coreflood,
    _normalise_adsorption,
    _normalise_coreflood,
    _normalise_phase,
    _normalise_sor_sheet,
    _normalise_vis_shear,
    _resolve_sheet,
)


def test_resolve_sheet_supports_repository_aliases():
    sheets = ["Vis_Shear", "PB_2003", "PB_2013_A", "PB_2013_S", "IFT_sur_F", "IFT_poly_F", "Adsorption", "Coreflood", "Sor_F"]
    assert _resolve_sheet(sheets, "PB_2013_B") == "PB_2013_S"
    assert _resolve_sheet(sheets, "IFT_sur_T") == "IFT_poly_F"
    assert _resolve_sheet(sheets, "adsorption") == "Adsorption"
    assert _resolve_sheet(sheets, "Sor_F") == "Sor_F"


def test_vis_shear_normalisation():
    raw = pd.DataFrame(
        {"Year ": [2013], "Polymer ": ["P1"], "Shear Rate  (1/sec)": [10], "Apparent Viscosity": [42.0]}
    )
    out = _normalise_vis_shear(raw)
    assert list(out.columns) == ["Year", "Polymer", "Shear Rate", "Apparent Viscosity"]
    assert out.iloc[0]["Apparent Viscosity"] == 42.0


def test_phase_and_adsorption_normalisation():
    phase = _normalise_phase(
        pd.DataFrame(
            {"Year ": [2003], "Formulation (A/S/P)": ["F1"], "Percipitation ": [0.25], "No Percepitation ": [0.75]}
        )
    )
    assert phase.iloc[0]["Precipitation"] == 0.25
    adsorption = _normalise_adsorption(
        pd.DataFrame(
            {
                "Year ": [2003],
                "Field ": ["Angsi"],
                "Surfactant ": ["S1"],
                "Days ": [5],
                "Adsorption c/cO": [0.6],
                "Temperature": [80],
                "Polymer Type": ["P1"],
            }
        )
    )
    assert adsorption.iloc[0]["Adsorption c/cO"] == 0.6
    assert adsorption.iloc[0]["Temperature"] == 80
    assert adsorption.iloc[0]["Polymer Type"] == "P1"


def test_sor_sheet_accepts_long_layout():
    sor = _normalise_sor_sheet(
        pd.DataFrame(
            {
                "Core sample": ["C1", "C2"],
                "Year": [2013, 2013],
                "Method": ["AS", "ASP"],
                "Sor Reduction (%)": [20, 42],
            }
        )
    )
    assert list(sor["Method"]) == ["AS", "ASP"]
    assert list(sor["Sor Reduction (%)"]) == [20, 42]


def test_sor_sheet_accepts_wide_layout():
    sor = _normalise_sor_sheet(
        pd.DataFrame(
            {
                "Core sample": ["C1"],
                "Year": [2013],
                "% Sor Reduction (AS)": [20],
                "% Sor Reduction (ASP)": [42],
            }
        )
    )
    assert set(sor["Method"]) == {"% Sor Reduction (AS)", "% Sor Reduction (ASP)"}


def test_sor_is_derived_from_coreflood_when_sor_sheet_is_unavailable():
    coreflood = _normalise_coreflood(
        pd.DataFrame(
            {
                "Core sample": ["C1"],
                "Year": [2013],
                "% Sor Reduction (AS) = Sorw- Sorc / Sorw, %": [20],
                "% Sor Reduction (AS,P) = Sorw- Sorp / Sorw, %": [40],
                "% Sor Reduction (SP) = Sorw- Sorp / Sorw": [0],
            }
        )
    )
    sor = _derive_sor_from_coreflood(coreflood)
    assert set(sor["Method"]) == {"AS", "ASP", "SP"}
    assert float(sor.loc[sor["Method"] == "AS", "Sor Reduction (%)"].iloc[0]) == 20.0


def test_ceor_page_uses_repository_loader_not_legacy_app_renderer():
    source = (Path(__file__).resolve().parents[1] / "src" / "pages_ui" / "ceor.py").read_text(encoding="utf-8")
    assert "load_ceor_evidence" in source
    assert "_app.render_fluid_fluid_section()" not in source
    assert "_app.render_fluid_rock_section()" not in source
