from domain.rule_engine import RuleEngine, EligibilityStatus
from utils.validators import InputValidator, ValidationStatus


def make_valid_values():
    return {
        "depth_ft": 6500,
        "porosity_pct": 22,
        "perm_md": 180,
        "api": 35,
        "visc_cp": 5,
        "so_pct": 60,
    }


def test_validator_rejects_invalid_physical_ranges():
    values = make_valid_values()
    values["depth_ft"] = -100
    valid, errors = InputValidator.validate_inputs(values)
    assert valid is False
    assert any("depth_ft" in error for error in errors)


def test_validator_marks_missing_evidence_as_insufficient_data():
    values = make_valid_values()
    values.pop("perm_md")
    assessment = InputValidator.assess_data_quality(values)
    assert assessment["status"] == ValidationStatus.INSUFFICIENT_DATA
    assert assessment["is_valid"] is False


def test_rule_trace_reports_missing_pass_fail_and_conditional_states():
    engine = RuleEngine()
    status, results = engine.evaluate_technique("CO2 WAG", make_valid_values())
    assert status in {EligibilityStatus.PASS, EligibilityStatus.CONDITIONAL, EligibilityStatus.FAIL}
    assert all("status" in result for result in results)
    assert {result["status"] for result in results}.issubset({"pass", "fail", "conditional", "missing"})


def test_rule_engine_detects_missing_values_as_missing_not_pass():
    engine = RuleEngine()
    values = make_valid_values()
    values["perm_md"] = None
    status, results = engine.evaluate_technique("CO2 WAG", values)
    assert status == EligibilityStatus.INSUFFICIENT_DATA
    assert any(result["status"] == "missing" for result in results)
