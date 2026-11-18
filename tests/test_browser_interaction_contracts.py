"""Regression contracts for browser-level EOR Atlas interaction checks."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_openglobus_browser_bridge_uses_the_production_renderer_click_event():
    source = (ROOT / "src" / "ui" / "openglobus.py").read_text(encoding="utf-8")

    assert 'globe.renderer.events.on("lclick",event=>' in source
    assert "window.__eorAtlasMapTest = Object.freeze({" in source
    assert 'events.dispatch(events.lclick,{pickingObject:entity});' in source
    assert "return selectedRecord === entity.properties;" in source


def test_browser_validation_checks_distinct_marker_details_and_chart_interactions():
    source = (ROOT / "scripts" / "validate_eor_atlas_browser.py").read_text(encoding="utf-8")

    assert "def _verify_candidate_marker_picking(" in source
    assert "def _verify_candidate_scatter_interactions(" in source
    assert "window.__eorAtlasMapTest.markerInfo(index)" in source
    assert "window.__eorAtlasMapTest.pickMarker(index)" in source
    assert 'locator("#detailLatLon")' in source
    assert 'locator(".vg-tooltip")' in source
    assert 'locator(".role-legend-entry")' in source
