import pandas as pd

from ui.openglobus import _build_openglobus_html, _normalise_records


def test_openglobus_normalises_map_records():
    frame = pd.DataFrame(
        {
            "Latitude": [4.3, "bad"],
            "Longitude": [103.1, 103.2],
            "Field": ["Angsi", "Invalid"],
            "Value": [5, 2],
            "Status": ["Candidate", "Historical"],
        }
    )

    records = _normalise_records(
        frame,
        latitude="Latitude",
        longitude="Longitude",
        name="Field",
        value="Value",
        value_label="RF Gap",
        detail_columns=[("Status", "Status")],
    )

    assert len(records) == 1
    assert records[0]["name"] == "Angsi"
    assert records[0]["value"] == 5.0
    assert records[0]["details"]["Status"] == "Candidate"


def test_openglobus_html_uses_requested_earth_configuration():
    html = _build_openglobus_html(
        [
            {
                "name": "Angsi",
                "latitude": 4.3,
                "longitude": 103.1,
                "value": 120,
                "value_label": "RF Gap",
                "details": {"Status": "Candidate"},
            }
        ],
        title="Field Opportunity",
        subtitle="OpenGlobus",
    )

    assert "new Globe({" in html
    assert "new GlobusRgbTerrain()" in html
    assert "layers: [new Bing()]" in html
    assert 'scene.SkyBox.createDefault(resourceRoot + "/")' in html
    assert "autoActivate: false" in html
    assert "globe.renderer.initialize();" in html
    assert "handler.isInitialized()" in html
    assert "globe.start();" in html
    assert "startupStage = \"rendering map entities\"" in html
    assert "const markerMaxValue = records.reduce" in html
    assert "Math.max(...magnitudes" not in html
    assert "const OPEN_GLOBUS_IMPORT_TIMEOUT_MS = 8000;" in html
    assert "importWithTimeout(candidate.js)" in html
    assert 'window.addEventListener("error", event =>' in html
    assert 'window.addEventListener("unhandledrejection", event =>' in html
    assert 'renderer.events.on("postdraw", markRendererReady)' in html
    assert "async: false" in html
    assert "assetCandidates" in html
    assert "esm.sh/@openglobus/og@0.28.7" in html
    assert "cdn.jsdelivr.net/npm/@openglobus/og@0.28.7/lib/og.es.js" in html
    assert html.index("cdn.jsdelivr.net/npm/@openglobus/og@0.28.7/lib/og.es.js") < html.index("unpkg.com/@openglobus/og@0.28.7/lib/og.es.js")
    assert "unpkg.com/@openglobus/og@0.28.7" in html
    assert "sandbox.openglobus.org/external/og/lib/og.es.js" not in html
    assert "All OpenGlobus asset hosts failed." in html
    assert 'stylesheet.rel = "stylesheet"' in html
    assert '<link rel="stylesheet" href="https://sandbox.openglobus.org' not in html
    assert 'sun: {active: true}' in html
    assert 'navigation: {mode: "lockNorth", inertia: .18, zoomSpeed: 1.15}' in html
    assert "resourcesSrc:" in html
    assert "fontsSrc:" in html


def test_openglobus_html_has_click_to_detail_behaviour():
    html = _build_openglobus_html(
        [
            {
                "name": "Angsi",
                "latitude": 4.3,
                "longitude": 103.1,
                "value": 1,
                "value_label": "Records",
                "details": {},
            }
        ],
        title="Challenge Landscape",
        subtitle="Details",
    )

    assert 'renderer.events.on("lclick"' in html
    assert "Fly to location" in html
    assert "renderDetails(picked.properties)" in html


def test_openglobus_dynamic_import_constructors_are_available_to_helpers():
    html = _build_openglobus_html(
        [
            {
                "name": "Angsi",
                "latitude": 4.3,
                "longitude": 103.1,
                "value": 1,
                "value_label": "Records",
                "details": {},
            }
        ],
        title="OpenGlobus",
        subtitle="Regression",
    )

    assert "let OGEntity = null;" in html
    assert "let OGLonLat = null;" in html
    assert "OGEntity = Entity;" in html
    assert "OGLonLat = LonLat;" in html
    assert "new OGEntity(entityOptions)" in html
    assert "if (showLabels || selected)" in html
    assert "new OGLonLat(record.longitude" in html
    assert "new OGLonLat(center.lon" in html
