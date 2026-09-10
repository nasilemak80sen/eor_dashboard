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

## Redesigned UI Shell

The recommended production UI entrypoint is now `src/eor_atlas.py`.

The interface uses a PETRONAS-inspired internal application shell with:

- sidebar navigation instead of a wide horizontal tab row
- consistent page headers and reusable KPI/status components
- PETRONAS green, blue, lime, yellow and purple accents
- an engineering-first visual hierarchy
- one active page rendered at a time to reduce visual clutter and unnecessary widget execution
- dedicated pages for portfolio discovery, engineering screening, hybrid intelligence, insights, historical knowledge, CEOR analysis, challenges and system governance

The redesign is presentation-only: the working Excel Gate, current CatBoost compatibility model, and Decision Fusion services remain in the existing execution layer.

## Dashboard Modules

| Module | Role |
|---|---|
| 🏠 Executive Overview | Portfolio-level EOR indicators and opportunity landscape |
| 🎯 EOR Candidates | Interactive field/reservoir candidate exploration |
| 🔍 EOR Screening | Deterministic Excel/ScreenTool engineering gate |
| 🧠 Hybrid Intelligence | Excel-gated CatBoost ranking and Decision Fusion |
| 📊 EOR Insights | Portfolio opportunity concentration and action view |
| 📚 Historical EOR | Historical application records and saved screening runs |
| ⚠️ Challenges & Lessons | Engineering observations and execution risks |
| 🧪 CEOR Lab | Fluid/fluid and fluid/rock technical analytics |
| ⚙ System & Model | Runtime health and model governance |

The EOR Candidates module remains intentionally independent from deterministic screening and machine-learning inference.

## Excel Gate

The screening layer reproduces the executable engineering logic represented by the EOR screening workbook. It returns technique-level:

- PASS
- CONDITIONAL
- FAIL (critical)
- engineering score
- incremental recovery estimate
- reasons for failure or conditionality

A critical Excel Gate failure is a hard veto in Decision Fusion.

## ScreenTool v3 Inputs

The v3-aligned production input flow distinguishes core engineering variables from optional context.

Core reservoir and recovery inputs include depth, pressure, temperature, viscosity, API gravity, permeability, porosity, Current Oil Saturation (`So`), recovery context, waterflood history, injection context and gas/WAG information.

Optional/context fields include:

- Residual Oil Saturation to Waterflood (`Sorw`)
- optional numeric Produced GOR
- numeric GOR-derived category
- movable oil saturation (`So - Sorw`)
- `φSo` opportunity indicator
- gas-source/reinjection context

Optional fields are represented explicitly when unavailable; values are not silently fabricated.

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

`src/ml/train_hybrid_catboost.py` trains this next-generation model only from a real labelled historical EOR dataset. ScreenTool-generated labels are intentionally not used as training targets.

## Model Evaluation

The model assessment workflow tracks:

- accuracy
- balanced accuracy
- macro and weighted F1
- precision / recall
- log loss
- probability calibration / ECE
- class support and sparse-class readiness

The repository contains regression tests for the hybrid decision layer, feature schema, model assessment utilities and the redesigned UI imports.

## Project Structure

```text
EORWEBDEV/
├── data/
├── outputs/model_artifacts/
├── tests/
│   ├── test_hybrid_intelligence.py
│   ├── test_hybrid_feature_builder.py
│   └── test_hybrid_model_assessment.py
├── src/
│   ├── app_2.py
│   ├── hybrid_app.py
│   ├── eor_atlas.py              # redesigned production UI shell
│   ├── ui/
│   │   ├── theme.py
│   │   ├── components.py
│   │   ├── navigation.py
│   │   └── app_shell.py
│   ├── pages_ui/
│   │   ├── overview.py
│   │   ├── candidates.py
│   │   ├── screening.py
│   │   ├── intelligence.py
│   │   ├── insights.py
│   │   ├── historical.py
│   │   ├── ceor.py
│   │   ├── challenges.py
│   │   └── system.py
│   ├── candidate_analytics/
│   ├── config/
│   ├── data/
│   ├── domain/
│   ├── ml/
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

Run the redesigned production interface:

```bash
streamlit run src/eor_atlas.py
```

The previous hybrid entrypoint remains available for direct engineering/ML troubleshooting:

```bash
streamlit run src/hybrid_app.py
```

## Testing

Run the regression tests:

```bash
PYTHONPATH=src pytest -q tests/test_hybrid_intelligence.py tests/test_hybrid_feature_builder.py tests/test_hybrid_model_assessment.py
```

Run syntax checks:

```bash
python -m py_compile src/eor_atlas.py src/hybrid_app.py src/ml/hybrid_intelligence.py src/ml/hybrid_feature_builder.py src/ml/hybrid_model_assessment.py src/ml/train_hybrid_catboost.py
```

GitHub Actions also compiles and imports the redesigned UI modules on pushes and pull requests to `main`.

## Limitations

EOR Atlas is a screening and decision-support platform, not a full-field reservoir simulator, detailed project design package, or substitute for reservoir-engineering judgement.

The current hybrid model is still an implementation-stage decision-support component. A production-grade next-generation CatBoost model requires a larger, consistently labelled historical dataset and independent validation.

## Disclaimer

Outputs are intended for screening, analytical support, and technical demonstration. Qualified reservoir engineering and EOR specialists should review results before technical or investment decisions are made.
