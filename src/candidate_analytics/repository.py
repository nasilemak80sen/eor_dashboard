from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from config.settings import settings


PRIMARY_SHEET = "PROP_updatedNov25_v2"
COORDINATE_SHEET = "v2"

KEY_COLUMNS = ["Field", "Reservoir", "Field & Reservoir "]

NUMERIC_COLUMNS = [
    "STOIIP_ARPR 1.1.2025",
    "Np_ARPR 1.1.2025",
    "UR_ARPR 1.1.2025",
    "EUR_ARPR 1.1.2026",
    "RF_ARPR 1.1.2025 (calculated) ",
    "RCI",
    "Benchmark RF (%)",
    "RF Gap =Benchmark  RF - Field RF (%) ",
    "RF Gap =Benchmark  RF - Field RF (%) abs ",
    "CR volume potential = RF Gap x STOIIP  (MMSTB)",
    "Non producing reservoirs ",
    "Reservoir Temperature (F)",
    "# Idle Well (June 25) ",
    "Temp (deg C)",
    "Oil API",
    "Gross Thickness (ft)",
    "Oil Column (ft)",
    "Avg Porosity",
    "Avg Permeability (mD)",
    "Oil Producers",
    "Injectors",
    "Gas cap m-ratio",
    "Initial Reservoir Pressure (psi)",
    "Bubble point (psi)",
    "Initial Oil Saturation (Soi)",
    "Oil FVF (Boi)",
    "Oil Viscosity (cP)",
    "Solution GOR (scf/bbl)",
    "LATITUDE",
    "LONGITUDE",
]

AXIS_LABELS = {
    "# Idle Well (June 25) ": "# Idle Well (June 25)",
    "Avg Permeability (mD)": "Avg Permeability (mD)",
    "Avg Porosity": "Avg Porosity",
    "Benchmark RF (%)": "Benchmark RF (%)",
    "Bubble point (psi)": "Bubble point (psi)",
    "CR volume potential = RF Gap x STOIIP  (MMSTB)": "CR volume potential = RF Gap × STOIIP (MMSTB)",
    "EUR_ARPR 1.1.2026": "EUR_ARPR 1.1.2026",
    "Field": "Field",
    "Field & Reservoir ": "Field & Reservoir",
    "Gas cap m-ratio": "Gas cap m-ratio",
    "Gross Thickness (ft)": "Gross Thickness (ft)",
    "Historical Pressure Management": "Historical Pressure Management",
    "Initial Oil Saturation (Soi)": "Initial Oil Saturation (Soi)",
    "Initial Reservoir Pressure (psi)": "Initial Reservoir Pressure (psi)",
    "Injected Fluid": "Injected Fluid",
    "Injectors": "Injectors",
    "Non producing reservoirs ": "Non producing reservoirs",
    "Np_ARPR 1.1.2025": "Np_ARPR 1.1.2025",
    "Oil Column (ft)": "Oil Column (ft)",
    "Oil API": "Oil API",
    "Oil FVF (Boi)": "Oil FVF (Boi)",
    "Oil Producers": "Oil Producers",
    "Oil Viscosity (cP)": "Oil Viscosity (cP)",
    "Remarks_Nis": "Remarks_Nis",
    "RCI": "RCI",
    "Reservoir Temperature (F)": "Reservoir Temperature (F)",
    "Reservoir": "Reservoir",
    "RF Gap =Benchmark  RF - Field RF (%) ": "RF Gap = Benchmark RF − Field RF (%)",
    "RF Gap =Benchmark  RF - Field RF (%) abs ": "RF Gap = Benchmark RF − Field RF (%) abs",
    "RF_ARPR 1.1.2025 (calculated) ": "RF_ARPR 1.1.2025 (calculated)",
    "Solution GOR (scf/bbl)": "Solution GOR (scf/bbl)",
    "STOIIP_ARPR 1.1.2025": "STOIIP_ARPR 1.1.2025",
    "Temp (deg C)": "Temp (deg C)",
    "UR_ARPR 1.1.2025": "UR_ARPR 1.1.2025",
}


class CandidateDataError(RuntimeError):
    """Raised when the candidate workbook cannot be loaded or validated."""


