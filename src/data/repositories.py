"""
Data access layer for EOR Atlas.

Handles loading and caching of Excel workbooks, fuzzy envelopes, and other data.
"""

from typing import Dict, Tuple
import pandas as pd
from pathlib import Path

from config.settings import settings
from utils.logging_config import logger


class EnvelopeRepository:
    """Repository for fuzzy envelope data."""
    
    @staticmethod
    def load_envelopes() -> Tuple[Dict, list]:
        """
        Load fuzzy envelopes from Excel ranges data.
        
        Returns:
            Tuple of (envelope_dict, techniques_list)
        """
        try:
            logger.info(f"Loading envelopes from {settings.ranges_path}")
            
            table1 = pd.read_excel(
                settings.ranges_path,
                sheet_name=settings.ranges_sheet,
                engine="openpyxl",
            )
            
            # Normalize column values
            table1["technique"] = table1["EOR technique"].apply(
                EnvelopeRepository._normalize_technique
            )
            table1["formation_category"] = table1["Formation type"].apply(
                EnvelopeRepository._normalize_formation
            )
            
            # Remove invalid rows
            table1 = table1.dropna(subset=["technique", "formation_category"]).copy()
            
            # Build envelope dictionary
            env = {}
            for _, row in table1.iterrows():
                key = (row["technique"], row["formation_category"])
                env[key] = {
                    "depth": (row["Depth min (ft)"], row["Depth max (ft)"]),
                    "por": (row["Porosity min (%)"], row["Porosity max (%)"]),
                    "perm": (
                        row["Permeability min (mD)"],
                        row["Permeability max (mD)"],
                    ),
                    "api": (
                        row["Oil gravity min (°API)"],
                        row["Oil gravity max (°API)"],
                    ),
                    "visc": (
                        row["Oil viscosity min (cp)"],
                        row["Oil viscosity max (cp)"],
                    ),
                    "so": (
                        row["So at start min (%)"],
                        row["So at start max (%)"],
                    ),
                }
            
            # Extract unique techniques
            techs_all = sorted(set(key[0] for key in env.keys()))
            
            logger.info(f"Loaded {len(env)} envelopes for {len(techs_all)} techniques")
            return env, techs_all
            
        except Exception as e:
            logger.error(f"Failed to load envelopes: {e}")
            raise
    
    @staticmethod
    def _normalize_technique(x) -> str:
        """Normalize technique name."""
        if pd.isna(x):
            return None
        x = str(x).strip().replace("CO22", "CO2").replace("*", "")
        return x if x else None
    
    @staticmethod
    def _normalize_formation(x) -> str:
        """Normalize formation name."""
        if pd.isna(x):
            return None
        x = str(x).strip().lower()
        if "sandstone" in x:
            return "Sandstone"
        if "unconsolidated" in x:
            return "Unconsolidated sands"
        if "carbonate" in x:
            return "Carbonates"
        return None


class WorkbookRepository:
    """Repository for Excel workbook data."""
    
    @staticmethod
    def load_workbook() -> Dict[str, pd.DataFrame]:
        """
        Load all sheets from EOR workbook.
        
        Returns:
            Dictionary mapping sheet names to DataFrames
        """
        try:
            if not settings.workbook_path.exists():
                logger.warning(f"Workbook not found: {settings.workbook_path}")
                return {}
            
            logger.info(f"Loading workbook: {settings.workbook_path}")
            
            sheets = {}
            excel_file = pd.ExcelFile(settings.workbook_path, engine="openpyxl")
            
            for sheet_name in excel_file.sheet_names:
                try:
                    df = pd.read_excel(
                        settings.workbook_path,
                        sheet_name=sheet_name,
                        engine="openpyxl",
                    )
                    sheets[sheet_name] = df
                except Exception as e:
                    logger.warning(f"Failed to load sheet '{sheet_name}': {e}")
                    sheets[sheet_name] = pd.DataFrame({
                        "sheet": [sheet_name],
                        "note": ["Unable to load sheet automatically"],
                    })
            
            logger.info(f"Loaded {len(sheets)} sheets from workbook")
            return sheets
            
        except Exception as e:
            logger.error(f"Failed to load workbook: {e}")
            return {}
    
    @staticmethod
    def get_sheet(sheets: Dict[str, pd.DataFrame], sheet_name: str) -> pd.DataFrame:
        """
        Retrieve a specific sheet from loaded workbook.
        
        Args:
            sheets: Dictionary of loaded sheets
            sheet_name: Name of sheet to retrieve
        
        Returns:
            DataFrame or empty DataFrame if not found
        """
        if sheet_name not in sheets:
            logger.warning(f"Sheet '{sheet_name}' not found in workbook")
            return pd.DataFrame()
        
        return sheets[sheet_name]
