import pandas as pd

from ui.portfolio_globe import build_portfolio_globe, portfolio_globe_config


def test_portfolio_globe_builds_orthographic_scene():
    frame = pd.DataFrame(
        {
            "Field": ["Angsi", "Tapis", "Bekok"],
            "Latitude": [4.31, 5.65, 1.83],
            "Longitude": [103.12, 104.22, 103.95],
            "Methods": [3, 2, 1],
            "EOR Methods": [
                "CO2, WAG, Steam",
                "WAG, Polymer",
                "CO2",
            ],
        }
    )

    fig = build_portfolio_globe(
        frame,
        latitude="Latitude",
        longitude="Longitude",
        name="Field",
        value="Methods",
    )

    assert fig.data
    assert fig.data[0].type == "scattergeo"
    assert fig.layout.geo.projection.type == "orthographic"
    assert fig.layout.geo.projection.rotation.lon == 102.0
    assert fig.layout.geo.projection.rotation.lat == 4.2
    assert fig.layout.height == 620


def test_portfolio_globe_preserves_field_hover_payload():
    frame = pd.DataFrame(
        {
            "Field": ["Angsi"],
            "Latitude": [4.31],
            "Longitude": [103.12],
            "Methods": [3],
            "EOR Methods": ["CO2, WAG, Steam"],
        }
    )

    fig = build_portfolio_globe(frame)
    trace = fig.data[0]

    assert trace.customdata[0][0] == "Angsi"
    assert trace.customdata[0][1] == 3
    assert trace.customdata[0][2] == "CO2, WAG, Steam"
    assert "Angsi" in (trace.hovertemplate or "")


def test_portfolio_globe_config_is_lightweight():
    config = portfolio_globe_config()

    assert config["displaylogo"] is False
    assert config["responsive"] is True
    assert config["scrollZoom"] is False
    assert "lasso2d" in config["modeBarButtonsToRemove"]
