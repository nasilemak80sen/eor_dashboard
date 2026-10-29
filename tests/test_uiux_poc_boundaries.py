from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_poc_entrypoint_sets_safety_mode_before_importing_ui():
    source = (ROOT / "src" / "eor_atlas_poc.py").read_text(encoding="utf-8")
    assert source.index('os.environ["EOR_POC_MODE"] = "1"') < source.index("import eor_atlas as atlas")
    assert "def _render_poc_history()" in source
    assert "_render_poc_history()" in source
    assert "atlas._render_page(page, services)" in source


def test_screening_and_hybrid_pages_guard_all_run_writes_in_poc_mode():
    screening = (ROOT / "src" / "pages_ui" / "screening.py").read_text(encoding="utf-8")
    intelligence = (ROOT / "src" / "pages_ui" / "intelligence.py").read_text(encoding="utf-8")
    assert 'poc_mode = os.environ.get("EOR_POC_MODE") == "1"' in screening
    assert 'poc_mode = os.environ.get("EOR_POC_MODE") == "1"' in intelligence
    assert 'if poc_mode:' in screening
    assert 'if poc_mode:' in intelligence
    assert 'persist_engineering_run(inputs, formation, result)' in screening
    assert 'persist_hybrid_run(result)' in intelligence


def test_poc_history_does_not_call_the_engineering_history_repository():
    source = (ROOT / "src" / "eor_atlas_poc.py").read_text(encoding="utf-8")
    assert "from data.screening_history import" not in source
    assert "list_report_cards(" not in source
    assert "dataframe" not in source.lower() or "st.dataframe(" in source
    assert '"Status": "SYNTHETIC"' in source


def test_vue_poc_uses_synthetic_local_service_and_no_fastapi_client():
    app = (ROOT / "frontend" / "src" / "App.vue").read_text(encoding="utf-8")
    service = (ROOT / "frontend" / "src" / "demoService.ts").read_text(encoding="utf-8")
    assert 'from "./demoService"' in app
    assert "runDemoEvaluation(" in app
    assert "fetch(" not in app
    assert "synthetic-ui-fixture" in service
    assert not (ROOT / "frontend" / "src" / "api.ts").exists()
