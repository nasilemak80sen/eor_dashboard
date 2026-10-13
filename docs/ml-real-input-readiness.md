# ML Real-Input Readiness

This note defines the safety boundary for the engineering-aware CatBoost training path.

## Runtime input contract

`src/ml/hybrid_feature_builder.py` rejects missing, non-numeric, non-finite, or out-of-domain core measurements before it builds the feature vector. The required core inputs are:

- `depth_ft` (> 0)
- `temperature_c` (-20 to 400 °C)
- `reservoir_pressure` (> 0)
- `porosity_pct` (0–100%)
- `perm_md` (>= 0 mD)
- `api` (0–100)
- `visc_cp` (> 0 cp)
- `so_pct` (0–100%)

Optional measurements such as Sorw and produced GOR remain optional; the feature schema uses explicit availability indicators for these two inputs. When optional numeric values are supplied, invalid values are rejected rather than silently normalised. Unrecognized non-empty categorical values (including injectivity, mobility, risk, binary yes/no, and WAG ratio inputs) are rejected rather than silently mapped to zero or a default ratio. An unfamiliar formation name remains explicitly unclassified by the three existing formation indicator features.

## Training readiness gates

`src/ml/train_hybrid_catboost.py` is deliberately fail-closed:

1. Target technique and formation values must be present and resolved.
2. Rows marked `needs_review` cannot enter training until they are reviewed or excluded through a documented, reproducible dataset-preparation step.
3. The production-candidate trainer requires complete `field_id` values. Case/report/publication grouping may be useful for research, but does not satisfy this field-generalisation gate.
4. Every target technique must have at least six independent field groups, not merely six rows.
5. Cross-validation uses group-isolated splits; provenance identifiers are not predictive features.
6. Model artifacts are written only after these checks and validation complete.

If a gate fails, the expected outcome is an actionable error and no newly promoted model artifact. Do not weaken the gates just to make a small dataset train.

## Interpretation boundary

The OGJ2014 literature table represents reported technique associations. It does not provide a direct outcome target for recovery factor uplift, economic value, or project success. A model trained on it must be described as a technique-association/research model, not an EOR success predictor.

The Excel/ScreenTool engineering gate remains authoritative. ML output is supplementary evidence and must never override a critical engineering failure. A technique that fails the hard gate is excluded from the recommendation ranking; if every mapped technique fails, the service returns no recommendation. Relative hybrid ranking scores are not calibrated probabilities of success.

## Validation

The hybrid CI workflow runs regression tests for missing and invalid real inputs, training-label quarantine, independent field-group support, and malformed ML probabilities. A passing CI run confirms those automated checks; browser-level and engineering-domain validation remain separate acceptance steps.
