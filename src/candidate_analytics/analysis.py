from __future__ import annotations

from typing import Any, Iterable

import numpy as np
import pandas as pd

from .repository import AXIS_LABELS


GROUP_COLUMNS = {
    "Field": "Field",
    "Reservoir": "Reservoir",
    "Field & Reservoir": "Field & Reservoir ",
}

FILTER_COLUMNS = {
    "Injected Fluid": "Injected Fluid",
    "Reservoir Producing Status": "Reservoir Producing Status",
    "Oil API": "Oil API",
    "Avg Porosity": "Avg Porosity",
    "Avg Permeability (mD)": "Avg Permeability (mD)",
    "Temperature (°C)": "Temp (deg C)",
    "Oil Column (ft)": "Oil Column (ft)",
    "Oil Viscosity (cP)": "Oil Viscosity (cP)",
}


class CandidateAnalysis:
    """Pure analytical operations for the standalone candidate explorer."""

    def __init__(self, dataframe: pd.DataFrame) -> None:
        self.df = dataframe.copy()

    @property
    def row_count(self) -> int:
        return len(self.df)

    @property
    def field_count(self) -> int:
        return int(self.df["Field"].nunique()) if "Field" in self.df else 0

    @property
    def reservoir_count(self) -> int:
        return int(len(self.df))

    def categorical_options(self, column: str) -> list[str]:
        if column not in self.df.columns:
            return []
        values = self.df[column].dropna().astype(str).str.strip()
        values = values[values != ""]
        return sorted(values.unique().tolist(), key=str.casefold)

    def numeric_bounds(self, column: str) -> tuple[float, float] | None:
        if column not in self.df.columns:
            return None
        values = pd.to_numeric(self.df[column], errors="coerce").dropna()
        if values.empty:
            return None
        return float(values.min()), float(values.max())

    @staticmethod
    def _apply_numeric_range(
        df: pd.DataFrame,
        column: str,
        bounds: tuple[float, float] | None,
    ) -> pd.DataFrame:
        if bounds is None or column not in df.columns:
            return df
        low, high = bounds
        numeric = pd.to_numeric(df[column], errors="coerce")
        return df[numeric.between(low, high, inclusive="both")]

    def filter(
        self,
        *,
        injected_fluids: Iterable[str] | None = None,
        statuses: Iterable[str] | None = None,
        oil_api: tuple[float, float] | None = None,
        porosity: tuple[float, float] | None = None,
        permeability: tuple[float, float] | None = None,
        temperature_c: tuple[float, float] | None = None,
        oil_column: tuple[float, float] | None = None,
        viscosity: tuple[float, float] | None = None,
    ) -> pd.DataFrame:
        """Return records satisfying the selected candidate filters."""
        result = self.df.copy()

        if injected_fluids:
            selected = {str(x).strip().casefold() for x in injected_fluids}
            result = result[
                result["Injected Fluid"].fillna("").astype(str).str.strip().str.casefold().isin(selected)
            ]

        if statuses:
            selected = {str(x).strip().casefold() for x in statuses}
            result = result[
                result["Reservoir Producing Status"].fillna("").astype(str).str.strip().str.casefold().isin(selected)
            ]

        result = self._apply_numeric_range(result, "Oil API", oil_api)
        result = self._apply_numeric_range(result, "Avg Porosity", porosity)
        result = self._apply_numeric_range(result, "Avg Permeability (mD)", permeability)
        result = self._apply_numeric_range(result, "Temp (deg C)", temperature_c)
        result = self._apply_numeric_range(result, "Oil Column (ft)", oil_column)
        result = self._apply_numeric_range(result, "Oil Viscosity (cP)", viscosity)

        return result.reset_index(drop=True)

    def axis_options(self) -> list[str]:
        """Return the Power BI-equivalent dynamic-axis fields."""
        available = [column for column in AXIS_LABELS if column in self.df.columns]
        return available

    def axis_label(self, column: str) -> str:
        return AXIS_LABELS.get(column, column)

    def is_numeric_axis(self, column: str) -> bool:
        if column not in self.df.columns:
            return False
        return pd.api.types.is_numeric_dtype(self.df[column])

    def prepare_scatter(
        self,
        dataframe: pd.DataFrame,
        x_column: str,
        y_column: str,
        group_by: str,
    ) -> pd.DataFrame:
        """Prepare a clean scatter dataset without modifying source values."""
        if x_column not in dataframe.columns or y_column not in dataframe.columns:
            return pd.DataFrame()

        group_column = GROUP_COLUMNS.get(group_by, "Field")
        columns = [
            column
            for column in [
                "Field",
                "Reservoir",
                "Field & Reservoir ",
                group_column,
                x_column,
                y_column,
                "CR volume potential = RF Gap x STOIIP  (MMSTB)",
                "STOIIP_ARPR 1.1.2025",
                "RF Gap =Benchmark  RF - Field RF (%) ",
                "LATITUDE",
                "LONGITUDE",
            ]
            if column in dataframe.columns
        ]

        scatter = dataframe[columns].copy()
        scatter["__x"] = pd.to_numeric(scatter[x_column], errors="coerce")
        scatter["__y"] = pd.to_numeric(scatter[y_column], errors="coerce")
        scatter = scatter.dropna(subset=["__x", "__y"])

        if group_column not in scatter.columns:
            scatter[group_column] = "Unknown"

        scatter["__group"] = scatter[group_column].fillna("Unknown").astype(str)
        scatter["__size"] = pd.to_numeric(
            scatter.get(
                "CR volume potential = RF Gap x STOIIP  (MMSTB)",
                pd.Series(1.0, index=scatter.index),
            ),
            errors="coerce",
        ).fillna(0.0)

        # Plotting libraries generally behave better with strictly positive
        # marker sizes. The source CR potential remains untouched.
        scatter["__marker_size"] = scatter["__size"].clip(lower=0.0)
        if not scatter.empty and float(scatter["__marker_size"].max()) == 0.0:
            scatter["__marker_size"] = 1.0

        return scatter.reset_index(drop=True)

    def opportunity_summary(self, dataframe: pd.DataFrame) -> dict[str, Any]:
        """Portfolio-level descriptive statistics; not an EOR suitability score."""
        summary: dict[str, Any] = {
            "reservoirs": int(len(dataframe)),
            "fields": int(dataframe["Field"].nunique()) if "Field" in dataframe else 0,
        }

        for label, column in {
            "STOIIP": "STOIIP_ARPR 1.1.2025",
            "CR potential": "CR volume potential = RF Gap x STOIIP  (MMSTB)",
            "RF gap": "RF Gap =Benchmark  RF - Field RF (%) ",
        }.items():
            if column in dataframe.columns:
                values = pd.to_numeric(dataframe[column], errors="coerce")
                summary[f"{label}_total"] = float(values.sum(min_count=1)) if values.notna().any() else np.nan
                summary[f"{label}_median"] = float(values.median()) if values.notna().any() else np.nan

        return summary

    def table_view(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        """Return a user-facing candidate table with stable column order."""
        desired = [
            "Field",
            "Reservoir",
            "Field & Reservoir ",
            "Temp (deg C)",
            "Reservoir Temperature (F)",
            "Injected Fluid",
            "Reservoir Producing Status",
            "Avg Permeability (mD)",
            "Avg Porosity",
            "Oil API",
            "Oil Viscosity (cP)",
            "STOIIP_ARPR 1.1.2025",
            "EUR_ARPR 1.1.2026",
            "RF_ARPR 1.1.2025 (calculated) ",
            "Benchmark RF (%)",
            "RF Gap =Benchmark  RF - Field RF (%) ",
            "CR volume potential = RF Gap x STOIIP  (MMSTB)",
            "Oil Column (ft)",
            "Gross Thickness (ft)",
            "Oil Producers",
            "Injectors",
            "# Idle Well (June 25) ",
            "LATITUDE",
            "LONGITUDE",
        ]
        return dataframe[[c for c in desired if c in dataframe.columns]].copy()

    @staticmethod
    def format_for_display(dataframe: pd.DataFrame) -> pd.DataFrame:
        """Format only the UI copy; the analytical DataFrame remains numeric."""
        result = dataframe.copy()
        percentage_columns = [
            "Avg Porosity",
            "Benchmark RF (%)",
            "RF Gap =Benchmark  RF - Field RF (%) ",
            "RF Gap =Benchmark  RF - Field RF (%) abs ",
            "RF_ARPR 1.1.2025 (calculated) ",
            "Initial Oil Saturation (Soi)",
        ]
        for column in percentage_columns:
            if column in result.columns:
                result[column] = pd.to_numeric(result[column], errors="coerce").round(2)

        numeric_columns = [
            "STOIIP_ARPR 1.1.2025",
            "EUR_ARPR 1.1.2026",
            "CR volume potential = RF Gap x STOIIP  (MMSTB)",
            "Avg Permeability (mD)",
            "Oil API",
            "Oil Viscosity (cP)",
            "Temp (deg C)",
            "Oil Column (ft)",
        ]
        for column in numeric_columns:
            if column in result.columns:
                result[column] = pd.to_numeric(result[column], errors="coerce").round(2)
        return result
