"""
Engineering rule engine for EOR screening eligibility.

This module implements deterministic engineering rules that determine
whether a technique is feasible (PASS), conditionally feasible (CONDITIONAL),
or infeasible (FAIL) based on hard engineering constraints.
"""

from typing import Dict, List, Tuple
from enum import Enum
import numpy as np
import pandas as pd


class EligibilityStatus(str, Enum):
    """Eligibility status for EOR technique."""
    PASS = "🟢 PASS"
    CONDITIONAL = "🟡 CONDITIONAL"
    FAIL = "🔴 FAIL"
    INSUFFICIENT_DATA = "⚠️ INSUFFICIENT_DATA"


class EligibilityCriterion:
    """Single eligibility criterion for an EOR technique."""
    
    def __init__(
        self,
        name: str,
        parameter: str,
        condition: str,
        value: float,
        impact: str = "FAIL",
    ):
        """
        Initialize a criterion.
        
        Args:
            name: Human-readable criterion name
            parameter: Parameter to check (depth_ft, api, etc.)
            condition: Condition operator ('gt', 'lt', 'gte', 'lte', 'eq', 'range')
            value: Threshold value (or tuple for range)
            impact: Impact if failed (FAIL or CONDITIONAL)
        """
        self.name = name
        self.parameter = parameter
        self.condition = condition
        self.value = value
        self.impact = impact
    
    def evaluate(self, param_value: float) -> Tuple[bool, str]:
        """
        Evaluate criterion against parameter value.
        
        Args:
            param_value: Value to check
        
        Returns:
            Tuple of (passes, explanation)
        """
        if pd.isna(param_value):
            return False, f"{self.name}: Missing data"
        
        if self.condition == "gt":
            result = param_value > self.value
            exp = f"{param_value:.1f} > {self.value:.1f}"
        elif self.condition == "lt":
            result = param_value < self.value
            exp = f"{param_value:.1f} < {self.value:.1f}"
        elif self.condition == "gte":
            result = param_value >= self.value
            exp = f"{param_value:.1f} ≥ {self.value:.1f}"
        elif self.condition == "lte":
            result = param_value <= self.value
            exp = f"{param_value:.1f} ≤ {self.value:.1f}"
        elif self.condition == "eq":
            result = param_value == self.value
            exp = f"{param_value:.1f} = {self.value:.1f}"
        elif self.condition == "range":
            lower, upper = self.value
            result = lower <= param_value <= upper
            exp = f"{lower:.1f} ≤ {param_value:.1f} ≤ {upper:.1f}"
        else:
            return False, f"Unknown condition: {self.condition}"
        
        return result, exp


