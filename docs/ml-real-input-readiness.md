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


## OGJ2014 field-level benchmark status (2026-10-13)

Latest successful run: [OGJ2014 Field-Level ML Benchmark #123](https://github.com/nasilemak80sen/eor_dashboard/actions/runs/38365159114).

- The original 624 source rows and unique record IDs are preserved. Source-adjudication registers cover 179 label-conflict records and eight partial field fragments; original structured labels and raw source text remain unchanged. Twenty-three rows outside the v1 target taxonomy are excluded from the v1 benchmark scope.
- Historical CatBoost v1.0.0 training membership has been reconstructed and verified: 526 record IDs; the historical/current original 15-column workbook matrix SHA-256 values match. The model artifact SHA-256 also matches the historical artifact.
- Restricted five-class research scope: 585 rows across Combustion, Miscible CO2, Miscible HC, Polymer and Steam.
- Research CatBoost results: five-fold field-grouped CV macro-F1 0.743 ± 0.052; field-isolated holdout macro-F1 0.782 on 118 rows from 48 fields; 20 repeated field-isolated holdouts macro-F1 0.772 ± 0.052. Repeated-holdout percentiles describe split variability and are not formal confidence intervals.
- Four of nine classes remain below the minimum six independent confirmed fields: HC immiscible (2), Hot water (2), Miscible acid gas (1), Nitrogen immiscible (2). Full nine-class model promotion remains blocked.
- The reconstructed v1 training membership leaves zero genuinely unseen confirmed-field rows for direct deployed-artifact evaluation. The fold-retrained recipe comparison is not a direct score for the deployed artifact.
- This dataset represents observed literature technique associations, not EOR success, recovery uplift, or economic value. These results are preliminary internal research only; no production model artifact was changed.

Reports and reproducible CSV/JSON outputs are attached to the successful workflow run above as the `ogj2014-field-level-ml-reports` artifact.
