"""
EOR Atlas
Central application configuration.

Single source of truth for:
- project paths
- workbook/reference files
- ML model artifacts
- ML configuration
- engineering thresholds
- Streamlit UI configuration

No Streamlit execution logic belongs here.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class Settings:
    """Central configuration for the EOR Atlas application."""

    def __init__(self) -> None:

        # ================================================================
        # PROJECT PATHS
        #
        # Expected repository structure:
        #
        # EORWEBDEV/
        # ├── app.py
        # ├── data/
        # ├── outputs/
        # │   └── model_artifacts/
        # ├── EOR_Screening_Tool_2026.xlsx
        # └── src/
        #     └── config/
        #         └── settings.py
        # ================================================================

        self.settings_dir = Path(__file__).resolve().parent
        self.config_dir = self.settings_dir
        self.src_dir = self.config_dir.parent

        # settings.py:
        # EORWEBDEV/src/config/settings.py
        #
        # parent      -> EORWEBDEV/src
        # parent.parent -> EORWEBDEV
        self.project_root = self.src_dir.parent

        # ================================================================
        # DATA DIRECTORIES
        # ================================================================

        self.data_dir = (
            self.project_root / "data"
        )

        self.outputs_dir = (
            self.project_root / "outputs"
        )

        self.model_dir = (
            self.outputs_dir / "model_artifacts"
        )

        # ================================================================
        # ENGINEERING WORKBOOK / REFERENCE DATA
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
        # ACTIVE CATBOOST MODEL
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

        self.fuzzy_alpha = float(
            self.ml_config.get(
                "alpha",
                0.30,
            )
        )

        # ================================================================
        # ENGINEERING PARAMETERS
        # ================================================================

        self.engineering_params: dict[str, Any] = {
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
        # STREAMLIT UI
        # ================================================================

        self.ui_config: dict[str, Any] = {
            "page_title": (
                "EOR Atlas – Decision Support Platform"
            ),
            "page_icon": "📈",
            "layout": "wide",
            "initial_sidebar_state": "expanded",

            "formation_categories": [
                "Sandstone",
                "Carbonates",
                "Unconsolidated sands",
            ],

            "default_formation": "Sandstone",
        }

        # ================================================================
        # APPLICATION METADATA
        # ================================================================

        self.app_name = "EOR Atlas"
        self.app_version = "1.0.0"
        self.environment = "development"

    # ================================================================
    # ML CONFIGURATION
    # ================================================================

    def _load_ml_config(self) -> dict[str, Any]:
        """Load the active CatBoost model configuration."""

        if not self.config_path.is_file():
            return {
                "model_name": self.model_name,
                "version": self.model_version,
            }

        try:
            with self.config_path.open(
                "r",
                encoding="utf-8",
            ) as file:
                config = json.load(file)

            if not isinstance(config, dict):
                raise ValueError(
                    "ML configuration must be a JSON object."
                )

            return config

        except (
            OSError,
            json.JSONDecodeError,
            ValueError,
        ) as exc:

            print(
                "Warning: Could not load CatBoost configuration: "
                f"{exc}"
            )

            return {
                "model_name": self.model_name,
                "version": self.model_version,
            }

    # ================================================================
    # ENGINEERING PARAMETERS
    # ================================================================

    def get_engineering_param(
        self,
        key: str,
        default: Any = None,
    ) -> Any:
        """Return an engineering configuration parameter."""

        return self.engineering_params.get(
            key,
            default,
        )

    # ================================================================
    # PATH VALIDATION
    # ================================================================

    def validate_paths(self) -> dict[str, bool]:
        """Validate all required EOR Atlas paths."""

        return {
            "project_root": self.project_root.is_dir(),
            "src_dir": self.src_dir.is_dir(),
            "data_dir": self.data_dir.is_dir(),
            "outputs_dir": self.outputs_dir.is_dir(),
            "model_dir": self.model_dir.is_dir(),

            "model": self.model_path.is_file(),
            "label_encoder": self.label_encoder_path.is_file(),
            "config": self.config_path.is_file(),
            "manifest": self.model_manifest_path.is_file(),

            "ranges": self.ranges_path.is_file(),
            "workbook": self.workbook_path.is_file(),
        }

    # ================================================================
    # MODEL ARTIFACT DIAGNOSTICS
    # ================================================================

    def get_model_artifact_status(
        self,
    ) -> dict[str, Any]:
        """Return detailed diagnostics for production ML artifacts."""

        return {
            "project_root": str(
                self.project_root
            ),

            "data_dir": str(
                self.data_dir
            ),

            "model_dir": str(
                self.model_dir
            ),

            "model_path": str(
                self.model_path
            ),

            "label_encoder_path": str(
                self.label_encoder_path
            ),

            "config_path": str(
                self.config_path
            ),

            "model_manifest_path": str(
                self.model_manifest_path
            ),

            "paths": self.validate_paths(),
        }


# ========================================================================
# GLOBAL SETTINGS INSTANCE
# ========================================================================

settings = Settings()