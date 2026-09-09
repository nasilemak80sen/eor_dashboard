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
        self.df = self._ensure_unique_columns(dataframe.copy())

    @staticmethod
    def _ensure_unique_columns(dataframe: pd.DataFrame) -> pd.DataFrame:
        """Return a copy with deterministic, unique column labels.

        Duplicate Excel headers or duplicated selections can cause
        ``dataframe[column]`` to return a DataFrame rather than a Series.
        Candidate analytics always works with one logical column per label.
        """
        if not dataframe.columns.duplicated().any():
            return dataframe

        used: dict[str, int] = {}
        columns: list[str] = []
        for raw_column in dataframe.columns:
            column = str(raw_column)
            occurrence = used.get(column, 0)
            columns.append(
                column if occurrence == 0
                else f"{column}__duplicate_{occurrence}"
            )
            used[column] = occurrence + 1

        result = dataframe.copy()
        result.columns = columns
        return result

    @staticmethod
    def _first_series(dataframe: pd.DataFrame, column: str) -> pd.Series:
        """Safely return one Series even when a caller supplies duplicates."""
        value = dataframe.loc[:, column]
        if isinstance(value, pd.DataFrame):
            return value.iloc[:, 0]
        return value

    @property
    def row_count(self) -> int:
        return len(self.df)

    @property
    def field_count(self) -> int:
        if "Field" not in self.df.columns:
            return 0
        return int(self._first_series(self.df, "Field").nunique())

    @property
    def reservoir_count(self) -> int:
        return int(len(self.df))

    def categorical_options(self, column: str) -> list[str]:
        if column not in self.df.columns:
            return []
        values = self._first_series(self.df, column).dropna().astype(str).str.strip()
        values = values[values != ""]
        return sorted(values.unique().tolist(), key=str.casefold)

    def numeric_bounds(self, column: str) -> tuple[float, float] | None:
        if column not in self.df.columns:
            return None
        values = pd.to_numeric(
            self._first_series(self.df, column),
            errors="coerce",
        ).dropna()
        if values.empty:
            return None
        return float(values.min()), float(values.max())

    @staticmethod
    def _apply_numeric_range(
        dataframe: pd.DataFrame,
        column: str,
        bounds: tuple[float, float] | None,
    ) -> pd.DataFrame:
        if bounds is None or column not in dataframe.columns:
            return dataframe

        values = dataframe.loc[:, column]
        if isinstance(values, pd.DataFrame):
            values = values.iloc[:, 0]
        numeric = pd.to_numeric(values, errors="coerce")
        low, high = bounds
        return dataframe.loc[numeric.between(low, high, inclusive="both")]

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
        result = self._ensure_unique_columns(self.df.copy())

        if injected_fluids:
            selected = {str(x).strip().casefold() for x in injected_fluids}
            series = self._first_series(result, "Injected Fluid")
            result = result.loc[
                series.fillna("").astype(str).str.strip().str.casefold().isin(selected)
            ]

        if statuses:
            selected = {str(x).strip().casefold() for x in statuses}
            series = self._first_series(result, "Reservoir Producing Status")
            result = result.loc[
                series.fillna("").astype(str).str.strip().str.casefold().isin(selected)
            ]

        result = self._apply_numeric_range(result, "Oil API", oil_api)
        result = self._apply_numeric_range(result, "Avg Porosity", porosity)
        result = self._apply_numeric_range(result, "Avg Permeability (mD)", permeability)
        result = self._apply_numeric_range(result, "Temp (deg C)", temperature_c)
        result = self._apply_numeric_range(result, "Oil Column (ft)", oil_column)
        result = self._apply_numeric_range(result, "Oil Viscosity (cP)", viscosity)

        return self._ensure_unique_columns(result.reset_index(drop=True))

    def axis_options(self) -> list[str]:
        """Return the Power BI-equivalent dynamic-axis fields."""
        return [
            column
            for column in AXIS_LABELS
            if column in self.df.columns
        ]

    def axis_label(self, column: str) -> str:
        return AXIS_LABELS.get(column, column)

    def is_numeric_axis(self, column: str) -> bool:
        if column not in self.df.columns:
            return False
        return pd.api.types.is_numeric_dtype(
            self._first_series(self.df, column)
        )

    def prepare_scatter(
        self,
        dataframe: pd.DataFrame,
        x_column: str,
        y_column: str,
        group_by: str,
    ) -> pd.DataFrame:
        """Prepare a clean scatter dataset without modifying source values."""
        dataframe = self._ensure_unique_columns(dataframe.copy())
        if x_column not in dataframe.columns or y_column not in dataframe.columns:
            return pd.DataFrame()

        group_column = GROUP_COLUMNS.get(group_by, "Field")

        # Build the plotting frame without ever selecting a duplicated list of
        # labels. X/Y/group fields may legitimately refer to one of the fixed
        # metadata fields (e.g. X=Field), so a plain dataframe[columns] is unsafe.
        scatter = pd.DataFrame(index=dataframe.index)
        for column in [
            "Field",
            "Reservoir",
            "Field & Reservoir ",
            group_column,
        ]:
            if column in dataframe.columns and column not in scatter.columns:
                scatter[column] = self._first_series(dataframe, column)

        scatter["__x"] = pd.to_numeric(
            self._first_series(dataframe, x_column),
            errors="coerce",
        )
        scatter["__y"] = pd.to_numeric(
            self._first_series(dataframe, y_column),
            errors="coerce",
        )

        for column in [
            "CR volume potential = RF Gap x STOIIP  (MMSTB)",
            "STOIIP_ARPR 1.1.2025",
            "RF Gap =Benchmark  RF - Field RF (%) ",
            "LATITUDE",
            "LONGITUDE",
        ]:
            if column in dataframe.columns and column not in scatter.columns:
                scatter[column] = self._first_series(dataframe, column)

        scatter = scatter.dropna(subset=["__x", "__y"])

        if group_column not in scatter.columns:
            scatter["__group"] = "Unknown"
        else:
            group_series = self._first_series(scatter, group_column)
            scatter["__group"] = (
                group_series.fillna("Unknown")
                .astype(str)
                .str.strip()
                .replace("", "Unknown")
            )

        if "CR volume potential = RF Gap x STOIIP  (MMSTB)" in scatter.columns:
            size_series = self._first_series(
                scatter,
                "CR volume potential = RF Gap x STOIIP  (MMSTB)",
            )
        else:
            size_series = pd.Series(1.0, index=scatter.index)

        scatter["__size"] = pd.to_numeric(
            size_series,
            errors="coerce",
        ).fillna(0.0)

        scatter["__marker_size"] = scatter["__size"].clip(lower=0.0)
        if not scatter.empty and float(scatter["__marker_size"].max()) == 0.0:
            scatter["__marker_size"] = 1.0

        return self._ensure_unique_columns(scatter.reset_index(drop=True))

    def opportunity_summary(self, dataframe: pd.DataFrame) -> dict[str, Any]:
        """Portfolio-level descriptive statistics; not an EOR suitability score."""
        dataframe = self._ensure_unique_columns(dataframe.copy())
        fields = (
            self._first_series(dataframe, "Field").nunique()
            if "Field" in dataframe.columns
            else 0
        )
        summary: dict[str, Any] = {
            "reservoirs": int(len(dataframe)),
            "fields": int(fields),
        }

        for label, column in {
            "STOIIP": "STOIIP_ARPR 1.1.2025",
            "CR potential": "CR volume potential = RF Gap x STOIIP  (MMSTB)",
            "RF gap": "RF Gap =Benchmark  RF - Field RF (%) ",
        }.items():
            if column in dataframe.columns:
                values = pd.to_numeric(
                    self._first_series(dataframe, column),
                    errors="coerce",
                )
                summary[f"{label}_total"] = (
                    float(values.sum(min_count=1))
                    if values.notna().any()
                    else np.nan
                )
                summary[f"{label}_median"] = (
                    float(values.median())
                    if values.notna().any()
                    else np.nan
                )

        return summary

    def table_view(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        """Return a user-facing candidate table with stable column order."""
        dataframe = self._ensure_unique_columns(dataframe.copy())
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
        return dataframe.loc[
            :, [c for c in desired if c in dataframe.columns]
        ].copy()

    @staticmethod
    def format_for_display(dataframe: pd.DataFrame) -> pd.DataFrame:
        """Format only the UI copy; the analytical DataFrame remains numeric."""
        result = dataframe.copy()
        for column in [
            "Avg Porosity",
            "Benchmark RF (%)",
            "RF Gap =Benchmark  RF - Field RF (%) ",
            "RF Gap =Benchmark  RF - Field RF (%) abs ",
            "RF_ARPR 1.1.2025 (calculated) ",
            "Initial Oil Saturation (Soi)",
        ]:
            if column in result.columns:
                result[column] = pd.to_numeric(
                    result[column], errors="coerce"
                ).round(2)

        for column in [
            "STOIIP_ARPR 1.1.2025",
            "EUR_ARPR 1.1.2026",
            "CR volume potential = RF Gap x STOIIP  (MMSTB)",
            "Avg Permeability (mD)",
            "Oil API",
            "Oil Viscosity (cP)",
            "Temp (deg C)",
            "Oil Column (ft)",
        ]:
            if column in result.columns:
                result[column] = pd.to_numeric(
                    result[column], errors="coerce"
                ).round(2)
        return result
