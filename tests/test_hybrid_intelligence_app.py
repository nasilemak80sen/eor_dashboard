from __future__ import annotations

import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def test_hybrid_intelligence_page_submits_controlled_inputs_end_to_end(monkeypatch):
    # Replace persistence only; the real Excel Gate, model inference, and
    # Decision Fusion paths still execute using the checked-in test artifacts.
    from pages_ui import intelligence as intelligence_page

    def fake_persist(result, *, user=None):
        return {"id": 1, "reference": "TEST-EOR-000001", "mode": "HYBRID"}

    monkeypatch.setattr(intelligence_page, "persist_hybrid_run", fake_persist)

    app = AppTest.from_file(str(SRC / "eor_atlas.py"), default_timeout=120)
    app.session_state["atlas_page"] = "intelligence"
    app.run()

    assert len(app.exception) == 0, [item.message for item in app.exception]
    submit = next(
        (
            button
            for button in app.button
            if "Run Hybrid Intelligence" in (button.label or "")
        ),
        None,
    )
    assert submit is not None, "Hybrid Intelligence submit button did not render."

    submit.click().run()

    assert len(app.exception) == 0, [item.message for item in app.exception]
    result = app.session_state["eor_intelligence_result"]
    assert result["ml_available"] is True, result.get("ml_error")
    assert result["ml_probabilities"]
    assert len(result["ml_probabilities"]) == 9
    assert "screening" in result
    assert "hybrid" in result
    hybrid = result["hybrid"]
    ranking = hybrid["ranking"]
    recommendation = hybrid["recommendation"]
    if recommendation is None:
        assert ranking == []
    else:
        assert ranking
        assert ranking[0]["EOR Technique"] == recommendation["EOR Technique"]
    assert all(
        str(row.get("Engineering Status", "")).strip().upper()
        not in {"FAIL", "FAIL (CRITICAL)"}
        for row in ranking
    )
    assert app.session_state["intelligence_last_run"]["reference"] == "TEST-EOR-000001"
