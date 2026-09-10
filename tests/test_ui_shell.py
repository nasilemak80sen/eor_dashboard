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
