"""
Decision Engine: Phase 4
Reconciles ML predictions with engineering assessments
Produces final recommendation
"""

import logging
from typing import Dict, List, Tuple
from dataclasses import dataclass

from config import DECISION_MATRIX
from ml_prediction import (
    PredictionResult,
    EngineeringAssessment,
    IntegratedAssessment,
    ConfidenceLevel
)
from engineering_rules import EngineeringRuleEngine

logger = logging.getLogger(__name__)


class DecisionEngine:
    """
    Phase 4: Decision Engine
    
    Combines:
    - ML screening result (confidence + candidates)
    - Engineering assessment (compatibility)
    
    Produces:
    - Integrated recommendation
    - Explanation
    - Ranked candidate list
    """
    
    def __init__(self):
        """Initialize decision engine"""
        self.engineering_engine = EngineeringRuleEngine()
        self.logger = logging.getLogger(__name__)
    
    def assess_and_decide(
        self,
        ml_result: PredictionResult,
        reservoir: Dict
    ) -> IntegratedAssessment:
        """
        Full assessment and decision
        
        Args:
            ml_result: PredictionResult from ModelService
            reservoir: Reservoir data dict
        
        Returns:
            IntegratedAssessment with final recommendation
        """
        
        if not ml_result.is_valid:
            # ML failed - cannot make decision
            return IntegratedAssessment(
                ml_result=ml_result,
                engineering_assessment=EngineeringAssessment(
                    technique="Error",
                    compatibility_score=0.0,
                    compatibility_level="LOW",
                    satisfied_criteria=[],
                    violated_criteria=["ML prediction failed"],
                ),
                recommendation_level="🔴",
                recommendation_text="Unable to assess - ML error",
                reasoning=["ML prediction unavailable"]
            )
        
        # Get engineering assessment for predicted technique
        eng_assessment = self.engineering_engine.assess_technique(
            ml_result.technique,
            reservoir
        )
        
        # Create integrated assessment
        assessment = IntegratedAssessment(
            ml_result=ml_result,
            engineering_assessment=eng_assessment,
            recommendation_level="",
            recommendation_text=""
        )
        
        # Determine recommendation based on decision matrix
        ml_conf = self._classify_ml_confidence(ml_result.confidence)
        eng_conf = eng_assessment.compatibility_level
        
        decision_key = f"{ml_conf.lower()}_{eng_conf.lower()}"
        decision_info = DECISION_MATRIX.get(decision_key)
        
        if decision_info:
            assessment.recommendation_level = decision_info["level"]
            assessment.recommendation_text = decision_info["text"]
        
        # Generate reasoning
        assessment.reasoning = self._generate_reasoning(
            ml_result,
            eng_assessment,
            ml_conf,
            eng_conf
        )
        
        return assessment
    
    def rank_all_candidates(
        self,
        ml_result: PredictionResult,
        reservoir: Dict
    ) -> List[IntegratedAssessment]:
        """
        Rank all candidate techniques
        
        Returns:
            Ranked list of IntegratedAssessments
        """
        
        assessments = []
        
        # For each candidate from ML
        for technique, confidence in ml_result.get_top_candidates(n=9):
            
            # Create temporary result for this candidate
            temp_result = PredictionResult(
                technique=technique,
                confidence=confidence,
                confidence_level=ConfidenceLevel.from_confidence(confidence).value,
                candidates=ml_result.candidates,
                model_name=ml_result.model_name,
                model_version=ml_result.model_version,
            )
            
            # Get engineering assessment
            eng_assessment = self.engineering_engine.assess_technique(
                technique,
                reservoir
            )
            
            # Create integrated assessment
            ml_conf = self._classify_ml_confidence(confidence)
            eng_conf = eng_assessment.compatibility_level
            
            decision_key = f"{ml_conf.lower()}_{eng_conf.lower()}"
            decision_info = DECISION_MATRIX.get(decision_key)
            
            assessment = IntegratedAssessment(
                ml_result=temp_result,
                engineering_assessment=eng_assessment,
                recommendation_level=decision_info.get("level", "🔴") if decision_info else "🔴",
                recommendation_text=decision_info.get("text", "Unknown") if decision_info else "Unknown",
            )
            
            assessment.reasoning = self._generate_reasoning(
                temp_result,
                eng_assessment,
                ml_conf,
                eng_conf
            )
            
            assessments.append(assessment)
        
        # Sort by priority
        assessments.sort(key=lambda x: x.get_decision_priority())
        
        return assessments
    
    def _classify_ml_confidence(self, confidence: float) -> str:
        """Classify ML confidence as 'high', 'moderate', or 'low'"""
        if confidence >= 0.70:
            return "high"
        elif confidence >= 0.60:
            return "moderate"
        else:
            return "low"
    
    def _generate_reasoning(
        self,
        ml_result: PredictionResult,
        eng_assessment: EngineeringAssessment,
        ml_conf: str,
        eng_conf: str
    ) -> List[str]:
        """Generate human-readable reasoning"""
        
        reasoning = []
        
        # ML reasoning
        reasoning.append(
            f"ML Model ({ml_conf} confidence {ml_result.confidence_percentage}): "
            f"Predicts {ml_result.technique}"
        )
        
        # Engineering reasoning
        reasoning.append(
            f"Engineering Assessment ({eng_conf} compatibility): "
            f"{eng_assessment.compatibility_score:.1%} of criteria satisfied"
        )
        
        # Specific satisfied criteria
        if eng_assessment.satisfied_criteria:
            for criterion in eng_assessment.satisfied_criteria[:2]:
                reasoning.append(f"  {criterion}")
        
        # Specific violated criteria
        if eng_assessment.violated_criteria:
            for criterion in eng_assessment.violated_criteria[:2]:
                reasoning.append(f"  {criterion}")
        
        # Warnings
        if eng_assessment.warnings:
            reasoning.append(f"⚠ Warning: {eng_assessment.warnings[0]}")
        
        # Decision logic
        if ml_conf == "high" and eng_conf == "HIGH":
            reasoning.append("✓ Strong agreement between ML and engineering")
        elif ml_conf == "low" or eng_conf == "LOW":
            reasoning.append("⚠ Significant concerns detected - review recommended")
        else:
            reasoning.append("🔄 ML and engineering indicate mixed signals")
        
        return reasoning
    
    def sensitivity_analysis(
        self,
        ml_result: PredictionResult,
        reservoir: Dict,
        parameter: str,
        range_low: float,
        range_high: float,
        steps: int = 5
    ) -> List[Dict]:
        """
        Perform sensitivity analysis on a parameter
        
        Shows how decision changes as parameter varies
        
        Args:
            ml_result: Original ML prediction
            reservoir: Original reservoir data
            parameter: Parameter name to vary
            range_low: Low end of range
            range_high: High end of range
            steps: Number of steps
        
        Returns:
            List of analysis points
        """
        
        results = []
        step_size = (range_high - range_low) / (steps - 1) if steps > 1 else 0
        
        for i in range(steps):
            value = range_low + (i * step_size)
            
            # Create modified reservoir
            modified_reservoir = reservoir.copy()
            modified_reservoir[parameter] = value
            
            # Get engineering assessment
            eng_assessment = self.engineering_engine.assess_technique(
                ml_result.technique,
                modified_reservoir
            )
            
            # Determine recommendation
            ml_conf = self._classify_ml_confidence(ml_result.confidence)
            eng_conf = eng_assessment.compatibility_level
            decision_key = f"{ml_conf.lower()}_{eng_conf.lower()}"
            decision_info = DECISION_MATRIX.get(decision_key, {})
            
            results.append({
                "parameter_value": value,
                "parameter_name": parameter,
                "technique": ml_result.technique,
                "engineering_score": eng_assessment.compatibility_score,
                "recommendation": decision_info.get("text", "Unknown"),
                "recommendation_level": decision_info.get("level", "🔴"),
            })
        
        return results
    
    def get_decision_summary(
        self,
        assessment: IntegratedAssessment
    ) -> str:
        """
        Get concise decision summary
        
        Returns a one-line summary suitable for reports
        """
        
        return (
            f"{assessment.recommendation_level} "
            f"{assessment.ml_result.technique} "
            f"({assessment.ml_result.confidence_percentage} ML, "
            f"{assessment.engineering_assessment.compatibility_score:.0%} Engineering) "
            f"→ {assessment.recommendation_text}"
        )
