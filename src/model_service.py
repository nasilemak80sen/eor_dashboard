"""
<<<<<<< HEAD
<<<<<<< HEAD
EOR Atlas — UI-facing ML Model Service.

This module is the single ML entry point used by Streamlit.

Responsibilities
----------------
- Use central settings for all artifact paths.
- Load the production CatBoost ModelService.
- Convert UI reservoir inputs into the trained reservoir schema.
- Run prediction.
- Expose model status and metadata.

The Streamlit UI does not load CatBoost directly.
"""

from __future__ import annotations

from typing import Any

from src.ml.model_service import ModelService as ProductionModelService
=======
=======
>>>>>>> a771333522df95dfdfc0081485a1c62325356edc
ModelService: Phase 3B integration layer
Encapsulates all ML operations and returns PredictionResult
UI should never call CatBoost directly
"""

import logging
from typing import Optional, Dict, List
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from src.config import MODEL_CONFIG, FEATURES, NUM_CLASSES, EOR_TECHNIQUES
from src.ml_prediction import PredictionResult, ConfidenceLevel

logger = logging.getLogger(__name__)
<<<<<<< HEAD
>>>>>>> a771333522df95dfdfc0081485a1c62325356edc
=======
>>>>>>> a771333522df95dfdfc0081485a1c62325356edc


class ModelService:
    """
<<<<<<< HEAD
<<<<<<< HEAD
    Application-facing ML service.

    This is intentionally a thin facade over
    src.ml.model_service.ModelService.
    """

    def __init__(self) -> None:
        self._service = ProductionModelService()

        # Compatibility attributes used by the existing UI.
        self.model = self._service.model
        self.encoder = self._service.encoder
        self.error_message: str | None = None

    # ================================================================
    # STATUS
    # ================================================================

    def is_model_loaded(self) -> bool:
        """Return True when the production model is ready."""

        return self._service.is_loaded()

    def is_loaded(self) -> bool:
        """Alias for modern callers."""

        return self._service.is_loaded()

    # ================================================================
    # MODEL INFORMATION
    # ================================================================

    def get_model_info(self) -> dict[str, Any]:
        """Return production model metadata."""

        return self._service.get_model_info()

    # ================================================================
    # UI INPUT → MODEL INPUT
    # ================================================================

    @staticmethod
    def _to_model_input(
        reservoir_data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Convert Streamlit's single-value reservoir inputs into
        the range-based schema expected by feature_builder.py.

        A single UI measurement is represented as min == max.
        """

        formation_map = {
            "Sandstone": "Sandstone",
            "Carbonate": "Carbonates",
            "Carbonates": "Carbonates",
            "Unconsolidated sands": "Unconsolidated sands",
        }

        formation = formation_map.get(
            str(
                reservoir_data.get(
                    "Formation",
                    "Sandstone",
                )
            ).strip(),
            "Sandstone",
        )

        def number(
            key: str,
            default: float,
        ) -> float:
            value = reservoir_data.get(key, default)
            return float(value)

        depth = number("Depth", 5000.0)
        porosity = number("Porosity", 20.0)
        permeability = number("Permeability", 100.0)
        api = number("API", 32.0)
        viscosity = number("Viscosity", 10.0)
        oil_saturation = number(
            "Oil_Saturation",
            65.0,
        )

        return {
            "depth_min_ft": depth,
            "depth_max_ft": depth,

            "porosity_min_pct": porosity,
            "porosity_max_pct": porosity,

            "perm_min_md": permeability,
            "perm_max_md": permeability,

            "api_min": api,
            "api_max": api,

            "visc_min_cp": viscosity,
            "visc_max_cp": viscosity,

            "so_min_pct": oil_saturation,
            "so_max_pct": oil_saturation,

            "formation_category": formation,
        }

    # ================================================================
    # PREDICTION
    # ================================================================

    def predict(
        self,
        reservoir_data: dict[str, Any],
    ):
        """
        Run production CatBoost inference.

        The UI can continue passing its existing reservoir dictionary.
        """

        model_input = self._to_model_input(
            reservoir_data
        )

        result = self._service.predict(
            model_input
        )

        return result

    # ================================================================
    # BATCH PREDICTION
    # ================================================================

    def batch_predict(
        self,
        reservoirs: list[dict[str, Any]],
    ):
        """Run prediction for multiple UI reservoir records."""

        return [
            self.predict(reservoir)
            for reservoir in reservoirs
        ]

    # ================================================================
    # CANDIDATE / EXPLANATION HELPERS
    # ================================================================

    def explain_prediction(
        self,
        result,
    ) -> dict[str, Any]:
        """Return a simple serializable prediction explanation."""

        return {
            "predicted_technique": result.technique,
            "confidence": result.confidence,
            "confidence_level": result.confidence_level,
            "top_candidates": [
                {
                    "technique": candidate.technique,
                    "probability": candidate.probability,
                    "rank": candidate.rank,
                }
                for candidate in result.candidates[:3]
            ],
            "warning": result.warning,
        }
