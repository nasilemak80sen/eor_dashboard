# 🛢️ EOR Atlas

### Enhanced Oil Recovery Screening & Decision Support Platform

EOR Atlas is an engineering-first Streamlit platform for EOR screening, reservoir opportunity analysis, historical evidence review, and data-driven EOR intelligence.

## Decision Architecture

The production decision path is deliberately simple and auditable:

```text
Reservoir / Field Inputs
        │
        ▼
┌─────────────────────┐
│     Excel Gate      │
│ deterministic rules │
└──────────┬──────────┘
           │ eligible candidates
           ▼
┌─────────────────────┐
│  Hybrid Intelligence│
│      CatBoost       │
└──────────┬──────────┘
           │ class probabilities
           ▼
┌─────────────────────┐
│   Decision Fusion   │
│ engineering + ML    │
└──────────┬──────────┘
           ▼
   Hybrid EOR Ranking
```

**Engineering feasibility is authoritative. CatBoost supports the decision; it does not override a hard engineering failure.**

Fuzzy suitability is no longer part of the production dashboard decision path.

## Dashboard Modules

| Module | Role |
|---|---|
| 🏠 Executive Overview | Portfolio-level EOR indicators and operational overview |
| 🔍 EOR Screening | Deterministic Excel/ScreenTool engineering gate |
| 🎯 Field / Reservoir Parameters | Independent candidate exploration and reservoir-property analytics |
| 🧪 CEOR — Fluid / Fluid | Chemical EOR laboratory-style fluid analytics |
| 🪨 CEOR — Fluid / Rock | Fluid-rock interaction and compatibility analytics |
| 📚 Past EOR Results | Historical application records and saved screening runs |
| ⚠️ Challenges & Lessons | Engineering observations and lessons learnt |
| 🤖 EOR Intelligence | Excel-gated CatBoost prediction and decision fusion |

The Field / Reservoir Parameters tab is intentionally independent: it does not launch deterministic screening, call the ML model, or hand a selected reservoir into another tool.

## Excel Gate

The screening layer reproduces the executable engineering logic represented by the EOR screening workbook. It returns technique-level:

- PASS
- CONDITIONAL
- FAIL (critical)
- engineering score
- incremental recovery estimate
- reasons for failure or conditionality

A critical Excel Gate failure is a hard veto in Decision Fusion.

## Hybrid Intelligence

The current production path uses the existing CatBoost v1 artifact as a compatibility model while the richer v2 training pipeline is prepared.

Initial fusion defaults are:

```text
CatBoost probability        65%
Engineering compatibility  35%
Conditional penalty          0.90
```

These are implementation defaults, not validated project-performance claims. They should be calibrated against a sufficiently large labelled validation set before being treated as formal decision criteria.

### CatBoost v1 compatibility layer

The current model consumes 17 engineered features derived from:

- depth
- porosity
- permeability
- API gravity
- viscosity
- oil saturation
- uncertainty spans
- log permeability
- log viscosity
- formation indicators

The hybrid layer maps the model's current technique taxonomy to the ScreenTool taxonomy before fusion.

## Next CatBoost Generation

`src/ml/hybrid_feature_builder.py` provides the schema for the next engineering-aware model. It adds context such as:

- reservoir pressure and bubble-point margin
- temperature and net pay
- water cut
- salinity and hardness
- mobility, injectivity, heterogeneity and maturity
- injection-facility availability
- WAG context
- CO2 / MMP availability
- gas availability and reinjection context
- optional Sorw
- optional movable-oil saturation (`So - Sorw`)
- optional Produced GOR and derived GOR category

Missing optional values are represented explicitly; they are not silently treated as measured observations.

`src/ml/train_hybrid_catboost.py` trains this next-generation model only from a real labelled historical EOR dataset. ScreenTool-generated labels are intentionally not used as training targets because that would simply teach ML to reproduce the deterministic rule set.

## Model Evaluation

Model development should track more than accuracy. The assessment workflow is intended to monitor:

- accuracy
- macro F1
- weighted F1
- per-technique precision / recall / F1
- confusion matrix
- probability calibration
- confidence coverage

The repository also contains regression tests for the hybrid decision layer and feature schema.

## Project Structure

```text
EORWEBDEV/
├── data/
├── outputs/model_artifacts/
├── tests/
│   ├── test_hybrid_intelligence.py
│   └── test_hybrid_feature_builder.py
├── src/
│   ├── app_2.py
│   ├── hybrid_app.py
│   ├── candidate_analytics/
│   ├── config/
│   ├── data/
│   ├── domain/
│   ├── ml/
│   │   ├── feature_builder.py
│   │   ├── hybrid_feature_builder.py
│   │   ├── hybrid_intelligence.py
│   │   ├── model_assessment.py
│   │   ├── model_service.py
│   │   └── train_hybrid_catboost.py
│   └── utils/
├── EOR_Screening_Tool_2026.xlsx
├── requirements.txt
└── README.md
```

## Running Locally

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

Linux/macOS:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the production hybrid entrypoint:

```bash
streamlit run src/hybrid_app.py
```

## Testing

Run the hybrid regression tests:

```bash
PYTHONPATH=src pytest -q tests/test_hybrid_intelligence.py tests/test_hybrid_feature_builder.py
```

Run syntax checks:

```bash
python -m py_compile src/ml/hybrid_intelligence.py src/ml/hybrid_feature_builder.py src/ml/train_hybrid_catboost.py src/hybrid_app.py
```

GitHub Actions runs these checks automatically for pushes and pull requests to `main`.

## Data Sources

The platform uses the engineering screening workbook, application persistence, and historical EOR evidence available in the repository. The Field / Reservoir Parameters analytics use the workbook's reservoir-property tables and do not depend on a generated placeholder dataset.

## Limitations

EOR Atlas is a screening and decision-support platform, not a full-field reservoir simulator, detailed project design package, or substitute for reservoir-engineering judgement.

The current hybrid model is still an implementation-stage decision-support component. A production-grade next-generation CatBoost model requires a larger, consistently labelled historical dataset and independent validation.

## Disclaimer

Outputs are intended for screening, analytical support, and technical demonstration. Qualified reservoir engineering and EOR specialists should review results before technical or investment decisions are made.
