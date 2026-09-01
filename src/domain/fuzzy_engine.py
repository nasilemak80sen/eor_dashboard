"""
Fuzzy logic engine for EOR envelope evaluation.

This module handles fuzzy set operations and membership calculations
for reservoir characteristics against EOR technique envelopes.
"""

from typing import Dict, Tuple, List
import numpy as np
import pandas as pd


class FuzzyEngine:
    """Evaluates reservoir parameters against fuzzy EOR envelopes."""
    
    def __init__(self, env: Dict[Tuple[str, str], Dict], alpha: float = 0.30):
        """
        Initialize fuzzy engine.
        
        Args:
            env: Envelope dictionary mapping (technique, formation) to ranges
            alpha: Fuzzification parameter for trapezoidal membership (default: 0.30)
        """
        self.env = env
        self.alpha = alpha
    
    @staticmethod
    def trap_membership(
        x: float,
        lower: float,
        upper: float,
        alpha: float = 0.30,
    ) -> float:
        """
        Calculate trapezoidal membership function.
        
        Implements a trapezoidal fuzzy set with 4 points:
        - left slope: lower - alpha*(upper-lower)
        - bottom-left: lower
        - bottom-right: upper
        - right slope: upper + alpha*(upper-lower)
        
        Args:
            x: Input value
            lower: Lower bound of support
            upper: Upper bound of support
            alpha: Fuzzification parameter
        
        Returns:
            Membership value [0.0, 1.0]
        """
        if pd.isna(x) or pd.isna(lower) or pd.isna(upper):
            return 0.0
        
        if upper == lower:
            return 1.0 if x == lower else 0.0
        
        width = upper - lower
        left = lower - alpha * width
        right = upper + alpha * width
        
        # Outside support
        if x <= left or x >= right:
            return 0.0
        
        # Inside core
        if lower <= x <= upper:
            return 1.0
        
        # Left slope
        if left < x < lower:
            return (x - left) / (lower - left)
        
        # Right slope
        return (right - x) / (right - upper)
    
    def evaluate_technique(
        self,
        technique: str,
        formation: str,
        values: Dict[str, float],
    ) -> Tuple[float, Dict[str, float]]:
        """
        Evaluate suitability of a single EOR technique.
        
        Args:
            technique: EOR technique name
            formation: Formation type
            values: Input reservoir parameters
        
        Returns:
            Tuple of (overall_score, member_dict)
        """
        key = (technique, formation)
        
        if key not in self.env:
            return 0.0, {}
        
        envelope = self.env[key]
        
        # Calculate membership for each parameter
        memberships = {
            "Depth": self.trap_membership(
                values["depth_ft"],
                *envelope["depth"],
                alpha=self.alpha,
            ),
            "Porosity": self.trap_membership(
                values["porosity_pct"],
                *envelope["por"],
                alpha=self.alpha,
            ),
            "Permeability": self.trap_membership(
                values["perm_md"],
                *envelope["perm"],
                alpha=self.alpha,
            ),
            "API": self.trap_membership(
                values["api"],
                *envelope["api"],
                alpha=self.alpha,
            ),
            "Viscosity": self.trap_membership(
                values["visc_cp"],
                *envelope["visc"],
                alpha=self.alpha,
            ),
            "Oil Saturation": self.trap_membership(
                values["so_pct"],
                *envelope["so"],
                alpha=self.alpha,
            ),
        }
        
        # Average membership across all parameters
        overall_score = float(np.mean(list(memberships.values())))
        
        return overall_score, memberships
    
    def evaluate_all(
        self,
        techniques: List[str],
        formation: str,
        values: Dict[str, float],
    ) -> Dict[str, float]:
        """
        Evaluate suitability for all EOR techniques.
        
        Args:
            techniques: List of EOR technique names
            formation: Formation type
            values: Input reservoir parameters
        
        Returns:
            Dictionary mapping technique names to suitability scores
        """
        scores = {}
        for technique in techniques:
            score, _ = self.evaluate_technique(technique, formation, values)
            scores[technique] = score
        
        return scores
    
    def explain_technique(
        self,
        technique: str,
        formation: str,
        values: Dict[str, float],
    ) -> Tuple[List[Dict], float]:
        """
        Generate detailed explanation of technique evaluation.
        
        Args:
            technique: EOR technique name
            formation: Formation type
            values: Input reservoir parameters
        
        Returns:
            Tuple of (explanation_rows, overall_score)
        """
        key = (technique, formation)
        
        if key not in self.env:
            return [], 0.0
        
        envelope = self.env[key]
        
        # Map of parameter display names to keys and ranges
        param_specs = [
            ("Depth (ft)", "depth_ft", envelope["depth"]),
            ("Porosity (%)", "porosity_pct", envelope["por"]),
            ("Permeability (mD)", "perm_md", envelope["perm"]),
            ("API (°API)", "api", envelope["api"]),
            ("Viscosity (cp)", "visc_cp", envelope["visc"]),
            ("Oil Saturation (%)", "so_pct", envelope["so"]),
        ]
        
        explanation_rows = []
        memberships = []
        
        for display_name, param_key, (lower, upper) in param_specs:
            value = values[param_key]
            membership = self.trap_membership(value, lower, upper, alpha=self.alpha)
            memberships.append(membership)
            
            explanation_rows.append({
                "Variable": display_name,
                "Input": value,
                "Range_Min": lower,
                "Range_Max": upper,
                "Membership": float(membership),
            })
        
        overall_score = float(np.mean(memberships))
        
        return explanation_rows, overall_score
