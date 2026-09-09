from __future__ import annotations

import pandas as pd

from src.candidate_analytics.analysis import CandidateAnalysis


def sample_dataframe() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Field": ["Angsi", "Angsi", "Tapis"],
            "Reservoir": ["A1", "A2", "T1"],
            "Field & Reservoir ": ["Angsi — A1", "Angsi — A2", "Tapis — T1"],
            "Injected Fluid": ["WAT", "GAS", "WAT"],
            "Reservoir Producing Status": ["PRODUCING", "NONPRODUCING", "PRODUCING"],
            "Oil API": [32.0, 28.0, 35.0],
            "Avg Porosity": [0.22, 0.18, 0.25],
            "Avg Permeability (mD)": [100.0, 250.0, 150.0],
            "Temp (deg C)": [85.0, 95.0, 80.0],
            "Oil Column (ft)": [120.0, 150.0, 100.0],
            "Oil Viscosity (cP)": [2.0, 4.0, 1.5],
            "STOIIP_ARPR 1.1.2025": [100.0, 200.0, 150.0],
            "EUR_ARPR 1.1.2026": [50.0, 80.0, 75.0],
            "RF Gap =Benchmark  RF - Field RF (%) ": [10.0, 15.0, 8.0],
            "CR volume potential = RF Gap x STOIIP  (MMSTB)": [10.0, 30.0, 12.0],
            "LATITUDE": [4.0, 4.0, 3.8],
            "LONGITUDE": [103.0, 103.1, 103.2],
        }
    )


def test_filter_combines_categorical_and_numeric_filters() -> None:
    analysis = CandidateAnalysis(sample_dataframe())
    result = analysis.filter(
        injected_fluids=["WAT"],
        statuses=["PRODUCING"],
        oil_api=(30.0, 40.0),
        permeability=(90.0, 160.0),
    )

    assert len(result) == 2
    assert set(result["Field"]) == {"Angsi", "Tapis"}


def test_scatter_preparation_drops_missing_axis_values() -> None:
    df = sample_dataframe()
    df.loc[1, "Temp (deg C)"] = None
    analysis = CandidateAnalysis(df)

    scatter = analysis.prepare_scatter(
        df,
        "Temp (deg C)",
        "CR volume potential = RF Gap x STOIIP  (MMSTB)",
        "Field",
    )

    assert len(scatter) == 2
    assert "__x" in scatter.columns
    assert "__y" in scatter.columns
    assert "__group" in scatter.columns


def test_opportunity_summary_is_descriptive_not_a_suitability_score() -> None:
    analysis = CandidateAnalysis(sample_dataframe())
    summary = analysis.opportunity_summary(analysis.df)

    assert summary["reservoirs"] == 3
    assert summary["fields"] == 2
    assert summary["STOIIP_total"] == 450.0
    assert summary["CR potential_total"] == 52.0
