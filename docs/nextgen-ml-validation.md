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


## Source-review pass (2026-10-14)

A first source-by-source audit is recorded in `data/provenance/field_evidence_source_review.csv`; the wider candidate register is maintained in `data/provenance/external_eor_evidence_leads.csv`. These are audit artifacts, not training tables. No candidate from the latest pass is yet marked eligible for v2 training.

Important findings:
- **Miscible acid gas:** the 2007 field-history review explicitly records a 1976 miscible acid-gas pilot at Slaughter Estate Unit and cites Rowe et al. (1982) / Schiltz et al. (1984), but the excerpt only supplies carbonate context, 6.4 mD permeability and 1.38 cP oil viscosity. The primary source must be retrieved for depth, temperature, pressure, API and oil saturation. Do not count it as a feature-complete row until that extraction and the field-identity audit are complete.
- **Hot water:** the Loco Field 1968/1969 pilot paper confirms an implemented tertiary hot-waterflood and reports approximately 600 cP oil and pilot production, but its abstract is not a complete reservoir-property record. Pelican Lake E29 is a real hot-water-injection pilot from 2011; the readily available broad Pelican Lake property ranges come from a different field-wide source and do not necessarily describe the E29 transition zone. Pelican Lake already occurs in the OGJ2014 training source under polymer, so it cannot be in a holdout intended to be unseen relative to v1. Kern River's post-steam water injection is a separate stage and should not automatically be relabelled as stand-alone hot water. J8's cited paper evaluates viscosity-reducer injection; its hot-water development context is not the same as a hot-water test label.
- **Nitrogen immiscible:** a field review describes immiscible nitrogen injection at Akal/Cantarell and cites primary project work, but the reviewed snippets do not supply the full v2 vector. The 2020 global field table lists Liaohe Tuo 33 as immiscible N2 with porosity, permeability, depth, temperature and viscosity but no API, pressure or oil saturation; other project descriptions mention N2 foam, so the exact episode needs primary-source adjudication. Turner Valley is named in an OGJ nitrogen project row but miscibility is not established by that row alone. A source describes Jay as a nitrogen-miscible flooding case, so Jay LEC was corrected and excluded from nitrogen-immiscible evidence.
- **HC immiscible:** Ekofisk has separate historical gas-injection descriptions, including a lean-HC episode described as immiscible and another miscible-N2 episode. Keep episodes separate and do not count the field as unseen if any Ekofisk record was in training. Handil lean-gas history is a lead only until target miscibility and core properties are primary-source verified.
- **Disposal, simulation-only or proposed work is not a historical EOR training example.** Wayne-Rosedale acid-gas disposal, the North Viking Graben proposal that did not proceed, and the proposed Bohai Field D pilot remain excluded from class support. Foam projects are not coerced into plain-gas-flood classes.

## Current holdout readiness

The current v1 training manifest contains row IDs but not canonical field IDs on its own. A reproducible script, `scripts/reconstruct_v1_training_field_manifest.py`, now joins the reconstructed 526 v1 training rows to the source workbook's field-ID columns and produces a field-level training manifest/report. A second script, `scripts/prepare_v2_field_holdout.py`, refuses to emit a split unless the v1 manifest has confirmed field IDs, the v2 observations have approved source labels and complete finite core measurements, the holdout fields are absent from v1 training, the training/holdout groups are disjoint, and per-class field support remains at or above the configured gates.

The held-out set is configured for at least **two entire independent fields per technique class**, while leaving at least **six independent field groups per class in v2 training**. That means at least eight feature-complete field groups per class are needed before the reserved split can pass. No split is generated from the evidence-lead register or from incomplete rows.

## Current decision

The exact-class, feature-complete, v1-unseen record count from this source-review pass is **zero**. The four original deficits therefore remain: HC immiscible (2/6; gap 4), Hot water (2/6; gap 4), Miscible acid gas (1/6; gap 5), Nitrogen immiscible (2/6; gap 4). These counts are the baseline confirmed support; provisional candidates do not increase the counts. No v2 benchmark has been run, and no candidate model has been trained or promoted.
