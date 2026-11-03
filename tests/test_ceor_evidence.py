from pathlib import Path

import pandas as pd
import pytest

from data.ceor_evidence import (
    _derive_sor_from_coreflood,
    _normalise_adsorption,
    _normalise_coreflood,
    _normalise_phase,
    _normalise_field_map,
    _normalise_ift,
    _normalise_sor_sheet,
    _normalise_thermal,
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
    assert list(out.columns) == [
        "Year", "Polymer", "Salinity (mg/L TDS)", "Concentration (ppm)",
        "Shear Rate", "Apparent Viscosity",
    ]
    assert out.iloc[0]["Apparent Viscosity"] == 42.0
    assert pd.isna(out.iloc[0]["Salinity (mg/L TDS)"])



def test_ift_normalisation_preserves_reversed_source_bounds():
    raw = pd.DataFrame(
        {
            "Polymer": ["Polymer A"],
            "IFT low  dyne/cm": [0.3591],
            "IFT high  dyne/cm": [0.01],
            "Year ": [2013],
        }
    )
    out = _normalise_ift(raw, "Polymer")
    row = out.iloc[0]
    assert row["IFT Low"] == pytest.approx(0.3591)
    assert row["IFT High"] == pytest.approx(0.01)
    assert bool(row["IFT bounds reversed"]) is True
    assert row["IFT Low raw"] == "0.3591"
    assert row["IFT High raw"] == "0.01"


def test_field_map_contains_ceor_fields_only_and_canonicalises_st_joseph():
    raw = pd.DataFrame(
        {
            "Field ": ["Angsi", "Dulang", "Baram", "St Joseph"],
            "Types of EOR": ["CEOR ASP", "CEOR Alkaline", "WAG", "CEOR ASP"],
            "Year ": [2003, 2017, 2015, 2014],
            "Type of Study ": ["R&D", "R&D", "R&D", "R&D"],
        }
    )
    out = _normalise_field_map(raw)
    assert set(out["Field"]) == {"Angsi", "Dulang", "St. Joseph"}
    assert "Baram" not in set(out["Field"])


def test_thermal_normalisation_retains_explicit_field_tags():
    raw = pd.DataFrame(
        {
            "No ": [1, 2],
            "Year ": [2025, 2025],
            "Field ": ["Angsi", "Temana"],
            "Polymer Type": ["P1", "P2"],
            "Viscosity (cp)": [10.0, 12.0],
            "Viscosity reduction (%)": [25.0, 30.0],
            "Time (days)": [30, 60],
            "Polymer Concentration (ppm) ": [1000, 1500],
            "Temperature (degc)": [80, 90],
        }
    )
    out = _normalise_thermal(raw)
    assert set(out["Field"]) == {"Angsi", "Temana"}
    assert out.loc[out["Field"] == "Angsi", "Viscosity (cP)"].iloc[0] == 10.0


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



def test_primary_workbook_loads_the_repository_ceor_evidence_and_field_register():
    from data.ceor_evidence import load_ceor_evidence

    load_ceor_evidence.clear()
    data = load_ceor_evidence()
    metadata = data["metadata"]

    assert metadata["workbook_name"] == "EOR_Screening_Tool_2026.xlsx"
    assert metadata["source_map"]["field_map"] == "map"
    assert metadata["source_map"]["PB_2013_B"] == "PB_2013_S"
    assert len(data["Vis_Shear"]) == 64
    assert len(data["PB_2003"]) == 14
    assert len(data["PB_2013_A"]) == 4
    assert len(data["PB_2013_B"]) == 49
    assert len(data["IFT_sur_F"]) == 67
    assert len(data["IFT_sur_T"]) == 14
    assert metadata["ift_polymer_reversed_bounds"] == 14
    assert metadata["thermal_rows"] == 92
    assert set(metadata["thermal_fields"]) == {"Angsi", "D18", "Temana"}
    assert set(metadata["adsorption_fields"]) == {"Angsi"}
    assert set(metadata["fields"]) == {
        "Angsi", "Baronia", "Barton", "D18", "Dulang",
        "South Furious 30", "St. Joseph", "Temana",
    }


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


def test_r_and_d_page_uses_ceor_category_with_field_filter_and_two_method_views():
    source = (Path(__file__).resolve().parents[1] / "src" / "pages_ui" / "rd.py").read_text(encoding="utf-8")
    assert "St_Jos CEOR (Shared) (1).xlsx" in (Path(__file__).resolve().parents[1] / "src" / "data" / "rd_lab_evidence.py").read_text(encoding="utf-8")
    assert "Baronia_WAG_Data_EOR_ATLAS 1.xlsx" in source
    assert 'options=["CEOR", "WAG"]' in source
    assert 'st.tabs(["Fluid–Fluid", "Fluid–Rock"])' in source
    assert 'st.selectbox(\n        "Field"' in source
    assert "Legacy CEOR evidence" not in source
    assert "render_legacy_ceor" not in source


@pytest.mark.skipif(
    not (Path(__file__).resolve().parents[1] / "data" / "St_Jos CEOR (Shared) (1).xlsx").is_file(),
    reason="St. Joseph source workbook is supplied locally or through the R&D upload control",
)
def test_st_jos_loader_exposes_explicit_thermal_fields():
    from data.rd_lab_evidence import load_st_jos_ceor

    data = load_st_jos_ceor()
    assert data["metadata"]["thermal_rows"] == 92
    assert set(data["thermal"]["Field"].dropna().astype(str)) == {"Angsi", "D18", "Temana"}
    assert set(data["metadata"]["fields"]) == {"St. Joseph", "Angsi", "D18", "Temana"}


def test_ceor_page_has_compact_render_entrypoint():
    source = (Path(__file__).resolve().parents[1] / "src" / "pages_ui" / "ceor.py").read_text(encoding="utf-8")
    assert "def render_compact()" in source
    assert 'st.tabs(["Rheology", "Phase behaviour", "IFT"])' in source
    assert 'st.tabs(["Adsorption", "Core flood", "Sor reduction"])' in source


@pytest.mark.skipif(
    not (Path(__file__).resolve().parents[1] / "data" / "St_Jos CEOR (Shared) (1).xlsx").is_file(),
    reason="St. Joseph source workbook is supplied locally or through the R&D upload control",
)
def test_st_jos_ceor_workbook_loads_field_specific_laboratory_evidence():
    from data.rd_lab_evidence import load_st_jos_ceor

    data = load_st_jos_ceor()
    meta = data["metadata"]

    assert meta["rheology_plot_rows"] == 366
    assert meta["rheology_source_rows"] == 377
    assert meta["phase_point_rows"] == 290
    assert meta["phase_formulations"] == 26
    assert meta["phase_validated_rows"] == 262
    assert meta["phase_test_rows"] == 67
    assert meta["ift_rows"] == 21
    assert meta["adsorption_rows"] == 2
    assert meta["coreflood_samples"] == 16
    assert meta["sor_records"] == 16
    assert meta["ift_polymer_reversed_bounds"] == 14


@pytest.mark.skipif(
    not (Path(__file__).resolve().parents[1] / "data" / "St_Jos CEOR (Shared) (1).xlsx").is_file(),
    reason="St. Joseph source workbook is supplied locally or through the R&D upload control",
)
def test_st_jos_source_labels_are_preserved_when_ift_bounds_are_reversed():
    from data.rd_lab_evidence import load_st_jos_ceor

    data = load_st_jos_ceor()
    polymer_ift = data["ift_polymer"]

    assert (polymer_ift["IFT low (source)"] > polymer_ift["IFT high (source)"]).sum() == 14
    assert set(polymer_ift["IFT high raw"].dropna().astype(str)) == {"0.01"}
