"""
EOR Atlas ML Model Service.

Responsible for:
- loading model artifacts
- validating model schema
- building features
- running prediction
- ranking candidates
- assigning confidence level
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from src.config.settings import settings
from src.ml.feature_builder import FEATURE_COUNT, FEATURE_NAMES, build_features
from src.ml.prediction import (
    PredictionCandidate,
    PredictionResult,
)
from src.ml.validators import validate_feature_matrix, validate_reservoir_input


class ModelService:
    """Production-facing interface to the EOR ML model."""

    def __init__(
        self,
        model_path: Path | None = None,
        encoder_path: Path | None = None,
        config_path: Path | None = None,
    ) -> None:

        self.model_path = (
            model_path
            or settings.model_path
        )

        self.encoder_path = (
            encoder_path
            or settings.label_encoder_path
        )

        self.config_path = (
            config_path
            or settings.config_path
        )

        self.model = None

        self.encoder = None

        self.config: dict[str, Any] = {}

        self._load_artifacts()

        self._validate_schema()

    # ====================================================================
    # ARTIFACT LOADING
    # ====================================================================

    def _load_artifacts(self) -> None:

        self._validate_artifact_path(
            self.model_path,
            "model",
        )

        self._validate_artifact_path(
            self.encoder_path,
            "label encoder",
        )

        self._validate_artifact_path(
            self.config_path,
            "model configuration",
        )

        try:

            self.model = joblib.load(
                self.model_path
            )

        except Exception as exc:

            raise RuntimeError(
                "Unable to load CatBoost model.\n"
                f"Path: {self.model_path}\n"
                f"Error: {exc}"
            ) from exc

        try:

            self.encoder = joblib.load(
                self.encoder_path
            )

        except Exception as exc:

            raise RuntimeError(
                "Unable to load label encoder.\n"
                f"Path: {self.encoder_path}\n"
                f"Error: {exc}"
            ) from exc

        try:

            with self.config_path.open(
                "r",
                encoding="utf-8",
            ) as file:

                self.config = json.load(file)

        except Exception as exc:

            raise RuntimeError(
                "Unable to load model configuration.\n"
                f"Path: {self.config_path}\n"
                f"Error: {exc}"
            ) from exc

    # ====================================================================
    # ARTIFACT VALIDATION
    # ====================================================================

    @staticmethod
    def _validate_artifact_path(
        path: Path,
        artifact_name: str,
    ) -> None:

        if not path.exists():

            raise FileNotFoundError(
                f"{artifact_name.title()} artifact "
                f"not found:\n{path}"
            )

        if not path.is_file():

            raise FileNotFoundError(
                f"{artifact_name.title()} path is not a file:\n"
                f"{path}"
            )

    # ====================================================================
    # SCHEMA VALIDATION
    # ====================================================================

    def _validate_schema(self) -> None:

        if self.model is None or self.encoder is None:
            raise RuntimeError("Model artifacts have not been loaded.")

        expected_features = self.config.get(
            "feature_names",
            [],
        )

        builder_features = FEATURE_NAMES

        if expected_features != builder_features:

            raise RuntimeError(
                "ML feature schema mismatch.\n\n"
                f"Model config:\n{expected_features}\n\n"
                f"Feature builder:\n{builder_features}"
            )

        model_features = getattr(self.model, "feature_names_", expected_features)
        if list(model_features) != builder_features:
            raise RuntimeError(
                "Loaded model feature schema does not match feature builder."
            )

        if len(expected_features) != FEATURE_COUNT:

            raise RuntimeError(
                "Unexpected model feature count: "
                f"{len(expected_features)}"
            )

        expected_classes = self.config.get(
            "classes",
            [],
        )

        if not expected_classes:

            raise RuntimeError(
                "Model configuration does not "
                "contain class definitions."
            )

        if len(expected_classes) != len(
            self.encoder.classes_
        ):

            raise RuntimeError(
                "Model class count does not match "
                "encoder class count."
            )

    def is_loaded(self) -> bool:
        """Return whether model artifacts were loaded successfully."""

        return self.model is not None and self.encoder is not None

    def get_model_info(self) -> dict[str, Any]:
        """Return serializable model metadata for diagnostics."""

        if self.encoder is None:
            raise RuntimeError("Label encoder has not been loaded.")

        return {
            "model_name": self.config.get("model_name", settings.model_name),
            "model_version": self.config.get("version", settings.model_version),
            "feature_count": FEATURE_COUNT,
            "classes": list(self.encoder.classes_),
        }

    # ====================================================================
    # PREDICTION
    # ====================================================================

    def predict(
        self,
        reservoir: dict[str, Any],
    ) -> PredictionResult:

        if self.model is None or self.encoder is None:
            raise RuntimeError("Model artifacts have not been loaded.")

        validate_reservoir_input(reservoir)
        features = build_features(reservoir)
        validate_feature_matrix(features)

        # ---------------------------------------------------------------
        # Validate against model schema
        # ---------------------------------------------------------------

        self._validate_model_input(
            features
        )

        # ---------------------------------------------------------------
        # Predict encoded class
        # ---------------------------------------------------------------

        encoded_prediction = self.model.predict(
            features
        )

        predicted_code = int(
            np.asarray(encoded_prediction).reshape(-1)[0]
        )

        # ---------------------------------------------------------------
        # Decode class
        # ---------------------------------------------------------------

        technique = str(
            self.encoder.inverse_transform(
                [predicted_code]
            )[0]
        )

        # ---------------------------------------------------------------
        # Probabilities
        # ---------------------------------------------------------------

        probabilities = self.model.predict_proba(
            features
        )[0]

        # ---------------------------------------------------------------
        # Build candidates
        # ---------------------------------------------------------------

        candidates = self._build_candidates(
            probabilities
        )

        confidence = candidates[0].probability

        confidence_level = (
            self._classify_confidence(
                confidence
            )
        )

        warning = None

        if confidence < settings.get_engineering_param(
            "confidence_threshold",
            0.60,
        ):

            warning = (
                "Model confidence is below the "
                "engineering decision threshold. "
                "Validate this result against "
                "engineering screening criteria."
            )

        return PredictionResult(

            technique=technique,

            confidence=confidence,

            confidence_level=confidence_level,

            candidates=tuple(candidates),

            model_name=settings.model_name,

            model_version=settings.model_version,

            feature_count=FEATURE_COUNT,

            success=True,

            warning=warning,
        )

    # ====================================================================
    # CANDIDATE RANKING
    # ====================================================================

    def _build_candidates(
        self,
        probabilities,
    ) -> list[PredictionCandidate]:

        if self.encoder is None:
            raise RuntimeError("Label encoder has not been loaded.")

        class_names = list(
            self.encoder.classes_
        )

        ranked = sorted(

            zip(
                class_names,
                probabilities,
            ),

            key=lambda item: float(item[1]),

            reverse=True,
        )

        candidates = []

        for rank, (
            technique,
            probability,
        ) in enumerate(
            ranked,
            start=1,
        ):

            candidates.append(
                PredictionCandidate(

                    technique=str(
                        technique
                    ),

                    probability=float(
                        probability
                    ),

                    rank=rank,
                )
            )

        return candidates

    # ====================================================================
    # CONFIDENCE
    # ====================================================================

    @staticmethod
    def _classify_confidence(
        confidence: float,
    ) -> str:

        high = settings.get_engineering_param(
            "high_confidence_threshold",
            0.75,
        )

        acceptable = settings.get_engineering_param(
            "confidence_threshold",
            0.60,
        )

        if confidence >= high:

            return "High"

        if confidence >= acceptable:

            return "Moderate"

        return "Low"

    # ====================================================================
    # INPUT VALIDATION
    # ====================================================================

    def _validate_model_input(
        self,
        features: pd.DataFrame,
    ) -> None:

        expected = self.config[
            "feature_names"
        ]

        if list(features.columns) != expected:

            raise ValueError(
                "Model input feature order mismatch."
            )

        if features.shape != (
            1,
            len(expected),
        ):

            raise ValueError(
                "Invalid model input shape: "
                f"{features.shape}"
            )