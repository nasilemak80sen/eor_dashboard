from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_rheology_keeps_polymer_series_against_shear_rate():
    source = (ROOT / "src" / "pages_ui" / "rd.py").read_text(encoding="utf-8")
    assert 'x="Shear rate (1/sec)"' in source
    assert 'y="Apparent viscosity (cP)"' in source
    assert 'color="Polymer"' in source
    assert 'st.multiselect("Year"' in source
    assert 'st.multiselect("Polymer type"' in source


def test_phase_behaviour_keeps_three_historical_source_panels_separate():
    source = (ROOT / "src" / "pages_ui" / "rd.py").read_text(encoding="utf-8")
    assert '("PB_2003", "PB_2003 — Phase Behaviour")' in source
    assert '("PB_2013_A", "PB_2013_A — Phase Behaviour")' in source
    assert '("PB_2013_S", "PB_2013_B — Phase Behaviour")' in source
    assert 'barmode="stack"' in source
    assert '"No Precipitation (%)", "Precipitation (%)"' in source


def test_ift_retains_horizontal_low_to_high_range_chart():
    source = (ROOT / "src" / "pages_ui" / "rd.py").read_text(encoding="utf-8")
    assert 'x=work["Range"], base=low' in source
    assert 'y=work["Material"]' in source
    assert 'xaxis_title="IFT (dynes/cm)"' in source


def test_adsorption_retains_time_series_and_source_filters():
    source = (ROOT / "src" / "pages_ui" / "rd.py").read_text(encoding="utf-8")
    assert 'x="Days", y="Adsorption ratio", color="Surfactant"' in source
    assert 'st.multiselect("Field"' in source
    assert 'st.multiselect("Surfactant / formulation"' in source


def test_core_flood_and_sor_keep_original_stacked_and_grouped_comparisons():
    page = (ROOT / "src" / "pages_ui" / "rd.py").read_text(encoding="utf-8")
    loader = (ROOT / "src" / "data" / "rd_lab_evidence.py").read_text(encoding="utf-8")
    assert 'barmode="stack"' in page
    assert 'color="Recovery component"' in page
    assert 'barmode="group"' in page
    assert '("Water Flood", "AS", "Polymer", "Alkaline", "Surfactant", "SP", "ASP")' in loader
