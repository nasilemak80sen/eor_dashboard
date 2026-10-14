from ml.hybrid_feature_builder import FEATURE_NAMES, build_hybrid_features


def test_feature_builder_handles_missing_v3_values():
    values = {
        "depth_ft": 5000,
        "temperature_c": 95,
        "reservoir_pressure": 2500,
        "porosity_pct": 20,
        "perm_md": 100,
        "api": 35,
        "visc_cp": 2,
        "so_pct": 55,
        "sorw_pct": None,
        "produced_gor_scf_stb": None,
    }
    result = build_hybrid_features(values, "Sandstone")
    assert list(result.columns) == FEATURE_NAMES
    assert result.loc[0, "sorw_provided"] == 0.0
    assert result.loc[0, "gor_provided"] == 0.0
    assert result.loc[0, "movable_oil_saturation_pct"] == 0.0


def test_feature_builder_derives_v3_opportunity_features():
    values = {
        "depth_ft": 5000,
        "temperature_c": 95,
        "reservoir_pressure": 2500,
        "porosity_pct": 20,
        "perm_md": 100,
        "api": 35,
        "visc_cp": 2,
        "so_pct": 65,
        "sorw_pct": 35,
        "produced_gor_scf_stb": 750,
    }
    result = build_hybrid_features(values, "Carbonates")
    assert result.loc[0, "sorw_provided"] == 1.0
    assert result.loc[0, "gor_provided"] == 1.0
    assert result.loc[0, "movable_oil_saturation_pct"] == 30.0
    assert result.loc[0, "gor_moderate"] == 1.0
    assert result.loc[0, "formation_carbonates"] == 1.0


def test_feature_builder_keeps_schema_stable():
    values = {
        "depth_ft": 5000,
        "temperature_c": 95,
        "reservoir_pressure": 2500,
        "porosity_pct": 20,
        "perm_md": 100,
        "api": 35,
        "visc_cp": 2,
        "so_pct": 55,
    }
    result = build_hybrid_features(values, "Unconsolidated sands")
    assert result.shape == (1, len(FEATURE_NAMES))
    assert list(result.columns) == FEATURE_NAMES



def test_feature_builder_rejects_missing_required_real_input():
    import pytest

    values = {
        "depth_ft": 5000,
        "temperature_c": 95,
        "reservoir_pressure": 2500,
        "porosity_pct": 20,
        "perm_md": 100,
        "api": 35,
        "visc_cp": 2,
        "so_pct": 55,
    }
    values["reservoir_pressure"] = None
    with pytest.raises(ValueError, match="reservoir_pressure.*missing"):
        build_hybrid_features(values, "Sandstone")


def test_feature_builder_rejects_physically_invalid_real_input():
    import pytest

    values = {
        "depth_ft": 5000,
        "temperature_c": 95,
        "reservoir_pressure": 2500,
        "porosity_pct": 120,
        "perm_md": 100,
        "api": 35,
        "visc_cp": 2,
        "so_pct": 55,
    }
    with pytest.raises(ValueError, match="porosity_pct.*<= 100"):
        build_hybrid_features(values, "Sandstone")


def test_feature_builder_rejects_unfamiliar_categorical_inputs():
    import pytest

    values = {
        "depth_ft": 5000,
        "temperature_c": 95,
        "reservoir_pressure": 2500,
        "porosity_pct": 20,
        "perm_md": 100,
        "api": 35,
        "visc_cp": 2,
        "so_pct": 55,
        "gas_injectivity": "excellent-plus",
    }
    with pytest.raises(ValueError, match="Unrecognized category.*gas_injectivity"):
        build_hybrid_features(values, "Sandstone")


def test_feature_builder_keeps_unfamiliar_formation_explicitly_unclassified():
    values = {
        "depth_ft": 5000,
        "temperature_c": 95,
        "reservoir_pressure": 2500,
        "porosity_pct": 20,
        "perm_md": 100,
        "api": 35,
        "visc_cp": 2,
        "so_pct": 55,
    }
    result = build_hybrid_features(values, "Unknown formation")
    assert result.loc[0, "formation_sandstone"] == 0.0
    assert result.loc[0, "formation_carbonates"] == 0.0
    assert result.loc[0, "formation_unconsolidated_sands"] == 0.0



