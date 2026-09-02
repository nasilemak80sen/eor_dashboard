"""
Production ML inference service for EOR Atlas.

Supports the exported research KNN classifier.

Architecture:
    dashboard inputs
        ↓
    deterministic feature builder
        ↓
    persisted scaler
        ↓
    persisted KNN model
        ↓
    class probabilities
        ↓
    Top-N EOR techniques

Important:
- This service does NOT decide engineering feasibility.
- This service does NOT replace Excel screening.
- This service does NOT combine ML and fuzzy scores.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import joblib
import numpy as np

from config.settings import settings
from utils.logging_config import logger


class ModelService:
    """Production inference service for the exported EOR ML model."""

    def __init__(self) -> None:
        self.model = None
        self.scaler = None
        self.label_encoder = None
        self.config: Dict[str, Any] = {}
        self._loaded = False

    # ------------------------------------------------------------------
    # MODEL LOADING
    # ------------------------------------------------------------------

    def load(self) -> bool:
        """Load persisted KNN model and supporting artifacts."""

        try:
            logger.info("Loading EOR ML artifacts...")

            model_path = Path(settings.model_path)
            scaler_path = Path(settings.scaler_path)
            label_encoder_path = Path(settings.label_encoder_path)

            logger.info("Model: %s", model_path)
            logger.info("Scaler: %s", scaler_path)
            logger.info("Label encoder: %s", label_encoder_path)

            if not model_path.exists():
                raise FileNotFoundError(
                    f"KNN model not found: {model_path}"
                )

            if not scaler_path.exists():
                raise FileNotFoundError(
                    f"Scaler not found: {scaler_path}"
                )

            if not label_encoder_path.exists():
                raise FileNotFoundError(
                    f"Label encoder not found: {label_encoder_path}"
                )

            self.model = joblib.load(model_path)
            self.scaler = joblib.load(scaler_path)
            self.label_encoder = joblib.load(label_encoder_path)

            # Configuration is optional but strongly recommended.
            self.config = dict(
                getattr(settings, "ml_config", {}) or {}
            )

            self._validate_artifacts()

            self._loaded = True

            logger.info(
                "EOR ML model loaded successfully: %s",
                type(self.model).__name__,
            )

            return True

        except Exception as exc:
            logger.exception(
                "Failed to load EOR ML artifacts: %s",
                exc,
            )

            self._loaded = False
            return False

    # ------------------------------------------------------------------
    # VALIDATION
    # ------------------------------------------------------------------

    def _validate_artifacts(self) -> None:
        """Validate compatibility of persisted ML artifacts."""

        if self.model is None:
            raise ValueError("Model is None.")

        if self.scaler is None:
            raise ValueError("Scaler is None.")

        if self.label_encoder is None:
            raise ValueError("Label encoder is None.")

        # Verify scaler feature count where available.
        scaler_features = getattr(
            self.scaler,
            "n_features_in_",
            None,
        )

        if scaler_features is not None:
            logger.info(
                "Scaler expects %s features.",
                scaler_features,
            )

        # KNN should expose classes_.
        model_classes = getattr(
            self.model,
            "classes_",
            None,
        )

        if model_classes is None:
            raise ValueError(
                "Loaded model does not expose classes_. "
                "Expected a fitted sklearn classifier."
            )

        logger.info(
            "Model classes: %s",
            list(model_classes),
        )

        logger.info(
            "Label encoder classes: %s",
            list(self.label_encoder.classes_),
        )

    # ------------------------------------------------------------------
    # STATUS
    # ------------------------------------------------------------------

    def is_loaded(self) -> bool:
        """Return whether the model is ready for inference."""

        return self._loaded

    # ------------------------------------------------------------------
    # FEATURE ENGINEERING
    # ------------------------------------------------------------------

    def build_features(
        self,
        values: Dict[str, float],
        formation: str,
        techs_all: Sequence[str],
        fuzzy_scores: Optional[Dict[str, float]] = None,
    ) -> np.ndarray:
        """
        Build the exact feature vector expected by the research model.

        IMPORTANT:
        This must remain aligned with the notebook training pipeline.
        """

        fuzzy_scores = fuzzy_scores or {}

        depth_mid = float(values["depth_ft"])
        por_mid = float(values["porosity_pct"])
        perm_mid = float(values["perm_md"])
        api_mid = float(values["api"])
        visc_mid = float(values["visc_cp"])
        so_mid = float(values["so_pct"])

        # --------------------------------------------------------------
        # Uncertainty spans
        # --------------------------------------------------------------
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

        # --------------------------------------------------------------
        # Formation one-hot
        # --------------------------------------------------------------
        formation_names = [
            "Sandstone",
            "Carbonates",
            "Unconsolidated sands",
        ]

        formation_onehot = np.array(
            [
                1.0 if formation == name else 0.0
                for name in formation_names
            ],
            dtype=float,
        )

        # --------------------------------------------------------------
        # Fuzzy features
        # --------------------------------------------------------------
        fuzzy_vector = np.array(
            [
                float(fuzzy_scores.get(technique, 0.0))
                for technique in techs_all
            ],
            dtype=float,
        )

        features = np.concatenate(
            [
                numeric,
                formation_onehot,
                fuzzy_vector,
            ]
        )

        return features

    # ------------------------------------------------------------------
    # PREDICTION
    # ------------------------------------------------------------------

    def predict(
        self,
        features: np.ndarray,
        top_n: int = 3,
    ) -> Tuple[np.ndarray, List[Tuple[str, float]]]:
        """
        Run inference and return probabilities + Top-N predictions.
        """

        if not self._loaded:
            raise RuntimeError(
                "ModelService is not loaded."
            )

        features = np.asarray(
            features,
            dtype=float,
        ).reshape(1, -1)

        expected_features = getattr(
            self.scaler,
            "n_features_in_",
            None,
        )

        if (
            expected_features is not None
            and features.shape[1] != expected_features
        ):
            raise ValueError(
                "Feature mismatch: "
                f"model expects {expected_features}, "
                f"but received {features.shape[1]}."
            )

        # --------------------------------------------------------------
        # Scaling
        # --------------------------------------------------------------
        scaled_features = self.scaler.transform(
            features
        )

        # --------------------------------------------------------------
        # Probability prediction
        # --------------------------------------------------------------
        probabilities = self.model.predict_proba(
            scaled_features
        )[0]

        probabilities = np.asarray(
            probabilities,
            dtype=float,
        )

        # --------------------------------------------------------------
        # IMPORTANT:
        # sklearn probability columns correspond to model.classes_,
        # NOT necessarily label_encoder indices.
        # --------------------------------------------------------------
        model_class_ids = np.asarray(
            self.model.classes_
        )

        ranking_indices = np.argsort(
            probabilities
        )[::-1]

        ranking_indices = ranking_indices[:top_n]

        top_predictions: List[Tuple[str, float]] = []

        for idx in ranking_indices:

            class_id = model_class_ids[idx]

            try:
                label = self.label_encoder.inverse_transform(
                    [class_id]
                )[0]
            except Exception:
                label = str(class_id)

            top_predictions.append(
                (
                    str(label),
                    float(probabilities[idx]),
                )
            )

        return probabilities, top_predictions

    # ------------------------------------------------------------------
    # CONVENIENCE API
    # ------------------------------------------------------------------

    def predict_from_inputs(
        self,
        values: Dict[str, float],
        formation: str,
        techs_all: Sequence[str],
        fuzzy_scores: Optional[Dict[str, float]] = None,
        top_n: int = 3,
    ) -> Dict[str, Any]:
        """
        Build features and predict in one call.
        """

        features = self.build_features(
            values=values,
            formation=formation,
            techs_all=techs_all,
            fuzzy_scores=fuzzy_scores,
        )

        probabilities, top_predictions = self.predict(
            features=features,
            top_n=top_n,
        )

        return {
            "probabilities": probabilities,
            "top_predictions": top_predictions,
            "features": features,
        }

    # ------------------------------------------------------------------
    # MODEL INFORMATION
    # ------------------------------------------------------------------

    def get_model_info(self) -> Dict[str, Any]:
        """Return production model metadata."""

        if not self._loaded:
            return {
                "loaded": False,
                "error": "Model not loaded",
            }

        return {
            "loaded": True,
            "model_type": type(self.model).__name__,
            "model_name": self.config.get(
                "model_name",
                "EOR KNN",
            ),
            "num_classes": len(
                self.label_encoder.classes_
            ),
            "classes": list(
                self.label_encoder.classes_
            ),
            "feature_count": getattr(
                self.scaler,
                "n_features_in_",
                None,
            ),
            "n_neighbors": getattr(
                self.model,
                "n_neighbors",
                None,
            ),
            "weights": getattr(
                self.model,
                "weights",
                None,
            ),
            "metric": getattr(
                self.model,
                "metric",
                None,
            ),
        }