class CandidateRepository:
    """Load and normalize Field / Reservoir parameter data.

    The repository deliberately has no dependency on the EOR screening stack.
    It reads the workbook directly and returns a clean analytical DataFrame.
    """

    def __init__(
        self,
        workbook_path: str | Path | None = None,
        primary_sheet: str = PRIMARY_SHEET,
        coordinate_sheet: str = COORDINATE_SHEET,
    ) -> None:
        self.workbook_path = Path(workbook_path or settings.workbook_path)
        self.primary_sheet = primary_sheet
        self.coordinate_sheet = coordinate_sheet

    @staticmethod
    def _norm_text(value: Any) -> str:
        if pd.isna(value):
            return ""
        text = str(value).strip().upper()
        text = " ".join(text.split())
        return text

    @classmethod
    def _make_key(cls, field: Any, reservoir: Any) -> str:
        return f"{cls._norm_text(field)}|||{cls._norm_text(reservoir)}"

    @staticmethod
    def _to_numeric(series: pd.Series) -> pd.Series:
        cleaned = (
            series.astype("string")
            .str.replace(",", "", regex=False)
            .str.replace("%", "", regex=False)
            .str.strip()
        )
        return pd.to_numeric(cleaned, errors="coerce")

    def _validate_workbook(self) -> None:
        if not self.workbook_path.is_file():
            raise CandidateDataError(
                f"Candidate workbook not found: {self.workbook_path}"
            )

    def load(self) -> pd.DataFrame:
        """Load the candidate dataset and enrich it with v2 coordinates."""
        self._validate_workbook()

        try:
            primary = pd.read_excel(
                self.workbook_path,
                sheet_name=self.primary_sheet,
                engine="openpyxl",
            )
            coords = pd.read_excel(
                self.workbook_path,
                sheet_name=self.coordinate_sheet,
                engine="openpyxl",
            )
        except Exception as exc:
            raise CandidateDataError(
                f"Unable to read candidate workbook sheets "
                f"'{self.primary_sheet}' and '{self.coordinate_sheet}': {exc}"
            ) from exc

        if primary.empty:
            raise CandidateDataError(
                f"Sheet '{self.primary_sheet}' contains no records."
            )

        primary = primary.copy()
        coords = coords.copy()

        required = {"Field", "Reservoir"}
        missing = required.difference(primary.columns)
        if missing:
            raise CandidateDataError(
                f"Sheet '{self.primary_sheet}' is missing required columns: "
                f"{sorted(missing)}"
            )

        primary["Field"] = primary["Field"].fillna("").astype(str).str.strip()
        primary["Reservoir"] = primary["Reservoir"].fillna("").astype(str).str.strip()

        if "Field & Reservoir " not in primary.columns:
            primary["Field & Reservoir "] = primary.apply(
                lambda row: f"{row['Field']} — {row['Reservoir']}".strip(" —"),
                axis=1,
            )
        else:
            missing_combo = primary["Field & Reservoir "].isna() | (
                primary["Field & Reservoir "].astype(str).str.strip() == ""
            )
            primary.loc[missing_combo, "Field & Reservoir "] = primary.loc[
                missing_combo
            ].apply(
                lambda row: f"{row['Field']} — {row['Reservoir']}".strip(" —"),
                axis=1,
            )

        for column in NUMERIC_COLUMNS:
            if column in primary.columns:
                primary[column] = self._to_numeric(primary[column])

        for coordinate_column in ("LATITUDE", "LONGITUDE"):
            if coordinate_column in coords.columns:
                coords[coordinate_column] = self._to_numeric(
                    coords[coordinate_column]
                )

        # Coordinates exist only in v2, so they are intentionally joined as an
        # enrichment layer and are never used as screening/ML inputs.
        if {"Field", "Reservoir"}.issubset(coords.columns):
            coordinate_columns = [
                column
                for column in ["Field", "Reservoir", "LATITUDE", "LONGITUDE"]
                if column in coords.columns
            ]
            coord_df = coords[coordinate_columns].copy()
            coord_df["__candidate_key"] = coord_df.apply(
                lambda row: self._make_key(row.get("Field"), row.get("Reservoir")),
                axis=1,
            )
            coord_df = coord_df.drop_duplicates("__candidate_key", keep="first")
            coord_df = coord_df[
                ["__candidate_key", "LATITUDE", "LONGITUDE"]
            ]
        else:
            coord_df = pd.DataFrame(
                columns=["__candidate_key", "LATITUDE", "LONGITUDE"]
            )

        primary["__candidate_key"] = primary.apply(
            lambda row: self._make_key(row.get("Field"), row.get("Reservoir")),
            axis=1,
        )

        result = primary.merge(
            coord_df,
            on="__candidate_key",
            how="left",
            suffixes=("", "_v2"),
        )

        # Prefer v2 coordinate values when the primary sheet happens to contain
        # stale or differently named coordinate columns.
        if "LATITUDE_v2" in result.columns:
            result["LATITUDE"] = result["LATITUDE"].fillna(result["LATITUDE_v2"])
            result.drop(columns=["LATITUDE_v2"], inplace=True)
        if "LONGITUDE_v2" in result.columns:
            result["LONGITUDE"] = result["LONGITUDE"].fillna(
                result["LONGITUDE_v2"]
            )
            result.drop(columns=["LONGITUDE_v2"], inplace=True)

        result["Field"] = result["Field"].astype(str).str.strip()
        result["Reservoir"] = result["Reservoir"].astype(str).str.strip()
        result["Field & Reservoir "] = result["Field & Reservoir "].astype(str).str.strip()

        # Useful UI labels; these do not alter source engineering values.
        result["Reservoir Producing Status"] = result.get(
            "Non producing reservoirs ", pd.Series(index=result.index, dtype=float)
        ).map(
            lambda value: "NONPRODUCING" if pd.notna(value) and value > 0 else "PRODUCING"
        )

        result.drop(columns=["__candidate_key"], inplace=True)

        return result.reset_index(drop=True)

    def source_summary(self, df: pd.DataFrame) -> dict[str, Any]:
        """Return transparent source and quality statistics for the UI."""
        return {
            "workbook": self.workbook_path.name,
            "primary_sheet": self.primary_sheet,
            "coordinate_sheet": self.coordinate_sheet,
            "rows": int(len(df)),
            "fields": int(df["Field"].nunique(dropna=True)),
            "coordinates": int(
                df[["LATITUDE", "LONGITUDE"]].dropna().shape[0]
                if {"LATITUDE", "LONGITUDE"}.issubset(df.columns)
                else 0
            ),
        }