class RuleEngine:
    """Evaluates EOR technique eligibility based on engineering rules."""
    
    def __init__(self):
        """Initialize rule engine with default EOR rules."""
        self.rules: Dict[str, List[EligibilityCriterion]] = self._initialize_rules()
    
    @staticmethod
    def _initialize_rules() -> Dict[str, List[EligibilityCriterion]]:
        """
        Initialize engineering rules for EOR techniques.
        
        Based on fundamental EOR technical considerations:
        - Pressure requirements for gas injection
        - Viscosity requirements for various methods
        - API requirements for steam and thermal
        - Formation permeability requirements
        
        Returns:
            Dictionary mapping technique names to criterion lists
        """
        return {
            "CO2 WAG": [
                EligibilityCriterion(
                    "Minimum pressure",
                    "depth_ft",
                    "gt",
                    4500,
                    impact="FAIL",
                ),
                EligibilityCriterion(
                    "Suitable porosity",
                    "porosity_pct",
                    "gte",
                    10,
                    impact="FAIL",
                ),
                EligibilityCriterion(
                    "Suitable permeability",
                    "perm_md",
                    "gte",
                    10,
                    impact="CONDITIONAL",
                ),
                EligibilityCriterion(
                    "Suitable API",
                    "api",
                    "range",
                    (20, 50),
                    impact="CONDITIONAL",
                ),
            ],
            "Polymer": [
                EligibilityCriterion(
                    "Depth limit",
                    "depth_ft",
                    "lt",
                    12000,
                    impact="FAIL",
                ),
                EligibilityCriterion(
                    "Porosity requirement",
                    "porosity_pct",
                    "gte",
                    12,
                    impact="CONDITIONAL",
                ),
                EligibilityCriterion(
                    "Permeability requirement",
                    "perm_md",
                    "gte",
                    20,
                    impact="CONDITIONAL",
                ),
                EligibilityCriterion(
                    "Salinity tolerance",
                    "api",
                    "gte",
                    15,
                    impact="CONDITIONAL",
                ),
            ],
            "ASP": [
                EligibilityCriterion(
                    "Depth limit",
                    "depth_ft",
                    "lt",
                    10000,
                    impact="CONDITIONAL",
                ),
                EligibilityCriterion(
                    "Porosity requirement",
                    "porosity_pct",
                    "gte",
                    12,
                    impact="FAIL",
                ),
                EligibilityCriterion(
                    "Permeability requirement",
                    "perm_md",
                    "gte",
                    25,
                    impact="CONDITIONAL",
                ),
            ],
            "Steam": [
                EligibilityCriterion(
                    "Heavy oil requirement",
                    "api",
                    "lt",
                    25,
                    impact="FAIL",
                ),
                EligibilityCriterion(
                    "Depth limit",
                    "depth_ft",
                    "lt",
                    8000,
                    impact="CONDITIONAL",
                ),
                EligibilityCriterion(
                    "Viscosity requirement",
                    "visc_cp",
                    "gt",
                    2,
                    impact="CONDITIONAL",
                ),
            ],
            "Hot water": [
                EligibilityCriterion(
                    "Viscosity requirement",
                    "visc_cp",
                    "gt",
                    1,
                    impact="CONDITIONAL",
                ),
                EligibilityCriterion(
                    "Depth limit",
                    "depth_ft",
                    "lt",
                    6000,
                    impact="CONDITIONAL",
                ),
            ],
            "Miscible acid gas": [
                EligibilityCriterion(
                    "Pressure requirement",
                    "depth_ft",
                    "gt",
                    4000,
                    impact="FAIL",
                ),
                EligibilityCriterion(
                    "Porosity requirement",
                    "porosity_pct",
                    "gte",
                    8,
                    impact="CONDITIONAL",
                ),
            ],
            "IWAG": [
                EligibilityCriterion(
                    "Porosity requirement",
                    "porosity_pct",
                    "gte",
                    12,
                    impact="CONDITIONAL",
                ),
                EligibilityCriterion(
                    "Permeability requirement",
                    "perm_md",
                    "gte",
                    15,
                    impact="CONDITIONAL",
                ),
            ],
        }
    
    def evaluate_technique(
        self,
        technique: str,
        values: Dict[str, float],
    ) -> Tuple[EligibilityStatus, List[Dict]]:
        """Evaluate technique eligibility based on rules."""
        if technique not in self.rules:
            return (
                EligibilityStatus.INSUFFICIENT_DATA,
                [{"criterion": "Unknown technique", "result": "Unknown", "status": "missing"}],
            )

        criteria = self.rules[technique]
        results = []
        has_fail = False
        has_conditional = False
        has_missing = False

        for criterion in criteria:
            param_value = values.get(criterion.parameter, np.nan)
            if param_value is None or pd.isna(param_value):
                passes = False
                explanation = f"{criterion.name}: Missing data"
                status = "missing"
                has_missing = True
            else:
                passes, explanation = criterion.evaluate(param_value)
                status = "pass" if passes else "fail"
                if not passes:
                    if criterion.impact == "FAIL":
                        has_fail = True
                    elif criterion.impact == "CONDITIONAL":
                        has_conditional = True

            results.append({
                "criterion": criterion.name,
                "parameter": criterion.parameter,
                "value": param_value,
                "passes": passes,
                "status": status,
                "explanation": explanation,
                "impact": criterion.impact,
            })

        if has_missing:
            status = EligibilityStatus.INSUFFICIENT_DATA
        elif has_fail:
            status = EligibilityStatus.FAIL
        elif has_conditional:
            status = EligibilityStatus.CONDITIONAL
        else:
            status = EligibilityStatus.PASS

        return status, results
    
    def evaluate_all(
        self,
        techniques: List[str],
        values: Dict[str, float],
    ) -> Dict[str, Tuple[EligibilityStatus, List[Dict]]]:
        """
        Evaluate eligibility for all techniques.
        
        Args:
            techniques: List of technique names
            values: Input reservoir parameters
        
        Returns:
            Dictionary mapping technique names to (status, results)
        """
        results = {}
        for technique in techniques:
            results[technique] = self.evaluate_technique(technique, values)
        
        return results
    
    def get_eligible_techniques(
        self,
        techniques: List[str],
        values: Dict[str, float],
        include_conditional: bool = True,
    ) -> List[str]:
        """
        Get list of techniques that pass eligibility.
        
        Args:
            techniques: List of technique names
            values: Input reservoir parameters
            include_conditional: If True, include CONDITIONAL status
        
        Returns:
            List of eligible technique names
        """
        eligible = []
        results = self.evaluate_all(techniques, values)
        
        for technique, (status, _) in results.items():
            if status == EligibilityStatus.PASS:
                eligible.append(technique)
            elif include_conditional and status == EligibilityStatus.CONDITIONAL:
                eligible.append(technique)
        
        return eligible
