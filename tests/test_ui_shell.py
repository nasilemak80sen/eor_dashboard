from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_hybrid_app_direct_entrypoint_delegates_to_eor_atlas():
    source = (ROOT / "src" / "hybrid_app.py").read_text(encoding="utf-8")
    assert "from eor_atlas import main as atlas_main" in source
    assert "_app.render_executive_overview_section()" not in source
    assert "tabs = st.tabs(" not in source


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


def test_application_services_are_cached_across_reruns():
    source = (ROOT / "src" / "eor_atlas.py").read_text(encoding="utf-8")
    assert "@st.cache_resource(show_spinner=False)" in source
    assert "def _safe_services()" in source
