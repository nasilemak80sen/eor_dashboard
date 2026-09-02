"""
EOR Atlas
Central application configuration.

This module contains:
- project paths
- ML artifact configuration
- engineering configuration
- UI configuration

No Streamlit logic should live here.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class Settings:
    """Central configuration for EOR Atlas."""

    def __init__(self) -> None:

        # ================================================================
        # PROJECT PATHS
        # ================================================================

        self.src_dir = Path(__file__).resolve().parent

        self.project_root = self.src_dir.parent.parent

        self.data_dir = self.project_root / "data"

        self.outputs_dir = self.project_root / "outputs"

        self.model_dir = self.outputs_dir / "model_artifacts"

        # ================================================================
        # WORKBOOK
        # ================================================================

        self.workbook_path = (
            self.project_root /
            "EOR_Screening_Tool_2026.xlsx"
        )

        self.ranges_path = (
            self.data_dir /
            "NeuroFuzzy_EOR_Extracted_Tables.xlsx"
        )

        self.ranges_sheet = "Table1_Ranges"

        # ================================================================
        # ACTIVE MODEL
        # ================================================================

        self.model_name = "EOR CatBoost"

        self.model_version = "1.0.0"

        self.model_path = (
            self.model_dir /
            "eor_catboost_v1.0.0.joblib"
        )

        self.label_encoder_path = (
            self.model_dir /
            "label_encoder_catboost_v1.0.0.joblib"
        )

        self.config_path = (
            self.model_dir /
            "config_catboost_v1.0.0.json"
        )

        self.model_manifest_path = (
            self.model_dir /
            "model_manifest_catboost_v1.0.0.json"
        )

        # ================================================================
        # ML CONFIGURATION
        # ================================================================

        self.ml_config = self._load_ml_config()

        self.fuzzy_alpha = self.ml_config.get(
            "alpha",
            0.30,
        )

        # ================================================================
        # ENGINEERING PARAMETERS
        # ================================================================

        self.engineering_params = {

            "confidence_threshold": 0.60,

            "high_confidence_threshold": 0.75,

            "rare_class_override_enabled": True,

            "rare_threshold": 0.90,

            "rare_candidates": [
                "Hot water",
                "Miscible acid gas",
            ],
        }

        # ================================================================
        # UI
        # ================================================================

        self.ui_config = {

            "page_title":
                "EOR Atlas – Decision Support Platform",

            "page_icon":
                "📈",

            "layout":
                "wide",

            "formation_categories": [
                "Sandstone",
                "Carbonates",
                "Unconsolidated sands",
            ],

            "default_formation":
                "Sandstone",
        }

        # ================================================================
        # APPLICATION METADATA
        # ================================================================

        self.app_name = "EOR Atlas"

        self.app_version = "1.0.0"

        self.environment = "development"

    # ====================================================================
    # ML CONFIG
    # ====================================================================

    def _load_ml_config(self) -> dict[str, Any]:

        if not self.config_path.exists():

            return {
                "model_name": self.model_name,
                "version": self.model_version,
            }

        try:

            with self.config_path.open(
                "r",
                encoding="utf-8",
            ) as file:

                return json.load(file)

        except (OSError, json.JSONDecodeError) as exc:

            print(
                f"Warning: Could not load ML config: {exc}"
            )

            return {
                "model_name": self.model_name,
                "version": self.model_version,
            }

    # ====================================================================
    # ENGINEERING PARAMETER
    # ====================================================================

    def get_engineering_param(
        self,
        key: str,
        default: Any = None,
    ) -> Any:

        return self.engineering_params.get(
            key,
            default,
        )

    # ====================================================================
    # PATH VALIDATION
    # ====================================================================

    def validate_paths(self) -> dict[str, bool]:

        return {

            "project_root":
                self.project_root.exists(),

            "model_dir":
                self.model_dir.exists(),

            "model":
                self.model_path.exists(),

            "label_encoder":
                self.label_encoder_path.exists(),

            "config":
                self.config_path.exists(),

            "ranges":
                self.ranges_path.exists(),

            "workbook":
                self.workbook_path.exists(),
        }


# ========================================================================
# GLOBAL SETTINGS INSTANCE
# ========================================================================

settings = Settings()