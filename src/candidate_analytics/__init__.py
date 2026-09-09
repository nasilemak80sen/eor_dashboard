"""Standalone Field / Reservoir parameter analytics for EOR Atlas.

This package is intentionally isolated from:
- deterministic EOR screening
- fuzzy suitability scoring
- CatBoost / ML inference
- screening run persistence

It provides portfolio exploration only: filtering, parameter visualization,
and candidate-detail inspection based on the engineering workbook.
"""

from .analysis import CandidateAnalysis
from .repository import CandidateRepository
from .ui import render_field_reservoir_parameters_tab

__all__ = [
    "CandidateAnalysis",
    "CandidateRepository",
    "render_field_reservoir_parameters_tab",
]
