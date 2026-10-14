# EOR Atlas controlled validation and next-generation ML readiness

## Scope

This work validates the live v1 inference path and the Hybrid Intelligence submission flow. It also records external source leads and defines the data gate for a future engineering-aware model. It does not change the deployed v1 model artifact.

## Controlled v1 and dashboard checks

- Load the checked-in CatBoost v1.0.0 artifact and its label encoder.
- Verify the expected 17-feature schema and nine technique labels.
- Use a deterministic synthetic reservoir fixture to assert that inference returns nine finite probabilities in [0, 1], that they sum to one, and that ranking/confidence are internally consistent.
- Verify that malformed ranges, non-finite measurements, and unknown formation categories are rejected before inference.
- Use Streamlit AppTest to open the Hybrid Intelligence page, submit its default controlled fixture, and assert that the real Excel Gate, v1 CatBoost inference, and Decision Fusion return a result. Persistence is stubbed in this UI test so CI does not write business test records into the repository database.

These tests verify execution and invariants, not reservoir-specific appropriateness or field-level predictive accuracy.

## Sparse-class evidence plan

The current OGJ2014 source-reviewed evidence remains below the six-independent-confirmed-fields-per-class gate for HC immiscible, Hot water, Miscible acid gas, and Nitrogen immiscible. The accompanying data/provenance/external_eor_evidence_leads.csv logs potentially useful sources, feature gaps, and explicit counting rules. A lead is not a training row until its technique label, source identity, field/project relationship, feature provenance, and compatibility with the target definition are adjudicated.

In particular:
- Do not count two pools from the same named field as two independent fields.
- Do not label a simulator proposal, laboratory core flood, or unexecuted pilot as a historically implemented field EOR technique.
- Do not coerce broad Chemical/Gas/Thermal family labels into EOR Atlas's nine specific technique labels.
- Keep non-public operating data outside this repository unless its owner explicitly approves use and distribution.

## External data lead: Mendeley family-level dataset

The public dataset “Processed Field-Experience Dataset for Explainable Machine-Learning EOR-Family Screening” (DOI 10.17632/8wfntyb7v4.1; published 2026-09-22; CC BY 4.0) describes 36 source-verified field/project/reservoir observations with three labels (Chemical, Gas, Thermal) and six predictors (porosity, permeability, depth, temperature, API gravity, oil viscosity). It can be considered for a separate family-level research exercise once the raw files and Supplementary Table S1 have been downloaded and hashes/source identities recorded.

It is not compatible with the current nine-class production target or the expanded 68-feature engineering-aware training schema as published. Do not concatenate it directly with OGJ2014 rows or treat the dataset's excluded Niger Delta application cases as available holdout rows until the actual files and case-level Supplementary Table S1 have been inspected.

## Next-generation training gate

The existing src/ml/train_hybrid_catboost.py is intentionally fail-closed: it needs real technique labels, formation context, resolved field_id grouping, all inputs required by src/ml/hybrid_feature_builder.py, and at least six independent field groups per class. The currently benchmarked OGJ2014 data is structured around ranges used by the 17-feature v1 recipe and does not, by itself, provide a fully source-backed vector for all engineering-aware v2 inputs.

Training must remain blocked until the enriched dataset is assembled. Do not fill unavailable pressure, temperature, salinity, hardness, net pay, water-cut, saturation or operational-context values with invented values merely to satisfy the feature builder. Either source and document those inputs, or formally scope a separately versioned reduced-feature research model before fitting.

## Promotion requirements

Before any production promotion:
1. Freeze the source workbook and reviewed identity/label registers with content hashes.
2. Obtain production-eligible records from fields not present in the v1 training manifest.
3. Keep a final field-isolated holdout untouched during tuning.
4. Compare the v2 CatBoost pipeline with simple baselines on identical field-grouped splits.
5. Report macro-F1, balanced accuracy, per-class precision/recall/F1, confusion matrices, calibration, support, and split variability.
6. Review engineering plausibility and model behaviour on invalid inputs.
7. Keep every new artifact versioned and separate from the live v1 artifact until the promotion gate is explicitly approved.

Reported technique-classification scores must not be presented as estimates of EOR success, incremental recovery or economics.
