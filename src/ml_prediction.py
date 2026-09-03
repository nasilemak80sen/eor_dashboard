"""
Prediction result dataclass and types
This is the contract between ML service and Streamlit UI

Phase 3B: Separates ML internals from UI presentation
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict
from enum import Enum


class ConfidenceLevel(Enum):
    """Confidence level classification"""
    HIGH = "🟢 HIGH"
    MODERATE = "🟡 MODERATE"
    LOW = "🔴 LOW"

    @classmethod
    def from_confidence(cls, confidence: float) -> "ConfidenceLevel":
        """Classify confidence score"""
        if confidence >= 0.70:
            return cls.HIGH
        elif confidence >= 0.60:
            return cls.MODERATE
        else:
            return cls.LOW


@dataclass
class PredictionResult:
    """
    Result of ML prediction for a reservoir.
    
    This dataclass serves as the contract between:
    - ML service (ModelService)
    - UI layer (Streamlit)
    
    The UI should NOT know how the prediction was produced.
    """
    
    # Primary prediction
    technique: str
    confidence: float  # 0.0 to 1.0
    confidence_level: str  # "HIGH", "MODERATE", "LOW"
    
    # Candidate techniques
    candidates: List[Tuple[str, float]] = field(default_factory=list)
    
    # Model metadata
    model_name: str = "EOR CatBoost"
    model_version: str = "1.0.0"
    
    # Engineering assessment (set by engineering service)
    engineering_confidence: Optional[str] = None  # "HIGH", "MODERATE", "LOW"
    engineering_warning: Optional[str] = None
    
    # Feature importance (for explainability)
    feature_importance: Dict[str, float] = field(default_factory=dict)
    
    # Applicable conditions
    applicable_conditions: List[str] = field(default_factory=list)
    cautions: List[str] = field(default_factory=list)
    
    # Error/warning
    error_message: Optional[str] = None
    is_valid: bool = True
    
    def __post_init__(self):
        """Validate and normalize results"""
        # Ensure confidence is in valid range
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be 0-1, got {self.confidence}")
        
        # Set confidence level if not provided
        if not self.confidence_level:
            self.confidence_level = ConfidenceLevel.from_confidence(
                self.confidence
            ).value
        
        # Ensure candidates list has primary technique
        if self.candidates:
            # Verify primary technique is in candidates
            candidate_techniques = [c[0] for c in self.candidates]
            if self.technique not in candidate_techniques:
                self.candidates.insert(0, (self.technique, self.confidence))
    
    @property
    def confidence_percentage(self) -> str:
        """Format confidence as percentage"""
        return f"{self.confidence * 100:.1f}%"
    
    @property
    def display_confidence_level(self) -> str:
        """Emoji + text for display"""
        return self.confidence_level
    
    def get_top_candidates(self, n: int = 3) -> List[Tuple[str, float]]:
        """Get top N candidates"""
        return sorted(
            self.candidates,
            key=lambda x: x[1],
            reverse=True
        )[:n]
    
    def should_warn_low_confidence(self) -> bool:
        """Should UI display warning about low confidence?"""
        return self.confidence < 0.60
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        return {
            "technique": self.technique,
            "confidence": self.confidence,
            "confidence_percentage": self.confidence_percentage,
            "confidence_level": self.confidence_level,
            "candidates": self.candidates,
            "model_name": self.model_name,
            "model_version": self.model_version,
            "engineering_confidence": self.engineering_confidence,
            "engineering_warning": self.engineering_warning,
            "feature_importance": self.feature_importance,
            "applicable_conditions": self.applicable_conditions,
            "cautions": self.cautions,
            "is_valid": self.is_valid,
        }


@dataclass
class EngineeringAssessment:
    """
    Engineering assessment of a predicted EOR technique
    
    Phase 4: Used by engineering rule engine
    """
    
    technique: str
    compatibility_score: float  # 0.0 to 1.0
    compatibility_level: str  # "HIGH", "MODERATE", "LOW"
    
    satisfied_criteria: List[str] = field(default_factory=list)
    violated_criteria: List[str] = field(default_factory=list)
    
    recommendations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    @classmethod
    def from_score(
        cls,
        technique: str,
        score: float,
        satisfied: List[str],
        violated: List[str],
        recommendations: List[str] = None,
        warnings: List[str] = None
    ) -> "EngineeringAssessment":
        """Create from engineering scoring"""
        if score >= 0.70:
            level = "HIGH"
        elif score >= 0.50:
            level = "MODERATE"
        else:
            level = "LOW"
        
        return cls(
            technique=technique,
            compatibility_score=score,
            compatibility_level=level,
            satisfied_criteria=satisfied,
            violated_criteria=violated,
            recommendations=recommendations or [],
            warnings=warnings or [],
        )
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "technique": self.technique,
            "compatibility_score": self.compatibility_score,
            "compatibility_level": self.compatibility_level,
            "satisfied_criteria": self.satisfied_criteria,
            "violated_criteria": self.violated_criteria,
            "recommendations": self.recommendations,
            "warnings": self.warnings,
        }


@dataclass
class IntegratedAssessment:
    """
    Combined ML + Engineering assessment
    
    Phase 4: Final decision-support output
    """
    
    ml_result: PredictionResult
    engineering_assessment: EngineeringAssessment
    
    # Combined decision
    recommendation_level: str  # "🟢", "🟡", "🔴"
    recommendation_text: str
    
    # Explanation
    reasoning: List[str] = field(default_factory=list)
    
    def get_decision_priority(self) -> int:
        """Return priority for sorting (1=highest, 6=lowest)"""
        decision_map = {
            "🟢 Strong candidate": 1,
            "🟡 Candidate": 2,
            "🟡 Review required": 3,
            "🟡 Engineering review recommended": 4,
            "🔴 Engineering conflict": 5,
            "🔴 Weak candidate": 6,
        }
        return decision_map.get(self.recommendation_text, 99)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "ml_result": self.ml_result.to_dict(),
            "engineering_assessment": self.engineering_assessment.to_dict(),
            "recommendation_level": self.recommendation_level,
            "recommendation_text": self.recommendation_text,
            "reasoning": self.reasoning,
        }
