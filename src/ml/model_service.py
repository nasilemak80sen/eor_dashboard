"""
Neural network model service for EOR screening.

Handles loading, caching, and inference with the trained Keras model.
"""

from typing import Dict, Tuple, List
import numpy as np
import pandas as pd
from tensorflow import keras
import joblib
from pathlib import Path

from config.settings import settings
from utils.logging_config import logger


class ModelService:
    """Service for ML model operations."""
    
    def __init__(self):
        """Initialize model service."""
        self.model = None
        self.scaler = None
        self.label_encoder = None
        self.config = None
        self._loaded = False
    
    def load(self) -> bool:
        """
        Load model artifacts.
        
        Returns:
            True if loading successful, False otherwise
        """
        try:
            logger.info("Loading ML artifacts...")
            
            self.model = keras.models.load_model(settings.model_path)
            self.scaler = joblib.load(settings.scaler_path)
            self.label_encoder = joblib.load(settings.label_encoder_path)
            self.config = settings.ml_config
            
            self._loaded = True
            logger.info("ML artifacts loaded successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load ML artifacts: {e}")
            self._loaded = False
            return False
    
    def is_loaded(self) -> bool:
        """Check if model is loaded."""
        return self._loaded
    
    def build_features(
        self,
        values: Dict[str, float],
        formation: str,
        techs_all: List[str],
        fuzzy_scores: Dict[str, float],
    ) -> np.ndarray:
        """
        Build feature vector for model inference.
        
        Args:
            values: Input parameters
            formation: Formation type
            techs_all: List of all EOR techniques
            fuzzy_scores: Fuzzy suitability scores
        
        Returns:
            Feature vector ready for model.predict()
        """
        # Numeric features (raw and derived)
        depth_mid = values["depth_ft"]
        por_mid = values["porosity_pct"]
        perm_mid = values["perm_md"]
        api_mid = values["api"]
        visc_mid = values["visc_cp"]
        so_mid = values["so_pct"]
        
        # Span features (uncertainty ranges - set to 0 for point estimates)
        depth_span = 0.0
        por_span = 0.0
        perm_span = 0.0
        api_span = 0.0
        visc_span = 0.0
        so_span = 0.0
        
        eps = 1e-6
        numeric = np.array(
            [
                depth_mid,
                por_mid,
                perm_mid,
                api_mid,
                visc_mid,
                so_mid,
                depth_span,
                por_span,
                perm_span,
                api_span,
                visc_span,
                so_span,
                np.log10(max(perm_mid, 0.0) + eps),
                np.log10(max(visc_mid, 0.0) + eps),
                np.log10(perm_span + 1.0 + eps),
                np.log10(visc_span + 1.0 + eps),
            ],
            dtype=float,
        )
        
        # Formation one-hot encoding
        form_names = ["Sandstone", "Carbonates", "Unconsolidated sands"]
        form_onehot = np.array(
            [1.0 if formation == name else 0.0 for name in form_names],
            dtype=float,
        )
        
        # Fuzzy scores for all techniques
        fuzzy_vec = np.array(
            [fuzzy_scores.get(t, 0.0) for t in techs_all],
            dtype=float,
        )
        
        # Concatenate all features
        features = np.concatenate([numeric, form_onehot, fuzzy_vec], axis=0)
        
        return features
    
    def predict(
        self,
        features: np.ndarray,
    ) -> Tuple[np.ndarray, List[Tuple[str, float]]]:
        """
        Generate predictions.
        
        Args:
            features: Feature vector
        
        Returns:
            Tuple of (probabilities, top3_list)
        """
        if not self._loaded:
            logger.error("Model not loaded")
            return None, []
        
        # Scale features
        scaled_features = self.scaler.transform([features])
        
        # Get predictions
        probabilities = self.model.predict(scaled_features, verbose=0)[0]
        
        # Get top 3 predictions
        top3_idx = np.argsort(probabilities)[-3:][::-1]
        top3 = [
            (self.label_encoder.inverse_transform([idx])[0], float(probabilities[idx]))
            for idx in top3_idx
        ]
        
        return probabilities, top3
    
    def get_model_info(self) -> Dict:
        """
        Get model information and configuration.
        
        Returns:
            Dictionary with model metadata
        """
        if not self._loaded:
            return {"error": "Model not loaded"}
        
        return {
            "model_name": self.config.get("model_name", "Unknown"),
            "alpha": self.config.get("alpha", 0.30),
            "num_classes": len(self.label_encoder.classes_),
            "classes": list(self.label_encoder.classes_),
            "feature_shape": self.scaler.n_features_in_,
        }
