from pathlib import Path


def test_hybrid_app_direct_entrypoint_delegates_to_eor_atlas():
    source = (Path(__file__).resolve().parents[1] / "src" / "hybrid_app.py").read_text(encoding="utf-8")
    assert "from eor_atlas import main as atlas_main" in source
    assert "_app.render_executive_overview_section()" not in source
    assert "tabs = st.tabs(" not in source


def test_new_ui_entrypoint_exists():
    path = Path(__file__).resolve().parents[1] / "src" / "eor_atlas.py"
    assert path.exists()
