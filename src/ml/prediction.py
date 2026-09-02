"""Structured prediction results for EOR Atlas."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class PredictionCandidate:
    """One ranked EOR technique candidate."""

    technique: str
    probability: float
    rank: int = 0

    @property
    def probability_percent(self) -> float:
        return self.probability * 100.0


@dataclass(frozen=True)
class PredictionResult:
    """Complete result returned by ModelService."""

    technique: str
    confidence: float
    confidence_level: str
    candidates: tuple[PredictionCandidate, ...]
    model_name: str
    model_version: str
    feature_count: int
    success: bool = True
    warning: Optional[str] = None

    @property
    def confidence_percent(self) -> float:
        return self.confidence * 100.0

    @property
    def requires_engineering_review(self) -> bool:
        return self.confidence < 0.60

    @property
    def top_candidate(self) -> PredictionCandidate:
        return self.candidates[0]

    @property
    def top_candidates(self) -> tuple[PredictionCandidate, ...]:
        return self.candidates[:3]

    def top_n(self, n: int = 3) -> tuple[PredictionCandidate, ...]:
        return self.candidates[:n]