def test_feature_builder_rejects_invalid_optional_measurement_when_provided():
    import pytest

    values = {
        "depth_ft": 5000,
        "temperature_c": 95,
        "reservoir_pressure": 2500,
        "porosity_pct": 20,
        "perm_md": 100,
        "api": 35,
        "visc_cp": 2,
        "so_pct": 55,
        "produced_gor_scf_stb": -1,
    }
    with pytest.raises(ValueError, match="produced_gor_scf_stb.*>= 0"):
        build_hybrid_features(values, "Sandstone")


def test_feature_builder_rejects_non_finite_core_measurement():
    import pytest

    values = {
        "depth_ft": 5000,
        "temperature_c": float("inf"),
        "reservoir_pressure": 2500,
        "porosity_pct": 20,
        "perm_md": 100,
        "api": 35,
        "visc_cp": 2,
        "so_pct": 55,
    }
    with pytest.raises(ValueError, match="temperature_c.*finite"):
        build_hybrid_features(values, "Sandstone")



def test_feature_builder_preserves_missing_optional_context_with_flags():
    values = {
        "depth_ft": 5000,
        "temperature_c": 95,
        "reservoir_pressure": 2500,
        "porosity_pct": 20,
        "perm_md": 100,
        "api": 35,
        "visc_cp": 2,
        "so_pct": 55,
        "field_maturity": "Mid",
        "gas_reinjectable": "Unknown",
        "wag_ratio": "",
    }
    result = build_hybrid_features(values, "Sandstone")

    assert result.loc[0, "field_maturity_score"] == 0.5
    assert result.loc[0, "field_maturity_provided"] == 1.0
    assert result.loc[0, "gas_reinjectable"] == 0.0
    assert result.loc[0, "gas_reinjectable_provided"] == 0.0
    assert result.loc[0, "wag_ratio_numeric"] == 0.0
    assert result.loc[0, "wag_ratio_provided"] == 0.0
    assert result.loc[0, "salinity_log10"] == -6.0
    assert result.loc[0, "salinity_provided"] == 0.0
    assert result.loc[0, "hardness_provided"] == 0.0
    assert result.loc[0, "net_pay_provided"] == 0.0
    assert result.loc[0, "water_cut_provided"] == 0.0
    assert result.loc[0, "bubble_point_provided"] == 0.0
    assert result.loc[0, "co2_availability_provided"] == 0.0


def test_feature_builder_sets_availability_flags_for_supplied_optional_context():
    values = {
        "depth_ft": 5000,
        "temperature_c": 95,
        "reservoir_pressure": 2500,
        "porosity_pct": 20,
        "perm_md": 100,
        "api": 35,
        "visc_cp": 2,
        "so_pct": 55,
        "salinity_ppm": 50000,
        "hardness_ppm": 300,
        "net_pay_m": 30,
        "water_cut_pct": 60,
        "bubble_point_psi": 1800,
        "co2_availability": "Yes",
        "gas_injectivity": "Good",
        "wag_ratio": "1:1",
    }
    result = build_hybrid_features(values, "Sandstone")

    assert result.loc[0, "salinity_provided"] == 1.0
    assert result.loc[0, "hardness_provided"] == 1.0
    assert result.loc[0, "net_pay_provided"] == 1.0
    assert result.loc[0, "water_cut_provided"] == 1.0
    assert result.loc[0, "bubble_point_provided"] == 1.0
    assert result.loc[0, "co2_availability_provided"] == 1.0
    assert result.loc[0, "gas_injectivity_provided"] == 1.0
    assert result.loc[0, "wag_ratio_provided"] == 1.0
    assert result.loc[0, "wag_ratio_numeric"] == 1.0
