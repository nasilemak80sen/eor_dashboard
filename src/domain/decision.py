"""Reconcile ML evidence with deterministic engineering eligibility."""

from __future__ import annotations

from typing import Any, Mapping

from src.domain.rule_engine import EligibilityStatus
from src.ml.prediction import PredictionResult


def reconcile_prediction(
    prediction: PredictionResult,
    eligibility: Mapping[str, tuple[EligibilityStatus, list[dict[str, Any]]]],
    fuzzy_scores: Mapping[str, float] | None = None,
) -> dict[str, Any]:
    """Return an engineering-first assessment of an ML prediction."""

    fuzzy_scores = fuzzy_scores or {}
    eligible = {
        technique: status
        for technique, (status, _) in eligibility.items()
        if status in {EligibilityStatus.PASS, EligibilityStatus.CONDITIONAL}
    }

    candidates = []
    for candidate in prediction.candidates:
        status = eligibility.get(candidate.technique, (EligibilityStatus.INSUFFICIENT_DATA, []))[0]
        if status in {EligibilityStatus.PASS, EligibilityStatus.CONDITIONAL}:
            fuzzy_score = float(fuzzy_scores.get(candidate.technique, 0.0))
            combined_score = 0.7 * fuzzy_score + 0.3 * candidate.probability
            candidates.append((combined_score, candidate, status))

    candidates.sort(key=lambda item: item[0], reverse=True)
    selected = candidates[0] if candidates else None

    if selected is None:
        return {
            "status": "REQUIRES ENGINEERING REVIEW",
            "recommendation": "NO_FEASIBLE_METHOD",
            "score": 0.0,
            "reason": "No ML candidate has sufficient deterministic engineering eligibility.",
            "eligible_techniques": sorted(eligible),
            "selected_status": EligibilityStatus.INSUFFICIENT_DATA.value,
        }

    _, candidate, status = selected
    if prediction.requires_engineering_review or status == EligibilityStatus.CONDITIONAL:
        assessment_status = "REQUIRES ENGINEERING REVIEW"
    else:
        assessment_status = "ENGINEERING-COMPATIBLE CANDIDATE"

    return {
        "status": assessment_status,
        "recommendation": candidate.technique,
        "score": selected[0],
        "reason": (
            f"{candidate.technique} is the strongest eligible candidate after "
            "combining fuzzy suitability and ML probability."
        ),
        "eligible_techniques": sorted(eligible),
        "selected_status": status.value,
    }
