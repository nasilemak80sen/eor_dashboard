"""
Central configuration management for EOR Atlas.

This module provides a single source of truth for all application settings,
model paths, and engineering parameters.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional


class Settings:
    """EOR Atlas application settings."""
    
    def __init__(self):
        """Initialize settings from configuration files and environment."""
        self.base_dir = Path(__file__).resolve().parent.parent
        self.root_dir = self.base_dir.parent
        
        # Directory paths
        self.model_dir = self.root_dir / "outputs" / "model_artifacts"
        self.data_dir = self.root_dir / "data"
        self.workbook_path = self.root_dir / "EOR_Screening_Tool_2026.xlsx"
        
        # Model artifact paths
        self.model_path = self.model_dir / "eor_nn_alpha03.keras"
        self.scaler_path = self.model_dir / "scaler_alpha03.joblib"
        self.label_encoder_path = self.model_dir / "label_encoder.joblib"
        self.config_path = self.model_dir / "config_alpha03.json"
        
        # Data paths
        self.ranges_path = self.data_dir / "NeuroFuzzy_EOR_Extracted_Tables.xlsx"
        self.ranges_sheet = "Table1_Ranges"
        
        # ML Configuration
        self.ml_config: Dict[str, Any] = self._load_ml_config()
        self.fuzzy_alpha = self.ml_config.get("alpha", 0.30)
        
        # Engineering parameters (NOT exposed to UI)
        self.engineering_params = {
            "rare_class_override_enabled": True,
            "rare_threshold": 0.90,
            "nn_conf_threshold": 0.60,
            "rare_candidates": ["Hot water", "Miscible acid gas"],
        }
        
        # UI Configuration
        self.ui_config = {
            "page_title": "EOR Atlas – Decision Support Platform",
            "page_icon": "🛢️",
            "layout": "wide",
            "formation_categories": ["Sandstone", "Carbonates", "Unconsolidated sands"],
            "default_formation": "Sandstone",
        }
        
        # Application metadata
        self.app_name = "EOR Atlas"
        self.app_version = "2.0.0"
        self.environment = "development"
    
    def _load_ml_config(self) -> Dict[str, Any]:
        """Load ML configuration from artifact path."""
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Warning: Could not load ML config from {self.config_path}: {e}")
                return {"alpha": 0.30, "model_name": "NN_alpha_0.3"}
        return {"alpha": 0.30, "model_name": "NN_alpha_0.3"}
    
    def update_ml_config(self, config: Dict[str, Any]) -> None:
        """Update and persist ML configuration."""
        self.ml_config.update(config)
        if self.config_path.exists():
            try:
                with open(self.config_path, "w", encoding="utf-8") as f:
                    json.dump(self.ml_config, f, indent=2)
            except Exception as e:
                print(f"Warning: Could not save ML config: {e}")
    
    def get_engineering_param(self, key: str, default: Any = None) -> Any:
        """Get engineering parameter (not user-tunable)."""
        return self.engineering_params.get(key, default)
    
    def validate_paths(self) -> Dict[str, bool]:
        """Validate that all required paths exist."""
        return {
            "model": self.model_path.exists(),
            "scaler": self.scaler_path.exists(),
            "label_encoder": self.label_encoder_path.exists(),
            "config": self.config_path.exists(),
            "ranges": self.ranges_path.exists(),
            "workbook": self.workbook_path.exists(),
        }


# Global settings instance
settings = Settings()
