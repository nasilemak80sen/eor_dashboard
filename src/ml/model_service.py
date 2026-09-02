"""
Production ML inference service for EOR Atlas.

Active model:
    CatBoostClassifier

Responsibilities:
    - Load persisted CatBoost model
    - Load label encoder
    - Load model configuration
    - Build the exact feature vector expected by research pipeline
    - Run probability inference
    - Return Top-N EOR techniques

Important architecture rule:

    Excel Screening != Fuzzy Engine != CatBoost

This service does NOT:
    - determine engineering feasibility
    - modify Excel screening results
    - combine fuzzy and ML scores
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

import joblib
import numpy as np
from utils.logging_config import logger
from config.settings import settings

class ModelService:
    """Production inference service for EOR CatBoost model."""

    def __init__(self) -> None:
        self.model = None
        self.label_encoder = None
        self.config: Dict[str, Any] = {}
        self._loaded = False

    # ============================================================
    # LOAD
    # ============================================================

    def load(self) -> bool:
        """Load CatBoost model and supporting artifacts."""

        try:
            logger.info("Loading EOR CatBoost artifacts...")

            model_path = Path(settings.model_path)
            encoder_path = Path(settings.label_encoder_path)
            config_path = Path(settings.config_path)

            logger.info("Model: %s", model_path)
            logger.info("Encoder: %s", encoder_path)
            logger.info("Config: %s", config_path)

            # ----------------------------------------------------
            # Validate paths
            # ----------------------------------------------------

            if not model_path.exists():
                raise FileNotFoundError(
                    f"CatBoost model not found: {model_path}"
                )

            if not encoder_path.exists():
                raise FileNotFoundError(
                    f"Label encoder not found: {encoder_path}"
                )

            if not config_path.exists():
                raise FileNotFoundError(
                    f"CatBoost config not found: {config_path}"
                )

            # ----------------------------------------------------
            # Load artifacts
            # ----------------------------------------------------

            self.model = joblib.load(model_path)

            self.label_encoder = joblib.load(
                encoder_path
            )

            with open(
                config_path,
                "r",
                encoding="utf-8",
            ) as f:
                import json
                self.config = json.load(f)

            # ----------------------------------------------------
            # Validate compatibility
            # ----------------------------------------------------

            self._validate_artifacts()

            self._loaded = True

            logger.info(
                "CatBoost model loaded successfully."
            )

            return True

        except Exception as exc:

            logger.exception(
                "Failed to load CatBoost artifacts: %s",
                exc,
            )

            self._loaded = False

            return False

    # ============================================================
    # VALIDATION
    # ============================================================

    def _validate_artifacts(self) -> None:
        """Validate persisted CatBoost artifacts."""

        if self.model is None:
            raise ValueError(
                "CatBoost model is None."
            )

        if self.label_encoder is None:
            raise ValueError(
                "Label encoder is None."
            )

        # --------------------------------------------------------
        # Model type
        # --------------------------------------------------------

        model_type = type(self.model).__name__

        if model_type != "CatBoostClassifier":
            raise ValueError(
                "Expected CatBoostClassifier, "
                f"received {model_type}."
            )

        # --------------------------------------------------------
        # Probability support
        # --------------------------------------------------------

        if not hasattr(
            self.model,
            "predict_proba",
        ):
            raise ValueError(
                "CatBoost model does not support "
                "predict_proba()."
            )

        # --------------------------------------------------------
        # Feature count
        # --------------------------------------------------------

        expected_features = self.config.get(
            "feature_count"
        )

        actual_features = getattr(
            self.model,
            "n_features_in_",
            None,
        )

        logger.info(
            "Configured feature count: %s",
            expected_features,
        )

        logger.info(
            "Model feature count: %s",
            actual_features,
        )

        if (
            expected_features is not None
            and actual_features is not None
            and int(expected_features)
            != int(actual_features)
        ):
            raise ValueError(
                "CatBoost feature-count mismatch: "
                f"config={expected_features}, "
                f"model={actual_features}"
            )

        # --------------------------------------------------------
        # Class validation
        # --------------------------------------------------------

        configured_classes = self.config.get(
            "classes",
            [],
        )

        encoder_classes = list(
            self.label_encoder.classes_
        )

        logger.info(
            "Configured classes: %s",
            configured_classes,
        )

        logger.info(
            "Encoder classes: %s",
            encoder_classes,
        )

        if (
            configured_classes
            and configured_classes != encoder_classes
        ):
            raise ValueError(
                "Configuration classes do not match "
                "label encoder classes."
            )

        # --------------------------------------------------------
        # Feature-name validation
        # --------------------------------------------------------

        feature_names = self.config.get(
            "feature_names",
            [],
        )

        if not feature_names:
            logger.warning(
                "No feature_names found in CatBoost config."
            )

        logger.info(
            "CatBoost artifact validation passed."
        )

    # ============================================================
    # STATUS
    # ============================================================

    def is_loaded(self) -> bool:
        """Return whether the CatBoost service is ready."""

        return self._loaded

    # ============================================================
    # FEATURE ENGINEERING
    # ============================================================

    def build_features(
        self,
        values: Dict[str, float],
        formation: str,
    ) -> np.ndarray:
        """
        Build the 17-feature vector used by the research pipeline.

        Feature layout:

            1-6:
                depth
                porosity
                permeability
                API
                viscosity
                oil saturation

            7-12:
                uncertainty spans

            13-14:
                log permeability
                log viscosity

            15-17:
                formation one-hot
        """

        # --------------------------------------------------------
        # Required inputs
        # --------------------------------------------------------

        depth = float(
            values["depth_ft"]
        )

        porosity = float(
            values["porosity_pct"]
        )

        permeability = float(
            values["perm_md"]
        )

        api = float(
            values["api"]
        )

        viscosity = float(
            values["visc_cp"]
        )

        oil_saturation = float(
            values["so_pct"]
        )

        # --------------------------------------------------------
        # Point-estimate spans
        #
        # Current dashboard provides point values rather than
        # uncertainty ranges, so spans are zero.
        # --------------------------------------------------------

        depth_span = 0.0
        porosity_span = 0.0
        permeability_span = 0.0
        api_span = 0.0
        viscosity_span = 0.0
        oil_saturation_span = 0.0

        # --------------------------------------------------------
        # Log features
        # --------------------------------------------------------

        eps = 1e-6

        log_permeability = np.log10(
            max(permeability, 0.0) + eps
        )

        log_viscosity = np.log10(
            max(viscosity, 0.0) + eps
        )

        # --------------------------------------------------------
        # Formation encoding
        # --------------------------------------------------------

        formation_names = [
            "Sandstone",
            "Carbonates",
            "Unconsolidated sands",
        ]

        formation_onehot = [
            1.0 if formation == name else 0.0
            for name in formation_names
        ]

        # --------------------------------------------------------
        # Final feature vector
        # --------------------------------------------------------

        features = np.array(
            [
                depth,
                porosity,
                permeability,
                api,
                viscosity,
                oil_saturation,

                depth_span,
                porosity_span,
                permeability_span,
                api_span,
                viscosity_span,
                oil_saturation_span,

                log_permeability,
                log_viscosity,

                *formation_onehot,
            ],
            dtype=float,
        )

        # --------------------------------------------------------
        # Validate count
        # --------------------------------------------------------

        expected = self.config.get(
            "feature_count",
            len(features),
        )

        if len(features) != int(expected):
            raise ValueError(
                "Feature engineering produced "
                f"{len(features)} features, "
                f"but model expects {expected}."
            )

        return features

    # ============================================================
    # PREDICT
    # ============================================================

    def predict(
        self,
        features: np.ndarray,
        top_n: int = 3,
    ) -> Tuple[
        np.ndarray,
        List[Tuple[str, float]],
    ]:
        """
        Run CatBoost probability inference.

        Returns:
            probabilities,
            ranked Top-N predictions
        """

        if not self._loaded:
            raise RuntimeError(
                "ModelService is not loaded."
            )

        features = np.asarray(
            features,
            dtype=float,
        ).reshape(1, -1)

        expected = self.config.get(
            "feature_count"
        )

        if (
            expected is not None
            and features.shape[1]
            != int(expected)
        ):
            raise ValueError(
                "Feature mismatch: "
                f"expected {expected}, "
                f"received {features.shape[1]}."
            )

        # --------------------------------------------------------
        # CatBoost probability prediction
        # --------------------------------------------------------

        probabilities = self.model.predict_proba(
            features
        )

        probabilities = np.asarray(
            probabilities,
            dtype=float,
        )[0]

        # --------------------------------------------------------
        # CatBoost class IDs
        # --------------------------------------------------------

        model_classes = np.asarray(
            self.model.classes_
        )

        # --------------------------------------------------------
        # Rank
        # --------------------------------------------------------

        ranking_indices = np.argsort(
            probabilities
        )[::-1][:top_n]

        top_predictions: List[
            Tuple[str, float]
        ] = []

        for index in ranking_indices:

            class_id = model_classes[index]

            label = self.label_encoder.inverse_transform(
                [class_id]
            )[0]

            probability = float(
                probabilities[index]
            )

            top_predictions.append(
                (
                    str(label),
                    probability,
                )
            )

        return (
            probabilities,
            top_predictions,
        )

    # ============================================================
    # HIGH-LEVEL API
    # ============================================================

    def predict_from_inputs(
        self,
        values: Dict[str, float],
        formation: str,
        top_n: int = 3,
    ) -> Dict[str, Any]:
        """
        Build features and return CatBoost predictions.
        """

        features = self.build_features(
            values=values,
            formation=formation,
        )

        probabilities, top_predictions = (
            self.predict(
                features=features,
                top_n=top_n,
            )
        )

        return {
            "probabilities": probabilities,
            "top_predictions": top_predictions,
            "features": features,
        }

    # ============================================================
    # MODEL INFO
    # ============================================================

    def get_model_info(
        self,
    ) -> Dict[str, Any]:
        """Return model metadata for UI/logging."""

        if not self._loaded:
            return {
                "loaded": False,
                "error": "Model not loaded",
            }

        return {
            "loaded": True,

            "model_name": self.config.get(
                "model_name",
                "EOR CatBoost",
            ),

            "version": self.config.get(
                "version",
                "1.0.0",
            ),

            "model_type": type(
                self.model
            ).__name__,

            "algorithm": self.config.get(
                "algorithm",
                "CatBoostClassifier",
            ),

            "feature_count": self.config.get(
                "feature_count"
            ),

            "classes": list(
                self.label_encoder.classes_
            ),

            "class_count": len(
                self.label_encoder.classes_
            ),

            "catboost": self.config.get(
                "catboost",
                {},
            ),
        }