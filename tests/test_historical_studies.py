from pathlib import Path

import pandas as pd

from data.historical_studies import _prepare_frame, _status_is_success, merge_manual_studies


def test_prepare_frame_maps_expected_historical_columns(tmp_path: Path):
    frame = pd.DataFrame(
        {
            "Field": ["Guntong", "Dulang", "Tapis"],
            "Reservoir": ["J18/20", "1/2A-J1/4", "J-20/21"],
            "EOR Studies": ["ALSP", "CO2 WAG", "CO2M WAG"],
            "Incremental EUR (MMstb)": [190.0, 110.0, 70.0],
            "Status": ["PASS", "Success", "FAIL"],
        }
    )
    prepared, metadata = _prepare_frame(frame, tmp_path / "history.xlsx")
    assert len(prepared) == 2
    assert metadata["sheet_name"] == "Screening_Parameters"
    assert prepared.iloc[0]["Field"] == "Guntong"
    assert prepared.iloc[1]["EOR Study"] == "CO2 WAG"


def test_prepare_frame_maps_actual_y2k_method_columns(tmp_path: Path):
    frame = pd.DataFrame(
        {
            "Field": ["Guntong", "Dulang"],
            "Reservoir": ["J18/20", "1/2A-J1/4"],
            "MOST SUITABLE PROCESS": ["CO2M WAG", "ALSP"],
            "OTHERS PASS METHOD": ["CO2M NON WAG; CO2 WAG", "AS"],
            "INCREMENTAL EUR (MMSTB)": [190.0, 110.0],
        }
    )
    prepared, metadata = _prepare_frame(frame, tmp_path / "screening_parameters_Y2K Report.xlsx")
    assert len(prepared) == 2
    assert metadata["primary_method_column"] == "MOST SUITABLE PROCESS"
    assert metadata["alternative_method_column"] == "OTHERS PASS METHOD"
    assert prepared.iloc[0]["EOR Study"] == "CO2M WAG"
    assert prepared.iloc[0]["Other Passing Methods"] == "CO2M NON WAG; CO2 WAG"
    assert prepared["Incremental EUR (MMstb)"].sum() == 300.0


def test_status_success_is_conservative():
    assert _status_is_success("PASS") is True
    assert _status_is_success("Success") is True
    assert _status_is_success("FAIL") is False


def test_manual_rows_merge_without_duplicate_source_rows():
    base = pd.DataFrame(
        {
            "Field": ["Guntong"],
            "Reservoir": ["J18/20"],
            "EOR Study": ["ALSP"],
            "Other Passing Methods": [None],
            "Incremental EUR (MMstb)": [190.0],
            "Status": ["Historical study"],
        }
    )
    merged = merge_manual_studies(
        base,
        [
            {
                "Field": "Guntong",
                "Reservoir": "J18/20",
                "EOR Study": "ALSP",
                "Incremental EUR (MMstb)": 190.0,
                "Status": "User added",
            },
            {
                "Field": "Tapis",
                "Reservoir": "J-20/21",
                "EOR Study": "CO2 WAG",
                "Incremental EUR (MMstb)": 70.0,
                "Status": "User added",
            },
        ],
    )
    assert len(merged) == 2