=======
=======
>>>>>>> a771333522df95dfdfc0081485a1c62325356edc
    Phase 3B: ML service layer
    
    Responsibilities:
    - Load model and encoder
    - Handle feature validation
    - Run predictions
    - Return PredictionResult (not raw CatBoost output)
    
    The UI doesn't know this uses CatBoost.
    """
    
    def __init__(self):
        """Initialize model service"""
        self.model = None
        self.encoder = None
        self.feature_order = FEATURES.copy()
        self.is_ready = False
        self.error_message = None
        
        # Attempt to load model
        self._load_model()
        self._load_encoder()
    
    def _load_model(self) -> bool:
        """Load CatBoost model"""
        try:
            model_path = MODEL_CONFIG["model_file"]
            if not model_path.exists():
                self.error_message = f"Model file not found: {model_path}"
                logger.error(self.error_message)
                return False
            
            self.model = joblib.load(model_path)
            logger.info(f"Model loaded from {model_path}")
            return True
        
        except Exception as e:
            self.error_message = f"Failed to load model: {str(e)}"
            logger.error(self.error_message)
            return False
    
    def _load_encoder(self) -> bool:
        """Load label encoder"""
        try:
            encoder_path = MODEL_CONFIG["encoder_file"]
            if not encoder_path.exists():
                self.error_message = f"Encoder file not found: {encoder_path}"
                logger.error(self.error_message)
                return False
            
            self.encoder = joblib.load(encoder_path)
            logger.info(f"Encoder loaded from {encoder_path}")
            return True
        
        except Exception as e:
            self.error_message = f"Failed to load encoder: {str(e)}"
            logger.error(self.error_message)
            return False
    
    def validate_inputs(self, reservoir_data: Dict) -> tuple[bool, Optional[str]]:
        """
        Validate reservoir input data
        
        Returns:
            (is_valid, error_message)
        """
        # Check all required features present
        missing = [f for f in self.feature_order if f not in reservoir_data]
        if missing:
            return False, f"Missing features: {', '.join(missing)}"
        
        # Check no NaN values
        for feature, value in reservoir_data.items():
            if value is None or (isinstance(value, float) and np.isnan(value)):
                return False, f"Feature '{feature}' has missing value"
        
        # Check value ranges (basic sanity checks)
        if reservoir_data.get("Depth", 0) <= 0:
            return False, "Depth must be positive"
        
        if not (0 <= reservoir_data.get("Porosity", 0) <= 100):
            return False, "Porosity must be 0-100%"
        
        if not (0 <= reservoir_data.get("Oil_Saturation", 0) <= 100):
            return False, "Oil saturation must be 0-100%"
        
        if reservoir_data.get("Permeability", 0) < 0:
            return False, "Permeability must be non-negative"
        
        if not (0 <= reservoir_data.get("API", 0) <= 100):
            return False, "API gravity must be 0-100"
        
        return True, None
    
    def predict(self, reservoir_data: Dict) -> PredictionResult:
        """
        Make prediction for reservoir
        
        Phase 3B: Returns PredictionResult, not raw model output
        
        Args:
            reservoir_data: Dict with reservoir properties
        
        Returns:
            PredictionResult object
        """
        
        # Validate inputs
        is_valid, error_msg = self.validate_inputs(reservoir_data)
        if not is_valid:
            return PredictionResult(
                technique="Error",
                confidence=0.0,
                confidence_level="🔴 ERROR",
                error_message=error_msg,
                is_valid=False
            )
        
        # Check model is loaded
        if not self.model or not self.encoder:
            return PredictionResult(
                technique="Error",
                confidence=0.0,
                confidence_level="🔴 ERROR",
                error_message=self.error_message or "Model not loaded",
                is_valid=False
            )
        
        try:
            # Prepare feature vector in correct order
            features_list = [reservoir_data[f] for f in self.feature_order]
            X = np.array([features_list])
            
            # Get prediction
            prediction_encoded = self.model.predict(X)[0]
            prediction_proba = self.model.predict_proba(X)[0]
            
            # Decode technique
            predicted_technique = self.encoder.inverse_transform([prediction_encoded])[0]
            
            # Get confidence
            max_confidence = float(np.max(prediction_proba))
            
            # Get all candidates sorted by probability
            candidates = []
            for idx, prob in enumerate(prediction_proba):
                technique_name = self.encoder.inverse_transform([idx])[0]
                candidates.append((technique_name, float(prob)))
            
            candidates = sorted(candidates, key=lambda x: x[1], reverse=True)
            
            # Get confidence level
            confidence_level = ConfidenceLevel.from_confidence(max_confidence)
            
            # Get feature importance
            feature_importance = self._get_feature_importance()
            
            logger.info(
                f"Prediction: {predicted_technique} ({max_confidence:.1%})"
            )
            
            return PredictionResult(
                technique=predicted_technique,
                confidence=max_confidence,
                confidence_level=confidence_level.value,
                candidates=candidates,
                model_name=MODEL_CONFIG["name"],
                model_version=MODEL_CONFIG["version"],
                feature_importance=feature_importance,
                is_valid=True
            )
        
        except Exception as e:
            error_msg = f"Prediction failed: {str(e)}"
            logger.error(error_msg)
            return PredictionResult(
                technique="Error",
                confidence=0.0,
                confidence_level="🔴 ERROR",
                error_message=error_msg,
                is_valid=False
            )
    
    def _get_feature_importance(self) -> Dict[str, float]:
        """
        Get feature importance from model
        
        For CatBoost, returns feature importance scores
        """
        try:
            if hasattr(self.model, 'get_feature_importance'):
                importance = self.model.get_feature_importance()
                importance_dict = {
                    feature: float(imp)
                    for feature, imp in zip(self.feature_order, importance)
                }
                # Normalize to 0-1
                max_imp = max(importance_dict.values()) if importance_dict else 1
                if max_imp > 0:
                    importance_dict = {
                        k: v / max_imp for k, v in importance_dict.items()
                    }
                return importance_dict
        except Exception as e:
            logger.warning(f"Could not get feature importance: {e}")
        
        return {}
    
    def is_model_loaded(self) -> bool:
        """Check if model is ready"""
        return self.model is not None and self.encoder is not None
    
    def get_model_info(self) -> Dict:
        """Get model metadata for display"""
        return {
            "model_name": MODEL_CONFIG["name"],
            "version": MODEL_CONFIG["version"],
            "num_features": len(self.feature_order),
            "num_classes": NUM_CLASSES,
            "classes": EOR_TECHNIQUES,
            "is_ready": self.is_model_loaded(),
            "error": self.error_message,
        }
    
    def batch_predict(
        self,
        reservoirs: List[Dict]
    ) -> List[PredictionResult]:
        """
        Predict for multiple reservoirs
        
        Args:
            reservoirs: List of reservoir data dicts
        
        Returns:
            List of PredictionResult objects
        """
        return [self.predict(r) for r in reservoirs]
    
    def explain_prediction(
        self,
        result: PredictionResult
    ) -> Dict:
        """
        Generate explanation for a prediction
        
        Returns details about why prediction was made
        """
        explanation = {
            "predicted_technique": result.technique,
            "confidence": result.confidence_percentage,
            "top_candidates": result.get_top_candidates(3),
            "feature_importance": result.feature_importance,
        }
        
        # Add warnings if confidence is low
        if result.should_warn_low_confidence():
            explanation["warning"] = (
                "Low model confidence. "
                "Engineering review is highly recommended."
            )
        
        return explanation
<<<<<<< HEAD
>>>>>>> a771333522df95dfdfc0081485a1c62325356edc
=======
>>>>>>> a771333522df95dfdfc0081485a1c62325356edc
