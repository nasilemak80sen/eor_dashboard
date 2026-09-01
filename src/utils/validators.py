"""
Input validation for EOR Atlas screening.

Implements strict, defensible validation for reservoir screening inputs:
- All required parameters must be present and within valid ranges
- No silent 1.0 defaults; explicit assumptions are required
- Optional parameters are clearly marked
- Validation results include detailed evidence and missing-data flags
"""

from typing import Dict, Tuple, List, Optional
from enum import Enum
import numpy as np


class ValidationStatus(str, Enum):
    """Validation result status."""
    READY = "🟢 READY"
    READY_WITH_LIMITATIONS = "🟡 READY_WITH_LIMITATIONS"
    INSUFFICIENT_DATA = "🔴 INSUFFICIENT_DATA"


class InputValidator:
    """Validates EOR reservoir screening inputs with strict engineering governance."""

    # HARD CONSTRAINTS: Valid ranges for inputs (strictly enforced)
    VALID_RANGES = {
        "depth_ft": (0, 20000),           # Depth in feet
        "porosity_pct": (0, 100),         # Porosity percentage
        "perm_md": (0.001, 100000),       # Permeability in millidarcies (positive only)
        "api": (10, 70),                  # API gravity (oil range)
        "visc_cp": (0.001, 10000),        # Oil viscosity in cP (positive only)
        "so_pct": (0, 100),               # Oil saturation percentage (optional for some techniques)
    }

    # TIER 1: Required parameters - screening cannot proceed without these
    REQUIRED_PARAMS = ["depth_ft", "porosity_pct", "perm_md", "api", "visc_cp"]

    # TIER 2: Optional parameters - used where available but do not block screening
    OPTIONAL_PARAMS = ["so_pct"]

    # Additional engineering safety constraints for API-facing validation
    POSITIVE_ONLY = {"perm_md", "visc_cp"}  # Must be strictly > 0
    PERCENT_FIELDS = {"porosity_pct", "so_pct"}  # Must be [0, 100]
    
    # Approved categorical values
    FORMATION_TYPES = {
        "Sandstone", "Carbonate", "Shale", "Carboniferous", "Unknown"
    }

    @classmethod
    def is_missing_value(cls, value):
        """Return True for missing or null-like values."""
        if value is None:
            return True
        try:
            return bool(np.isnan(value))
        except TypeError:
            return False

    @classmethod
    def normalize_values(cls, values):
        """Coerce input values to numeric floats where possible."""
        normalized = {}
        for key, value in (values or {}).items():
            if value is None or value == "":
                normalized[key] = np.nan
                continue
            try:
                normalized[key] = float(value)
            except (TypeError, ValueError):
                normalized[key] = np.nan
        return normalized
    
    @classmethod
    def validate_single_input(
        cls,
        param_name: str,
        value: float,
        is_required: bool = True,
    ) -> Tuple[bool, str]:
        """
        Validate a single input parameter with strict range checking.
        
        Args:
            param_name: Name of the parameter
            value: Value to validate
            is_required: Whether this parameter is required
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if param_name not in cls.VALID_RANGES:
            return False, f"Unknown parameter: {param_name}"

        # For optional parameters: None is acceptable
        if cls.is_missing_value(value):
            if is_required:
                return False, f"{param_name} (REQUIRED): Missing value"
            else:
                return True, ""  # Optional parameter is OK when missing

        # Type coercion
        if isinstance(value, str):
            try:
                value = float(value)
            except ValueError:
                return False, f"{param_name}: Invalid numeric value '{value}'"

        # Strict positivity check
        if param_name in cls.POSITIVE_ONLY and value <= 0:
            return False, f"{param_name}: Must be > 0 (received {value})"

        # Percentage range check
        if param_name in cls.PERCENT_FIELDS and not (0 <= value <= 100):
            return False, f"{param_name}: Must be in [0, 100] (received {value})"

        # General range check
        min_val, max_val = cls.VALID_RANGES[param_name]
        if not (min_val <= value <= max_val):
            return (
                False,
                f"{param_name}: Value {value} outside valid range [{min_val}, {max_val}]",
            )

        return True, ""
    
    @classmethod
    def validate_inputs(
        cls,
        values: Dict[str, float],
        strict_mode: bool = True,
    ) -> Tuple[bool, List[str], List[str]]:
        """
        Validate all screening inputs.
        
        Args:
            values: Input dictionary
            strict_mode: If True, missing optional parameters are reported as warnings
            
        Returns:
            Tuple of (is_valid, error_list, warning_list)
        """
        normalized = cls.normalize_values(values)
        errors = []
        warnings = []

        # Check REQUIRED parameters
        for param in cls.REQUIRED_PARAMS:
            if param not in normalized or cls.is_missing_value(normalized.get(param)):
                errors.append(f"REQUIRED: {param} is missing")
                continue
            
            is_valid, error_msg = cls.validate_single_input(param, normalized[param], is_required=True)
            if not is_valid:
                errors.append(error_msg)

        # Check OPTIONAL parameters (if provided)
        for param in cls.OPTIONAL_PARAMS:
            if param in normalized and not cls.is_missing_value(normalized.get(param)):
                is_valid, error_msg = cls.validate_single_input(param, normalized[param], is_required=False)
                if not is_valid:
                    errors.append(error_msg)
            elif strict_mode:
                warnings.append(f"OPTIONAL: {param} not provided; some techniques may be less suitable")

        # Check for unknown/extra parameters
        all_valid_params = set(cls.REQUIRED_PARAMS + cls.OPTIONAL_PARAMS)
        for param in normalized.keys():
            if param not in all_valid_params:
                warnings.append(f"Unknown parameter '{param}' will be ignored")

        return len(errors) == 0, errors, warnings
    
    @classmethod
    def assess_data_quality(
        cls,
        values: Dict[str, float],
    ) -> Dict:
        """
        Assess data quality and readiness for screening.
        
        Returns structured quality report:
        - status: READY, READY_WITH_LIMITATIONS, or INSUFFICIENT_DATA
        - is_valid: True if all required parameters are present and valid
        - validation_errors: List of errors that block screening
        - validation_warnings: List of non-blocking warnings
        - missing_optional: List of optional parameters not provided
        - readiness_percentage: Fraction of data available
        """
        normalized = cls.normalize_values(values)
        is_valid, errors, warnings = cls.validate_inputs(normalized, strict_mode=True)

        # Count valid required parameters
        valid_required = sum(
            1
            for param in cls.REQUIRED_PARAMS
            if param in normalized and not cls.is_missing_value(normalized.get(param))
        )
        
        # Count valid optional parameters
        valid_optional = sum(
            1
            for param in cls.OPTIONAL_PARAMS
            if param in normalized and not cls.is_missing_value(normalized.get(param))
        )
        
        # Identify missing optional parameters
        missing_optional = [
            param for param in cls.OPTIONAL_PARAMS
            if param not in normalized or cls.is_missing_value(normalized.get(param))
        ]

        # Check for outliers/extreme values
        outliers = []
        for param, value in normalized.items():
            if param in cls.VALID_RANGES:
                if cls.is_missing_value(value):
                    continue
                min_val, max_val = cls.VALID_RANGES[param]
                range_size = max_val - min_val
                if (value < min_val + 0.05 * range_size) or (value > max_val - 0.05 * range_size):
                    outliers.append(param)

        # Determine overall status
        if not is_valid:
            status = ValidationStatus.INSUFFICIENT_DATA
        elif len(outliers) > 2 or missing_optional:
            status = ValidationStatus.READY_WITH_LIMITATIONS
        else:
            status = ValidationStatus.READY

        return {
            "is_valid": is_valid,
            "status": status,
            "validation_errors": errors,
            "validation_warnings": warnings,
            "required_parameters_total": len(cls.REQUIRED_PARAMS),
            "required_parameters_valid": valid_required,
            "optional_parameters_total": len(cls.OPTIONAL_PARAMS),
            "optional_parameters_valid": valid_optional,
            "optional_parameters_missing": missing_optional,
            "outliers": outliers,
            "readiness_percentage": (valid_required / len(cls.REQUIRED_PARAMS)) * 100,
            "can_proceed_to_screening": is_valid,  # Explicit flag for screening eligibility
        }
    
    @classmethod
    def validate_assumption(
        cls,
        assumption_name: str,
        value: Optional[float],
        assumption_type: str = "multiplier",
    ) -> Tuple[bool, str]:
        """
        Validate engineering assumptions (e.g., drive mechanism multiplier, maturity factor).
        
        Assumptions should never be silently defaulted to 1.0; they must be:
        1. Explicitly provided by the engineer
        2. Justified with documentation
        3. Dated and attributed
        
        Args:
            assumption_name: Name of the assumption (e.g., "drive_mech_multiplier")
            value: Provided value (must not be None for assumptions)
            assumption_type: Type of assumption ("multiplier", "factor", "percentage", etc.)
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if cls.is_missing_value(value):
            return False, f"Assumption '{assumption_name}' is REQUIRED and cannot be empty"
        
        # Multipliers typically range [0.5, 2.0]
        if assumption_type == "multiplier":
            if not (0.1 <= value <= 10.0):
                return False, f"Assumption '{assumption_name}' multiplier must be [0.1, 10.0] (received {value})"
        
        # Factors typically range [0.0, 1.0]
        elif assumption_type == "factor":
            if not (0.0 <= value <= 1.0):
                return False, f"Assumption '{assumption_name}' factor must be [0.0, 1.0] (received {value})"
        
        # Percentages must be [0, 100]
        elif assumption_type == "percentage":
            if not (0.0 <= value <= 100.0):
                return False, f"Assumption '{assumption_name}' percentage must be [0, 100] (received {value})"
        
        return True, ""
    
    @classmethod
    def validate_full_assumption_record(
        cls,
        assumption: Dict,
    ) -> Tuple[bool, List[str]]:
        """
        Validate a complete assumption record with documentation.
        
        Required fields:
        - name: Assumption name
        - value: Numeric value
        - type: Type (multiplier, factor, percentage)
        - justification: Why was this value chosen?
        - owner: Engineer responsible
        - date: Date assumption was made
        
        Args:
            assumption: Dictionary containing assumption data
            
        Returns:
            Tuple of (is_valid, error_list)
        """
        errors = []
        required_fields = {"name", "value", "type", "justification", "owner", "date"}
        
        # Check required fields
        for field in required_fields:
            if field not in assumption or not assumption[field]:
                errors.append(f"Assumption missing required field: {field}")
        
        # Validate value if present
        if "value" in assumption and "type" in assumption:
            is_valid, error = cls.validate_assumption(
                assumption.get("name", "unknown"),
                assumption.get("value"),
                assumption.get("type"),
            )
            if not is_valid:
                errors.append(error)
        
        # Validate justification is substantive
        if "justification" in assumption:
            justification = str(assumption["justification"]).strip()
            if len(justification) < 20:
                errors.append("Assumption justification is too brief; provide at least 20 characters")
        
        return len(errors) == 0, errors
