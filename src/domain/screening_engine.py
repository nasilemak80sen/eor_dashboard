"""
Main screening orchestration engine.

Coordinates fuzzy logic, engineering rules, ML inference, and decision synthesis.
"""

from typing import Dict, Tuple, List
from dataclasses import dataclass
from enum import Enum

from domain.fuzzy_engine import FuzzyEngine
from domain.rule_engine import RuleEngine, EligibilityStatus
from EORWEBDEV.src.tests.model_service import ModelService
from data.queries import ScreeningRepository, AuditRepository
from utils.validators import InputValidator, ValidationStatus
from utils.logging_config import logger


@dataclass
class ScreeningResult:
    """Complete screening result."""

    # Input metadata
    formation: str
    inputs: Dict

    # Data quality
    data_quality: Dict

    # Engineering eligibility
    eligibility: Dict  # technique -> (status, details)
    rule_trace: Dict

    # Fuzzy suitability
    fuzzy_scores: Dict  # technique -> score
    fuzzy_explanations: Dict  # technique -> (rows, overall_score)

    # ML inference
    ml_probabilities: Dict  # technique -> probability
    ml_top3: List[Tuple[str, float]]

    # Decision synthesis
    recommendation: str
    recommendation_status: str
    recommendation_score: float
    reasoning: Dict

    # Metadata
    mode: str  # 'ENGINEERING' | 'FUZZY' | 'ML' | 'SYNTHESIS'
    assumptions: Dict = None


