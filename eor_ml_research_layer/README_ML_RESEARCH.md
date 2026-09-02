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
