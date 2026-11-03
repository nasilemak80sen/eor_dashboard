import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_hybrid_app_direct_entrypoint_delegates_to_eor_atlas():
    source = (ROOT / "src" / "hybrid_app.py").read_text(encoding="utf-8")
    assert "from eor_atlas import main as atlas_main" in source
    assert "_app.render_executive_overview_section()" not in source
    assert "tabs = st.tabs(" not in source


def test_eor_atlas_does_not_depend_on_private_hybrid_app_internals():
    source = (ROOT / "src" / "eor_atlas.py").read_text(encoding="utf-8")
    assert "engine._app" not in source
    assert 'logging.getLogger("eor_atlas")' in source
    assert "st.exception(exc)" in source


def test_new_ui_entrypoint_exists():
    assert (ROOT / "src" / "eor_atlas.py").exists()


def test_theme_has_high_contrast_controls_and_metric_tiles():
    source = (ROOT / "src" / "ui" / "theme.py").read_text(encoding="utf-8")
    assert "background:#fff;color:#182230" in source
    assert '[data-testid="stMetric"]' in source
    assert "--atlas-text:#111827" in source
    assert ".exec-kpi-card" in source


def test_decision_pages_use_submit_driven_forms():
    screening = (ROOT / "src" / "pages_ui" / "screening.py").read_text(encoding="utf-8")
    intelligence = (ROOT / "src" / "pages_ui" / "intelligence.py").read_text(encoding="utf-8")
    assert 'st.form("screening_reservoir_form"' in screening
    assert "st.form_submit_button(" in screening
    assert 'st.form("hybrid_reservoir_form"' in intelligence
    assert "st.form_submit_button(" in intelligence


def test_legacy_app_is_import_safe():
    source = (ROOT / "src" / "app_2.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    top_level_streamlit_calls = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom)):
            continue
        for child in ast.walk(node):
            if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute):
                if isinstance(child.func.value, ast.Name) and child.func.value.id == "st":
                    top_level_streamlit_calls.append(child.func.attr)

    assert "set_page_config" not in top_level_streamlit_calls
    assert "markdown" not in top_level_streamlit_calls
    assert "def configure_legacy_page()" in source
    assert "configure_legacy_page()" in source


def test_production_entrypoint_configures_streamlit_before_rendering():
    source = (ROOT / "src" / "eor_atlas.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    main = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "main")

    first_stmt = main.body[0]
    assert isinstance(first_stmt, ast.Expr)
    assert isinstance(first_stmt.value, ast.Call)
    assert isinstance(first_stmt.value.func, ast.Attribute)
    assert isinstance(first_stmt.value.func.value, ast.Name)
    assert first_stmt.value.func.value.id == "st"
    assert first_stmt.value.func.attr == "set_page_config"


def test_application_services_are_cached_across_reruns():
    source = (ROOT / "src" / "eor_atlas.py").read_text(encoding="utf-8")
    assert "@st.cache_resource(show_spinner=False)" in source
    assert "def _safe_services()" in source


def test_top_navigation_uses_buttons_not_radio():
    navigation = (ROOT / "src" / "ui" / "navigation.py").read_text(encoding="utf-8")
    shell = (ROOT / "src" / "ui" / "app_shell.py").read_text(encoding="utf-8")
    assert "st.button(" in navigation
    assert "st.radio(" not in navigation
    assert "render_top_nav()" in shell


def test_sidebar_starts_collapsed():
    settings = (ROOT / "src" / "config" / "settings.py").read_text(encoding="utf-8")
    assert '"initial_sidebar_state": "collapsed"' in settings


def test_r_and_d_navigation_routes_to_new_page():
    navigation = (ROOT / "src" / "ui" / "navigation.py").read_text(encoding="utf-8")
    app = (ROOT / "src" / "eor_atlas.py").read_text(encoding="utf-8")
    assert 'NavItem("ceor", "R&D", "🧪")' in navigation
    assert "from pages_ui import challenges, ceor, rd," in app
    assert '"ceor": rd.render' in app


def test_r_and_d_page_routes_ceor_by_field_without_a_legacy_expander():
    page = (ROOT / "src" / "pages_ui" / "rd.py").read_text(encoding="utf-8")
    assert 'options=["CEOR", "WAG"]' in page
    assert 'st.tabs(["Fluid–Fluid", "Fluid–Rock"])' in page
    assert 'st.selectbox(\n        "Field"' in page
    assert "_render_fluid_fluid(field_data)" in page
    assert "_render_fluid_rock(field_data)" in page
    assert "Legacy CEOR evidence" not in page
    assert "render_legacy_ceor" not in page
    assert "Other · field mapping incomplete" in page


def test_r_and_d_data_loader_preserves_source_ift_bounds():
    loader = (ROOT / "src" / "data" / "rd_lab_evidence.py").read_text(encoding="utf-8")
    assert '"IFT low (source)"' in loader
    assert '"IFT high (source)"' in loader
    assert "ift_polymer_reversed_bounds" in loader


def test_ceor_field_options_include_all_fields_without_duplicate_field_values():
    from pages_ui.rd import _ceor_field_options, ALL_FIELDS_LABEL, OTHER_FIELD_LABEL

    options = _ceor_field_options(
        ["Angsi", "D18", "St. Joseph", "Temana", "St Joseph"],
        include_other=True,
    )
    assert options == [
        ALL_FIELDS_LABEL,
        "St. Joseph",
        "Angsi",
        "D18",
        "Temana",
        OTHER_FIELD_LABEL,
    ]


def test_ceor_all_fields_view_keeps_each_field_and_source_separate():
    page = (ROOT / "src" / "pages_ui" / "rd.py").read_text(encoding="utf-8")
    assert 'if selected_field == ALL_FIELDS_LABEL:' in page
    assert "def _render_ceor_all_fields(" in page
    assert "_render_thermal_all_fields(thermal)" in page
    assert "Colour identifies the source field" in page
    assert "EOR_Screening_Tool_2026.xlsx. Records are kept separate" in page
