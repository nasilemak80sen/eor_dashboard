"""
Test suite for EOR Atlas
Phase 3B & Phase 4 integration tests
"""

import pytest
import numpy as np
from typing import Dict

from src.config import FEATURES, EOR_TECHNIQUES
from src.model_service import ModelService
from src.ml_prediction import PredictionResult, ConfidenceLevel, EngineeringAssessment
from src.engineering_rules import EngineeringRuleEngine
from src.decision_engine import DecisionEngine


# Test fixtures
@pytest.fixture
def sample_reservoir() -> Dict:
    """Sample reservoir data for testing"""
    return {
        "Depth": 5000,
        "Porosity": 20,
        "Permeability": 100,
        "API": 32,
        "Viscosity": 10,
        "Oil_Saturation": 65,
        "Formation": "Sandstone",
        "Temperature": 150,
        "Clay_Content": 15,
        "Water_Saturation": 35,
        "Net_to_Gross": 0.7,
        "Trap_Type": "Structural",
        "Lithology": "Sandstone",
        "Underburden": "Good",
        "Seal_Quality": "Good",
        "Faulting": 10,
        "Dip": 15
    }


@pytest.fixture
def high_viscosity_reservoir() -> Dict:
    """High viscosity (steam candidate)"""
    res = {
        "Depth": 3000,
        "Porosity": 20,
        "Permeability": 100,
        "API": 22,
        "Viscosity": 80,
        "Oil_Saturation": 65,
        "Formation": "Sandstone",
        "Temperature": 140,
        "Clay_Content": 15,
        "Water_Saturation": 35,
        "Net_to_Gross": 0.7,
        "Trap_Type": "Structural",
        "Lithology": "Sandstone",
        "Underburden": "Good",
        "Seal_Quality": "Good",
        "Faulting": 10,
        "Dip": 15
    }
    return res


@pytest.fixture
def deep_reservoir() -> Dict:
    """Deep reservoir (CO2 candidate)"""
    res = {
        "Depth": 8000,
        "Porosity": 18,
        "Permeability": 150,
        "API": 38,
        "Viscosity": 2,
        "Oil_Saturation": 70,
        "Formation": "Carbonate",
        "Temperature": 200,
        "Clay_Content": 5,
        "Water_Saturation": 30,
        "Net_to_Gross": 0.8,
        "Trap_Type": "Structural",
        "Lithology": "Limestone",
        "Underburden": "Good",
        "Seal_Quality": "Excellent",
        "Faulting": 5,
        "Dip": 20
    }
    return res


# Test PredictionResult
class TestPredictionResult:
    """Tests for PredictionResult dataclass"""
    
    def test_create_valid_result(self):
        """Test creating a valid prediction result"""
        result = PredictionResult(
            technique="Miscible HC",
            confidence=0.65,
            confidence_level="🟡 MODERATE",
            candidates=[("Miscible HC", 0.65), ("Steam", 0.25)]
        )
        
        assert result.technique == "Miscible HC"
        assert result.confidence == 0.65
        assert result.is_valid
    
    def test_confidence_level_classification(self):
        """Test confidence level classification"""
        high = PredictionResult(
            technique="Test",
            confidence=0.75,
            confidence_level=""
        )
        assert "HIGH" in high.confidence_level
        
        moderate = PredictionResult(
            technique="Test",
            confidence=0.65,
            confidence_level=""
        )
        assert "MODERATE" in moderate.confidence_level
        
        low = PredictionResult(
            technique="Test",
            confidence=0.45,
            confidence_level=""
        )
        assert "LOW" in low.confidence_level
    
    def test_confidence_percentage(self):
        """Test confidence formatting"""
        result = PredictionResult(
            technique="Test",
            confidence=0.456,
            confidence_level=""
        )
        assert result.confidence_percentage == "45.6%"
    
    def test_should_warn_low_confidence(self):
        """Test low confidence warning logic"""
        high_conf = PredictionResult(
            technique="Test",
            confidence=0.65,
            confidence_level=""
        )
        assert not high_conf.should_warn_low_confidence()
        
        low_conf = PredictionResult(
            technique="Test",
            confidence=0.45,
            confidence_level=""
        )
        assert low_conf.should_warn_low_confidence()


# Test EngineeringRuleEngine
class TestEngineeringRuleEngine:
    """Tests for engineering rule engine"""
    
    def test_assess_miscible_hc(self, sample_reservoir):
        """Test Miscible HC assessment"""
        engine = EngineeringRuleEngine()
        assessment = engine._assess_miscible_hc(sample_reservoir)
        
        assert assessment.technique == "Miscible HC"
        assert 0.0 <= assessment.compatibility_score <= 1.0
        assert assessment.compatibility_level in ["HIGH", "MODERATE", "LOW"]
    
    def test_assess_steam_high_viscosity(self, high_viscosity_reservoir):
        """Test Steam assessment with high viscosity"""
        engine = EngineeringRuleEngine()
        assessment = engine._assess_steam(high_viscosity_reservoir)
        
        # High viscosity should favor steam
        assert assessment.compatibility_score > 0.5
        assert any("viscosity" in c.lower() for c in assessment.satisfied_criteria)
    
    def test_assess_miscible_co2_deep(self, deep_reservoir):
        """Test CO2 assessment with deep reservoir"""
        engine = EngineeringRuleEngine()
        assessment = engine._assess_miscible_co2(deep_reservoir)
        
        # Deep reservoir should favor CO2
        assert assessment.compatibility_score > 0.4
        assert any("depth" in c.lower() for c in assessment.satisfied_criteria)
    
    def test_ranking_all_techniques(self, sample_reservoir):
        """Test ranking all EOR techniques"""
        engine = EngineeringRuleEngine()
        rankings = engine.rank_techniques(sample_reservoir)
        
        # Should return multiple techniques
        assert len(rankings) > 0
        
        # Should be sorted by score (descending)
        scores = [a.compatibility_score for _, a in rankings]
        assert scores == sorted(scores, reverse=True)


