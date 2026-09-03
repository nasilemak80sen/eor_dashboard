"""
Engineering Rule Engine: Phase 4
Encapsulates domain knowledge for EOR technique evaluation
"""

import logging
from typing import Dict, List, Tuple
from dataclasses import dataclass

from config import (
    ENGINEERING_THRESHOLDS,
    EOR_TECHNIQUES,
)
from ml_prediction import EngineeringAssessment

logger = logging.getLogger(__name__)


@dataclass
class ReservoirCriteria:
    """Engineering criteria for a reservoir"""
    
    depth: float
    porosity: float
    permeability: float
    api: float
    viscosity: float
    oil_saturation: float
    formation: str
    temperature: float
    clay_content: float
    water_saturation: float


class EngineeringRuleEngine:
    """
    Phase 4: Engineering rule engine
    
    Evaluates EOR techniques against reservoir criteria
    Returns EngineeringAssessment for each technique
    """
    
    def __init__(self):
        """Initialize rule engine"""
        self.logger = logging.getLogger(__name__)
    
    def assess_technique(
        self,
        technique: str,
        reservoir: Dict
    ) -> EngineeringAssessment:
        """
        Assess one EOR technique for a reservoir
        
        Args:
            technique: EOR technique name
            reservoir: Reservoir data dict
        
        Returns:
            EngineeringAssessment
        """
        
        if technique == "Miscible HC":
            return self._assess_miscible_hc(reservoir)
        elif technique == "Steam":
            return self._assess_steam(reservoir)
        elif technique == "Miscible CO2":
            return self._assess_miscible_co2(reservoir)
        elif technique == "Polymer":
            return self._assess_polymer(reservoir)
        elif technique == "ASP":
            return self._assess_asp(reservoir)
        else:
            return self._assess_generic(technique, reservoir)
    
    def _assess_miscible_hc(self, reservoir: Dict) -> EngineeringAssessment:
        """Evaluate Miscible Hydrocarbon injection"""
        
        satisfied = []
        violated = []
        recommendations = []
        warnings = []
        
        viscosity = reservoir.get("Viscosity", 0)
        api = reservoir.get("API", 0)
        depth = reservoir.get("Depth", 0)
        permeability = reservoir.get("Permeability", 0)
        
        # Rule 1: Viscosity
        if viscosity < 35:
            satisfied.append("✓ Oil viscosity suitable for miscible HC")
        else:
            violated.append("✗ Oil viscosity too high (>35 cp)")
            warnings.append("Consider Steam or Polymer for high viscosity")
        
        # Rule 2: API gravity
        if api >= 30:
            satisfied.append("✓ API gravity favorable for miscibility")
        else:
            violated.append("✗ API gravity too low (<30°)")
            warnings.append("Low API reduces miscibility potential")
        
        # Rule 3: Depth
        if 2000 <= depth <= 12000:
            satisfied.append("✓ Depth within operational window")
        else:
            if depth < 2000:
                violated.append("✗ Reservoir too shallow for cost-effective injection")
            else:
                warnings.append("⚠ Very deep reservoir - assess economic feasibility")
        
        # Rule 4: Permeability
        if permeability > 50:
            satisfied.append("✓ Permeability adequate for HC miscible")
        else:
            warnings.append("⚠ Low permeability may limit injectivity")
        
        # Calculate score
        score = self._calculate_score(len(satisfied), len(violated), len(warnings))
        
        recommendations.append("Conduct slim tube miscibility experiment")
        recommendations.append("Evaluate supply and cost of HC solvent")
        
        return EngineeringAssessment.from_score(
            technique="Miscible HC",
            score=score,
            satisfied=satisfied,
            violated=violated,
            recommendations=recommendations,
            warnings=warnings
        )
    
    def _assess_steam(self, reservoir: Dict) -> EngineeringAssessment:
        """Evaluate Steam injection"""
        
        satisfied = []
        violated = []
        recommendations = []
        warnings = []
        
        viscosity = reservoir.get("Viscosity", 0)
        depth = reservoir.get("Depth", 0)
        api = reservoir.get("API", 0)
        temperature = reservoir.get("Temperature", 0)
        
        # Rule 1: Viscosity (steam loves high viscosity)
        if viscosity > 50:
            satisfied.append("✓ High oil viscosity ideal for steam")
        elif viscosity > 30:
            satisfied.append("✓ Viscosity acceptable for steam")
        else:
            violated.append("✗ Oil viscosity too low for steam recovery")
        
        # Rule 2: Depth (steam economics worsen with depth)
        if depth < 4000:
            satisfied.append("✓ Depth suitable for steam injection economics")
        else:
            violated.append("✗ Reservoir too deep - steam economics poor")
        
        # Rule 3: API gravity
        if api < 35:
            satisfied.append("✓ API gravity compatible with steam")
        else:
            warnings.append("⚠ High API gravity limits steam applicability")
        
        # Rule 4: Reservoir temperature
        if temperature < 100:
            satisfied.append("✓ Low reservoir temp favors steam response")
        else:
            warnings.append("⚠ High reservoir temp reduces steam effect")
        
        # Calculate score
        score = self._calculate_score(len(satisfied), len(violated), len(warnings))
        
        recommendations.append("Assess wellbore capability for steam injection")
        recommendations.append("Evaluate steam generation capacity and cost")
        recommendations.append("Review horizontal well application")
        
        if depth > 3000:
            warnings.append("Deep reservoirs challenge steam economics")
        
        return EngineeringAssessment.from_score(
            technique="Steam",
            score=score,
            satisfied=satisfied,
            violated=violated,
            recommendations=recommendations,
            warnings=warnings
        )
    
    def _assess_miscible_co2(self, reservoir: Dict) -> EngineeringAssessment:
        """Evaluate CO2 Miscible injection"""
        
        satisfied = []
        violated = []
        recommendations = []
        warnings = []
        
        depth = reservoir.get("Depth", 0)
        permeability = reservoir.get("Permeability", 0)
        api = reservoir.get("API", 0)
        viscosity = reservoir.get("Viscosity", 0)
        
        # Rule 1: Depth (CO2 needs depth for miscibility)
        if depth >= 2500:
            satisfied.append("✓ Depth sufficient for CO2 miscibility")
        else:
            violated.append("✗ Reservoir too shallow for CO2 miscibility")
        
        # Rule 2: Permeability
        if permeability > 50:
            satisfied.append("✓ Permeability adequate for CO2 injection")
        else:
            violated.append("✗ Low permeability limits CO2 injectivity")
        
        # Rule 3: API gravity
        if 25 <= api <= 45:
            satisfied.append("✓ API gravity optimal for CO2 recovery")
        else:
            warnings.append("⚠ API gravity outside typical CO2 window")
        
        # Rule 4: Viscosity
        if 0.5 <= viscosity <= 20:
            satisfied.append("✓ Oil viscosity compatible with CO2")
        else:
            warnings.append("⚠ Very low or very high viscosity affects CO2 performance")
        
        # Calculate score
        score = self._calculate_score(len(satisfied), len(violated), len(warnings))
        
        recommendations.append("Confirm minimum miscibility pressure (MMP)")
        recommendations.append("Assess CO2 source and supply reliability")
        recommendations.append("Evaluate seal quality (CO2 can diffuse)")
        
        return EngineeringAssessment.from_score(
            technique="Miscible CO2",
            score=score,
            satisfied=satisfied,
            violated=violated,
            recommendations=recommendations,
            warnings=warnings
        )
    
    def _assess_polymer(self, reservoir: Dict) -> EngineeringAssessment:
        """Evaluate Polymer flooding"""
        
        satisfied = []
        violated = []
        recommendations = []
        warnings = []
        
        permeability = reservoir.get("Permeability", 0)
        temperature = reservoir.get("Temperature", 0)
        salinity = reservoir.get("Water_Saturation", 0)
        porosity = reservoir.get("Porosity", 0)
        
        # Rule 1: Permeability (polymer works in lower perm)
        if 10 <= permeability <= 500:
            satisfied.append("✓ Permeability suitable for polymer")
        else:
            violated.append("✗ Permeability outside polymer range")
        
        # Rule 2: Temperature (polymer degrades at high temp)
        if temperature < 80:
            satisfied.append("✓ Temperature acceptable for polymer")
        else:
            warnings.append("⚠ High temperature may degrade polymer")
        
        # Rule 3: Porosity
        if porosity > 15:
            satisfied.append("✓ Porosity adequate for polymer distribution")
        else:
            warnings.append("⚠ Low porosity may limit polymer sweep")
        
        # Calculate score
        score = self._calculate_score(len(satisfied), len(violated), len(warnings))
        
        recommendations.append("Select appropriate polymer type")
        recommendations.append("Assess formation minerals for adsorption")
        recommendations.append("Test polymer injectivity")
        
        return EngineeringAssessment.from_score(
            technique="Polymer",
            score=score,
            satisfied=satisfied,
            violated=violated,
            recommendations=recommendations,
            warnings=warnings
        )
    
    def _assess_asp(self, reservoir: Dict) -> EngineeringAssessment:
        """Evaluate Alkaline-Surfactant-Polymer"""
        
        satisfied = []
        violated = []
        recommendations = []
        warnings = []
        
        permeability = reservoir.get("Permeability", 0)
        depth = reservoir.get("Depth", 0)
        api = reservoir.get("API", 0)
        
        # Rule 1: Permeability
        if permeability > 50:
            satisfied.append("✓ Permeability suitable for ASP")
        else:
            violated.append("✗ Permeability too low for ASP economics")
        
        # Rule 2: Depth
        if depth > 2500:
            violated.append("✗ Reservoir depth challenges ASP economics")
        else:
            satisfied.append("✓ Depth acceptable for ASP")
        
        # Rule 3: API gravity
        if 20 <= api <= 35:
            satisfied.append("✓ API gravity within ASP window")
        else:
            warnings.append("⚠ API gravity may affect ASP performance")
        
        # Calculate score
        score = self._calculate_score(len(satisfied), len(violated), len(warnings))
        
        recommendations.append("Conduct ASP phase behavior study")
        recommendations.append("Assess polymer and surfactant retention")
        recommendations.append("Evaluate capital and operating costs")
        
        if depth > 3000:
            warnings.append("Deep ASP projects rare due to cost")
        
        return EngineeringAssessment.from_score(
            technique="ASP",
            score=score,
            satisfied=satisfied,
            violated=violated,
            recommendations=recommendations,
            warnings=warnings
        )
    
    def _assess_generic(
        self,
        technique: str,
        reservoir: Dict
    ) -> EngineeringAssessment:
        """Generic assessment for unknown techniques"""
        
        return EngineeringAssessment.from_score(
            technique=technique,
            score=0.5,
            satisfied=["Technique recognized"],
            violated=[],
            recommendations=["Conduct detailed engineering study"],
            warnings=["Limited guidance for this technique"]
        )
    
    def _calculate_score(
        self,
        num_satisfied: int,
        num_violated: int,
        num_warnings: int
    ) -> float:
        """
        Calculate engineering compatibility score (0-1)
        
        Logic:
        - Each satisfied criterion: +0.20 (max 100%)
        - Each violation: -0.30 (can go negative)
        - Each warning: -0.10
        """
        
        score = (
            (num_satisfied * 0.20) -
            (num_violated * 0.30) -
            (num_warnings * 0.10)
        )
        
        # Clamp to 0-1
        return max(0.0, min(1.0, score))
    
    def rank_techniques(
        self,
        reservoir: Dict
    ) -> List[Tuple[str, EngineeringAssessment]]:
        """
        Rank all EOR techniques for a reservoir
        
        Returns:
            List of (technique, assessment) sorted by score
        """
        
        results = []
        
        for technique in EOR_TECHNIQUES:
            if technique not in ["Not Suitable", "Data Missing", "Requires Study"]:
                assessment = self.assess_technique(technique, reservoir)
                results.append((technique, assessment))
        
        # Sort by score (descending)
        results.sort(key=lambda x: x[1].compatibility_score, reverse=True)
        
        return results
