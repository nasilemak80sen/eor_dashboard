import pandas as pd

from ui.openglobus import _build_openglobus_html, _normalise_records


def _sample_html():
    return _build_openglobus_html(
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


def test_openglobus_matches_proven_competency_dashboard_bootstrap():
    html = _sample_html()

    assert '<script type="module">' in html
    assert "import {Globe, GlobusRgbTerrain, OpenStreetMap, control, Vector, Entity, LonLat}" in html
    assert "https://cdn.jsdelivr.net/npm/@openglobus/og@0.28.7/lib/og.es.js" in html
    assert "new OpenStreetMap(" in html
    assert "© OpenStreetMap contributors" in html
    assert "new GlobusRgbTerrain()" in html
    assert "resourcesSrc:" in html
    assert "fontsSrc:" in html
    assert 'msaa:4' in html
    assert 'idleMode:false' in html
    assert 'navigation:{mode:"north",inertia:.18,zoomSpeed:1.15}' in html

    # The old EOR implementation added cold-start work before OpenGlobus even
    # began: esm.sh bundling, dynamic import fallbacks, explicit renderer
    # initialization, skybox assets and Bing imagery.
    assert "esm.sh/@openglobus" not in html
    assert "OPEN_GLOBUS_IMPORT_TIMEOUT_MS" not in html
    assert "importWithTimeout" not in html
    assert "sandbox.openglobus.org" not in html
    assert "scene.SkyBox.createDefault" not in html
    assert "new Bing()" not in html
    assert "globe.renderer.initialize()" not in html
    assert "autoActivate:false" not in html


def test_openglobus_renders_markers_and_details():
    html = _sample_html()

    assert "const markerMaxValue = records.reduce" in html
    assert "Math.max(...magnitudes" not in html
    assert "new Entity(entityOptions)" in html
    assert "markerLayer.setEntities(entities)" in html
    assert 'renderer.events.on("lclick"' in html
    assert "renderDetails(picked.properties)" in html
    assert "Fly to location" in html
    assert "showLabels || selected" in html


def test_openglobus_vector_layer_uses_async_rendering_and_resize_kick():
    html = _sample_html()
    assert "async:true" in html
    assert "window.dispatchEvent(new Event(\"resize\")),250" in html


def test_openglobus_has_runtime_error_surface():
    html = _sample_html()
    assert 'status.innerHTML =' in html
    assert "3D Earth could not be initialized" in html
    assert "catch(error)" in html


def test_openglobus_uses_requested_camera_defaults():
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
        subtitle="Camera",
        center_lat=4.2,
        center_lon=102.0,
        camera_height=12000000,
    )

    assert "new LonLat(center.lon,center.lat,center.height)" in html
    assert "center.height/3" in html


def test_openglobus_html_does_not_ship_legacy_dynamic_loader_artifacts():
    html = _sample_html()
    for legacy in (
        "const assetCandidates",
        "__ASSET_CANDIDATES__",
        "OPEN_GLOBUS_CANDIDATES",
        "loadingOverlayHidden",
        "rendererReady",
        "startupStage",
    ):
        assert legacy not in html