# Test DecisionEngine
class TestDecisionEngine:
    """Tests for decision engine"""
    
    def test_assess_and_decide(self, sample_reservoir):
        """Test integrated assessment and decision"""
        engine = DecisionEngine()
        
        # Create mock ML result
        ml_result = PredictionResult(
            technique="Miscible HC",
            confidence=0.65,
            confidence_level="🟡 MODERATE",
            candidates=[("Miscible HC", 0.65), ("Steam", 0.25)]
        )
        
        assessment = engine.assess_and_decide(ml_result, sample_reservoir)
        
        assert assessment.ml_result.technique == "Miscible HC"
        assert assessment.engineering_assessment is not None
        assert assessment.recommendation_level in ["🟢", "🟡", "🔴"]
        assert len(assessment.reasoning) > 0
    
    def test_rank_all_candidates(self, sample_reservoir):
        """Test ranking all candidates"""
        engine = DecisionEngine()
        
        ml_result = PredictionResult(
            technique="Miscible HC",
            confidence=0.65,
            confidence_level="🟡 MODERATE",
            candidates=[
                ("Miscible HC", 0.65),
                ("Steam", 0.25),
                ("Miscible CO2", 0.08),
                ("Polymer", 0.02)
            ]
        )
        
        ranked = engine.rank_all_candidates(ml_result, sample_reservoir)
        
        # Should have same number as candidates
        assert len(ranked) == len(ml_result.candidates)
        
        # Should be sorted by priority
        priorities = [a.get_decision_priority() for a in ranked]
        assert priorities == sorted(priorities)
    
    def test_sensitivity_analysis(self, sample_reservoir):
        """Test sensitivity analysis"""
        engine = DecisionEngine()
        
        ml_result = PredictionResult(
            technique="Miscible HC",
            confidence=0.65,
            confidence_level="🟡 MODERATE",
            candidates=[("Miscible HC", 0.65)]
        )
        
        analysis = engine.sensitivity_analysis(
            ml_result,
            sample_reservoir,
            parameter="Viscosity",
            range_low=1,
            range_high=100,
            steps=5
        )
        
        assert len(analysis) == 5
        assert all(r["parameter_name"] == "Viscosity" for r in analysis)


# Test integration
class TestIntegration:
    """End-to-end integration tests"""
    
    def test_complete_workflow(self, sample_reservoir):
        """Test complete ML → Decision workflow"""
        
        # Initialize services
        model_service = ModelService()
        decision_engine = DecisionEngine()
        
        if not model_service.is_model_loaded():
            pytest.skip("Model not available for integration test")
        
        # Run ML prediction
        ml_result = model_service.predict(sample_reservoir)
        
        if ml_result.is_valid:
            # Run decision engine
            assessment = decision_engine.assess_and_decide(ml_result, sample_reservoir)
            
            # Verify output
            assert assessment.recommendation_level in ["🟢", "🟡", "🔴"]
            assert len(assessment.reasoning) > 0
    
    def test_error_handling(self):
        """Test error handling in services"""
        
        model_service = ModelService()
        
        # Invalid input (missing features)
        invalid_reservoir = {"Depth": 5000}
        
        result = model_service.predict(invalid_reservoir)
        assert not result.is_valid
        assert result.error_message is not None


# Test edge cases
class TestEdgeCases:
    """Test edge cases and boundary conditions"""
    
    def test_extremely_high_viscosity(self, sample_reservoir):
        """Test with extremely high viscosity"""
        sample_reservoir["Viscosity"] = 500
        
        engine = EngineeringRuleEngine()
        assessment = engine._assess_steam(sample_reservoir)
        
        # Should recognize steam is suitable
        assert assessment.compatibility_score > 0.3
    
    def test_extremely_low_confidence(self):
        """Test with extremely low confidence"""
        result = PredictionResult(
            technique="Test",
            confidence=0.01,
            confidence_level=""
        )
        
        assert result.should_warn_low_confidence()
        assert "LOW" in result.confidence_level
    
    def test_confidence_boundary_at_0_6(self):
        """Test confidence boundary at 60%"""
        result_just_low = PredictionResult(
            technique="Test",
            confidence=0.599,
            confidence_level=""
        )
        assert "LOW" in result_just_low.confidence_level
        
        result_just_high = PredictionResult(
            technique="Test",
            confidence=0.60,
            confidence_level=""
        )
        assert "MODERATE" in result_just_high.confidence_level


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
