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
    assert "new scene.SkyBox({" in html
    assert "skybox/px.webp" in html
    assert "skybox/nx.webp" in html
    assert "skybox/py.webp" in html
    assert "skybox/ny.webp" in html
    assert "skybox/pz.webp" in html
    assert "skybox/nz.webp" in html
    assert 'sun: {active: true}' in html
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
