"""
Prediction result structures for EOR Atlas.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class PredictionCandidate:
    """One EOR technique candidate."""

    technique: str

    probability: float

    rank: int

    @property
    def probability_percent(self) -> float:
        """Probability expressed as percentage."""

        return self.probability * 100


@dataclass(frozen=True)
class PredictionResult:
    """Complete ML prediction result."""

    technique: str

    confidence: float

    confidence_level: str

    candidates: tuple[PredictionCandidate, ...]

    model_name: str

    model_version: str

    success: bool = True

    warning: Optional[str] = None

    error: Optional[str] = None

    @property
    def confidence_percent(self) -> float:

        return self.confidence * 100

    @property
    def top_candidates(self) -> tuple[PredictionCandidate, ...]:

        return self.candidates[:3]