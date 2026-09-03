"""
Configuration module for EOR Atlas
Centralized settings and constants
"""

import os
from dataclasses import dataclass
from pathlib import Path

# Paths
PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
MODEL_ARTIFACTS_DIR = OUTPUTS_DIR / "model_artifacts"

# Ensure directories exist
MODEL_ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

# Model configuration
MODEL_CONFIG = {
    "name": "EOR CatBoost",
    "version": "1.0.0",
    "model_file": MODEL_ARTIFACTS_DIR / "eor_catboost_v1.0.0.joblib",
    "encoder_file": MODEL_ARTIFACTS_DIR / "label_encoder_catboost_v1.0.0.joblib",
    "feature_order_file": MODEL_ARTIFACTS_DIR / "model_manifest_catboost_v1.0.0.json",
}

# Feature configuration
FEATURES = [
    "Depth",
    "Porosity",
    "Permeability",
    "API",
    "Viscosity",
    "Oil_Saturation",
    "Formation",
    "Temperature",
    "Clay_Content",
    "Water_Saturation",
    "Net_to_Gross",
    "Trap_Type",
    "Lithology",
    "Underburden",
    "Seal_Quality",
    "Faulting",
    "Dip"
]

NUM_FEATURES = len(FEATURES)

# EOR Technique classes
EOR_TECHNIQUES = [
    "Miscible HC",
    "Steam",
    "Miscible CO2",
    "Polymer",
    "ASP",
    "Other",
    "Not Suitable",
    "Requires Study",
    "Data Missing"
]

NUM_CLASSES = len(EOR_TECHNIQUES)

# Confidence thresholds
CONFIDENCE_THRESHOLDS = {
    "high": 0.70,      # >= 70%
    "moderate": 0.60,  # 60-69.99%
    "low": 0.0         # < 60%
}

CONFIDENCE_LEVELS = {
    "high": "🟢 HIGH",
    "moderate": "🟡 MODERATE",
    "low": "🔴 LOW"
}

# Training metadata
TRAINING_METADATA = {
    "training_rows": 526,
    "features": NUM_FEATURES,
    "classes": NUM_CLASSES,
    "training_source": "OGJ2014",
    "created": "2026-09-02"
}

# Logging configuration
LOGGING_CONFIG = {
    "level": "INFO",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "file": OUTPUTS_DIR / "eor_atlas.log"
}

# Streamlit configuration
STREAMLIT_CONFIG = {
    "page_title": "EOR Atlas",
    "page_icon": "🔍",
    "layout": "wide",
    "initial_sidebar_state": "expanded",
}

# Session management
SESSION_CONFIG = {
    "auto_load_last": False,  # Do NOT auto-load previous session
    "save_sessions": True,
}

# Engineering rule thresholds
ENGINEERING_THRESHOLDS = {
    "viscosity": {
        "steam": (50, float('inf')),          # viscosity > 50 cp favors steam
        "miscible_hc": (0, 35),               # viscosity < 35 cp favors miscible HC
        "polymer": (5, 1000),                 # polymer works in moderate range
    },
    "permeability": {
        "miscible_co2": (50, float('inf')),   # permeability > 50 md favors CO2
        "polymer": (10, 500),                 # polymer works in lower perm
        "asm": (50, float('inf')),            # ASP needs reasonable perm
    },
    "api": {
        "miscible_hc": (30, float('inf')),    # API > 30 for miscible HC
        "steam": (10, 35),                    # API < 35 for steam
    },
    "depth": {
        "steam": (0, 4000),                   # Steam typically < 4000 ft
        "miscible_co2": (2500, float('inf')), # CO2 needs deeper for miscibility
    }
}

# Decision matrix configuration
DECISION_MATRIX = {
    "high_high": {"level": "🟢", "text": "Strong candidate", "priority": 1},
    "high_moderate": {"level": "🟡", "text": "Candidate", "priority": 2},
    "high_low": {"level": "🔴", "text": "Engineering conflict", "priority": 5},
    "moderate_high": {"level": "🟡", "text": "Candidate", "priority": 2},
    "moderate_moderate": {"level": "🟡", "text": "Review required", "priority": 3},
    "low_high": {"level": "🟡", "text": "Engineering review recommended", "priority": 4},
    "low_low": {"level": "🔴", "text": "Weak candidate", "priority": 6},
}
