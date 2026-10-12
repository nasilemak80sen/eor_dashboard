# EOR Atlas ML Research Layer

## Recommended model strategy

The current research dataset is a small, tabular, literature/project-range dataset. The visible repository notebook output shows a 624-row extracted-range table with EOR technique, formation and min/max reservoir variables.

Therefore:

- **Primary candidate:** XGBoost
- **Required baseline:** Random Forest
- **Strong alternates:** CatBoost, ExtraTrees, SVM-RBF
- **Sanity baseline:** Logistic Regression
- **Research comparison:** MLP / neural network
- **Optional small-data research:** TabPFN, subject to environment/licensing review

Do not select a model because it is a neural network. Tree boosting is a much more natural first hypothesis for this type of data, and EOR-specific published studies have also found strong performance from RF/boosting-family models. See the sources cited in the accompanying assistant response.

## Main scientific concern

Your data is literature-derived and range-based. If the target technique is closely tied to the ranges used as predictors, the model may learn the data construction process rather than a robust field-level causal relationship.

The primary benchmark therefore excludes:
- `# projects`
- `raw_line`
- fuzzy scores

Fuzzy scores are evaluated as a separate evidence layer in EOR Intelligence.

## Validation and promotion guardrails

The benchmark removes exact duplicate training records and aggregates
identical reservoir-feature rows into a multi-label target containing every
associated technique. One-vs-rest models are selected using source-grouped
cross-validation only; a separate source-grouped holdout is reported once for
the selected candidate and is never used to rank models.

The benchmark requires a field, project, report, or publication identifier
standardized as `source_group`, with at least six independent groups per
technique. The current extracted OGJ table has no such identifier and very
limited independent support for multiple classes, so it must not produce a
generalization claim or a deployable model. Add traceable source-group IDs and
more independently labelled cases before attempting a fresh benchmark.

The current extracted table contains 51 identical feature signatures linked
to multiple techniques (108 raw rows; 102 remain after exact duplicate
removal). These are treated as multi-label associations, not as conflicting
single-label records. The training objective is therefore technique
association/suitability, not a single best-method classification.

`05_export_artifact.ipynb` writes only a separately named
`eor_research_candidate.joblib` after the grouped evaluation has completed. It
does not overwrite the active production CatBoost v1 artifact. The candidate's
labels remain literature-associated technique labels, not proven project
success outcomes, and require engineering review before any production use.

## Notebook order

1. `01_data_audit.ipynb`
2. `02_feature_engineering.ipynb`
3. `03_model_benchmark.ipynb`
4. `04_model_evaluation_explainability.ipynb`
5. `05_export_artifact.ipynb`

## Deployment flow

Jupyter:
    data -> features -> benchmark -> evaluate -> export

Dashboard:
    exported joblib -> ResearchModelService -> Top 3

EOR Screening remains independent:
    reservoir input -> exact Excel deterministic logic

EOR Intelligence:
    same input -> ML Top 3 + fuzzy Top 3 + concordance

## Important taxonomy issue

The notebook sample contains labels such as `Steam` and `Miscible CO2`, while the deterministic Excel specification uses 13 more specific method names. Do not silently relabel them. Use the supplied `taxonomy_mapping_template.json` as a starting point and review mappings with engineering/domain owners before retraining a production model.