class ScreeningEngine:
    """Main EOR screening orchestration engine."""
    
    def __init__(
        self,
        fuzzy_engine: FuzzyEngine,
        rule_engine: RuleEngine,
        model_service: ModelService,
        screening_repo: ScreeningRepository = None,
        audit_repo: AuditRepository = None,
    ):
        """
        Initialize screening engine.
        
        Args:
            fuzzy_engine: Fuzzy logic evaluator
            rule_engine: Engineering rule evaluator
            model_service: ML model service
            screening_repo: Optional database repository for persistence
            audit_repo: Optional audit repository
        """
        self.fuzzy_engine = fuzzy_engine
        self.rule_engine = rule_engine
        self.model_service = model_service
        self.screening_repo = screening_repo or ScreeningRepository()
        self.audit_repo = audit_repo or AuditRepository()
    
    def screen(
        self,
        values: Dict[str, float],
        formation: str,
        techniques: List[str],
    ) -> ScreeningResult:
        """Execute complete screening workflow with safety gates and structured traces."""
        logger.info(f"Starting screening for {formation} formation")

        normalized_values = InputValidator.normalize_values(values)

        # Step 1: Validate inputs
        logger.info("Step 1: Validating inputs...")
        data_quality = InputValidator.assess_data_quality(normalized_values)

        assumptions = {
            "rf_eur_estimate": "Unavailable; requires named engineering assumption or workbook mapping",
            "assumption_based_estimate": False,
            "workbook_mapping_status": "not configured",
        }

        if not data_quality["is_valid"]:
            logger.error(f"Input validation failed: {data_quality['validation_errors']}")
            rule_trace = {
                technique: {
                    "status": "INSUFFICIENT_DATA",
                    "criteria": [{"criterion": "input_validation", "status": "missing", "explanation": "Invalid or incomplete evidence"}],
                    "counts": {"pass": 0, "fail": 0, "missing": 1, "conditional": 0},
                }
                for technique in techniques
            }
            result = ScreeningResult(
                formation=formation,
                inputs=normalized_values,
                data_quality=data_quality,
                eligibility={t: (EligibilityStatus.INSUFFICIENT_DATA, [{"criterion": "input_validation", "status": "missing", "explanation": "Invalid or incomplete evidence"}]) for t in techniques},
                rule_trace=rule_trace,
                fuzzy_scores={t: 0.0 for t in techniques},
                fuzzy_explanations={t: ([], 0.0) for t in techniques},
                ml_probabilities={t: 0.0 for t in techniques},
                ml_top3=[],
                recommendation="NO_FEASIBLE_METHOD",
                recommendation_status="INSUFFICIENT DATA",
                recommendation_score=0.0,
                reasoning={
                    "strategy": "No screening run was permitted because the evidence is incomplete or invalid",
                    "pass_techniques": [],
                    "conditional_techniques": [],
                    "rf_eur_estimate": "assumption-based estimate only",
                    "assumptions": assumptions,
                },
                mode="INSUFFICIENT",
                assumptions=assumptions,
            )
            self._persist_screening_result(result, normalized_values)
            return result

        # Step 2: Engineering eligibility
        logger.info("Step 2: Evaluating engineering eligibility...")
        eligibility = self.rule_engine.evaluate_all(techniques, normalized_values)
        rule_trace = {}
        for technique, (status, details) in eligibility.items():
            counts = {"pass": 0, "fail": 0, "missing": 0, "conditional": 0}
            for detail in details:
                bucket = detail.get("status")
                if bucket in counts:
                    counts[bucket] += 1
            rule_trace[technique] = {
                "status": str(status),
                "criteria": details,
                "counts": counts,
            }

        # Step 3: Fuzzy evaluation
        logger.info("Step 3: Evaluating fuzzy suitability...")
        fuzzy_scores = self.fuzzy_engine.evaluate_all(techniques, formation, normalized_values)
        
        # Generate fuzzy explanations for eligible techniques
        fuzzy_explanations = {}
        for technique in techniques:
            try:
                rows, score = self.fuzzy_engine.explain_technique(
                    technique,
                    formation,
                    values,
                )
                fuzzy_explanations[technique] = (rows, score)
            except Exception as e:
                logger.warning(f"Failed to explain {technique}: {e}")
                fuzzy_explanations[technique] = ([], 0.0)
        
        # Step 4: ML inference
        logger.info("Step 4: Executing ML inference...")
        ml_probabilities = {}
        ml_top3 = []
        
        if self.model_service.is_loaded():
            try:
                features = self.model_service.build_features(
                    values,
                    formation,
                    techniques,
                    fuzzy_scores,
                )
                probs, top3 = self.model_service.predict(features)
                
                # Map probabilities to techniques
                for idx, technique in enumerate(techniques):
                    if idx < len(probs):
                        ml_probabilities[technique] = float(probs[idx])
                
                ml_top3 = top3
            except Exception as e:
                logger.error(f"ML inference failed: {e}")
                ml_probabilities = {t: 0.0 for t in techniques}
                ml_top3 = []
        
        # Step 5: Decision synthesis
        logger.info("Step 5: Synthesizing decision...")
        recommendation, rec_status, rec_score, reasoning, mode = self._synthesize_decision(
            techniques,
            eligibility,
            fuzzy_scores,
            ml_probabilities,
        )
        
        result = ScreeningResult(
            formation=formation,
            inputs=normalized_values,
            data_quality=data_quality,
            eligibility=eligibility,
            rule_trace=rule_trace,
            fuzzy_scores=fuzzy_scores,
            fuzzy_explanations=fuzzy_explanations,
            ml_probabilities=ml_probabilities,
            ml_top3=ml_top3,
            recommendation=recommendation,
            recommendation_status=rec_status,
            recommendation_score=rec_score,
            reasoning={
                **reasoning,
                "rf_eur_estimate": "assumption-based estimate only; workbook mapping not configured",
                "assumptions": assumptions,
            },
            mode=mode,
            assumptions=assumptions,
        )

        self._persist_screening_result(result, normalized_values)

        logger.info(f"Screening complete: Recommended {recommendation}")
        return result

    def _persist_screening_result(self, result: ScreeningResult, normalized_values: Dict[str, float]) -> None:
        """Persist the screening attempt and structured rule trace to the database."""
        try:
            screening_record = self.screening_repo.create(
                formation=result.formation,
                depth_ft=normalized_values.get("depth_ft", 0.0),
                porosity_pct=normalized_values.get("porosity_pct", 0.0),
                perm_md=normalized_values.get("perm_md", 0.0),
                api=normalized_values.get("api", 0.0),
                visc_cp=normalized_values.get("visc_cp", 0.0),
                so_pct=normalized_values.get("so_pct", 0.0),
                name=f"{result.formation}-{result.recommendation}",
                status="completed" if result.recommendation_status.upper() != "INSUFFICIENT DATA" else "failed",
                data_quality_status=result.data_quality.get("status", "UNKNOWN"),
                data_readiness_pct=result.data_quality.get("readiness_percentage", 0.0),
                recommended_technique=result.recommendation,
                recommendation_status=result.recommendation_status,
                recommendation_score=result.recommendation_score,
                recommendation_mode=result.mode,
                model_version=(self.model_service.config or {}).get("model_name", "unknown"),
                input_payload=normalized_values,
                rule_trace=result.rule_trace,
                assumptions=result.assumptions,
                workbook_version="not-configured",
                rule_version="default-engineering-rules",
                fuzzy_model_version=(self.model_service.config or {}).get("model_name", "unknown"),
                evidence_summary={
                    "valid": result.data_quality.get("is_valid", False),
                    "recommendation_status": result.recommendation_status,
                    "rule_statuses": {k: v["status"] for k, v in result.rule_trace.items()},
                },
            )
            self.screening_repo.save_eligibility_results(screening_record.id, {
                name: {
                    "status": str(status),
                    "criteria_passed": len([r for r in details if r.get("passes")]),
                    "criteria_total": len(details),
                    "details": details,
                    "rule_trace": result.rule_trace.get(name, {}),
                }
                for name, (status, details) in result.eligibility.items()
            })
            self.screening_repo.save_fuzzy_results(
                screening_record.id,
                result.fuzzy_scores,
                {technique: {"score": score} for technique, score in result.fuzzy_scores.items()},
            )
            self.screening_repo.save_ml_results(
                screening_record.id,
                result.ml_probabilities,
            )
            self.audit_repo.log_event(
                action="SCREENING_COMPLETED",
                object_type="screening_run",
                object_id=screening_record.id,
                details={
                    "formation": result.formation,
                    "recommendation": result.recommendation,
                    "score": float(result.recommendation_score),
                    "mode": result.mode,
                    "assumptions": result.assumptions,
                },
            )
        except Exception as exc:
            logger.warning(f"Database persistence for screening failed: {exc}")
    
    def _synthesize_decision(
        self,
        techniques: List[str],
        eligibility: Dict[str, Tuple[EligibilityStatus, List]],
        fuzzy_scores: Dict[str, float],
        ml_probabilities: Dict[str, float],
    ) -> Tuple[str, str, float, Dict, str]:
        """
        Synthesize final recommendation from all available evidence.
        
        Decision logic:
        1. Get PASS eligible techniques (hard constraints)
        2. Rank by fuzzy suitability
        3. Validate with ML
        4. Select top candidate
        
        Args:
            techniques: List of techniques
            eligibility: Eligibility results
            fuzzy_scores: Fuzzy scores
            ml_probabilities: ML probabilities
        
        Returns:
            Tuple of (recommendation, status, score, reasoning, mode)
        """
        # Filter eligible techniques
        pass_techniques = [
            t
            for t in techniques
            if eligibility[t][0] == EligibilityStatus.PASS
        ]
        
        conditional_techniques = [
            t
            for t in techniques
            if eligibility[t][0] == EligibilityStatus.CONDITIONAL
        ]
        
        # If no PASS techniques, consider CONDITIONAL
        if not pass_techniques:
            pass_techniques = conditional_techniques
        
        # Rank by fuzzy score
        if pass_techniques:
            ranked = sorted(
                pass_techniques,
                key=lambda t: fuzzy_scores.get(t, 0.0),
                reverse=True,
            )
            recommendation = ranked[0]
            fuzzy_score = fuzzy_scores.get(recommendation, 0.0)
            ml_score = ml_probabilities.get(recommendation, 0.0)

            # Combined score: 70% fuzzy + 30% ML
            combined_score = (0.7 * fuzzy_score) + (0.3 * ml_score)

            status_str = "🟢 RECOMMENDED"
            mode = "SYNTHESIS"

            reasoning = {
                "strategy": "Engineering eligibility + Fuzzy suitability + ML validation",
                "pass_techniques": pass_techniques,
                "conditional_techniques": conditional_techniques,
                "fuzzy_score": float(fuzzy_score),
                "ml_score": float(ml_score),
                "combined_score": float(combined_score),
                "rf_eur_estimate": "assumption-based estimate only; workbook mapping not configured",
            }

            return recommendation, status_str, combined_score, reasoning, mode

        # No eligible techniques
        return (
            "NO_FEASIBLE_METHOD",
            "INSUFFICIENT DATA",
            0.0,
            {
                "strategy": "No techniques met engineering requirements or enough evidence was available",
                "pass_techniques": [],
                "conditional_techniques": conditional_techniques,
                "rf_eur_estimate": "assumption-based estimate only; workbook mapping not configured", })
