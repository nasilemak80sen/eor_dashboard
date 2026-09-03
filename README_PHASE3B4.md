# EOR Atlas — Enhanced Oil Recovery Screening System

**Phase 3B & Phase 4 Implementation**

A decision-support platform that combines machine learning predictions with engineering domain knowledge to recommend enhanced oil recovery (EOR) techniques.

---

## 🎯 Architecture Overview

### Phase 3B: ML ↔ Streamlit Integration

```
┌───────────────────────────┐
│        STREAMLIT UI        │
│                           │
│ Reservoir Inputs          │
└──────────────┬────────────┘
               │
               ▼
      ┌─────────────────┐
      │ Input Validator │
      └────────┬────────┘
               │
               ▼
      ┌─────────────────┐
      │ Feature Builder │
      └────────┬────────┘
               │
               ▼
      ┌─────────────────┐
      │  Model Service  │
      │                 │
      │   CatBoost      │
      └────────┬────────┘
               │
               ▼
      ┌────────────────────┐
      │ PredictionResult   │
      └────────┬───────────┘
               │
               ▼
      ┌────────────────────┐
      │  ML Result Card    │
      └────────────────────┘
```

**Key principle:** The UI doesn't know CatBoost exists. It only interacts with `ModelService`, which returns `PredictionResult`.

### Phase 4: Engineering Decision Intelligence

```
                  Reservoir Data
                       │
             ┌─────────┴─────────┐
             │                   │
             ▼                   ▼
       Engineering          ML Model
       Screening             Screening
             │                   │
             ▼                   ▼
       EOR Criteria        ML Prediction
             │                   │
             └─────────┬─────────┘
                       ▼
                Decision Engine
                       │
                       ▼
              Decision Assessment
```

**Key principle:** ML is ONE source of evidence. Engineering rules are ANOTHER source. The Decision Engine reconciles them.

---

## 📁 File Structure

```
eor_dashboard/
│
├── config.py                 # Configuration & constants
├── model_service.py          # ML service layer (Phase 3B)
├── ml_prediction.py          # Prediction dataclasses (Phase 3B)
├── engineering_rules.py      # Domain rules engine (Phase 4)
├── decision_engine.py        # ML + engineering reconciliation (Phase 4)
├── ui_components.py          # Streamlit UI building blocks
│
├── app.py                    # Main Streamlit application
├── test_eor_atlas.py         # Test suite
│
├── requirements.txt          # Python dependencies
├── .streamlit_config.toml    # Streamlit configuration
│
├── data/                     # Input data
├── outputs/                  # Model artifacts & results
│   └── model_artifacts/
│       ├── eor_model.joblib
│       ├── label_encoder.joblib
│       └── feature_order.json
│
└── README.md                 # This file
```

---

## 🚀 Getting Started

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Prepare Model Artifacts

Place your trained model files in `outputs/model_artifacts/`:

- `eor_model.joblib` — Trained CatBoost model
- `label_encoder.joblib` — Label encoder for EOR techniques
- `feature_order.json` — Feature order (if not using default)

### 3. Run Application

```bash
streamlit run app.py
```

The app will start on `http://localhost:8501`

### 4. Run Tests

```bash
pytest test_eor_atlas.py -v
```

---

## 📊 How It Works

### Step 1: Reservoir Input (Phase 3B)

User enters 17 reservoir properties:
- Depth, Porosity, Permeability
- API, Viscosity, Oil Saturation
- Formation, Temperature, Clay Content
- Water Saturation, Net-to-Gross
- Trap Type, Lithology, Underburden
- Seal Quality, Faulting, Dip

### Step 2: ML Screening (Phase 3B)

`ModelService.predict()` returns:

```python
PredictionResult(
    technique="Miscible HC",
    confidence=0.65,  # 65%
    confidence_level="🟡 MODERATE",
    candidates=[
        ("Miscible HC", 0.65),
        ("Steam", 0.25),
        ("Miscible CO2", 0.08)
    ],
    feature_importance={
        "Viscosity": 0.95,
        "API": 0.87,
        ...
    }
)
```

**The UI has no idea this came from CatBoost.**

### Step 3: Engineering Assessment (Phase 4)

`EngineeringRuleEngine.assess_technique()` evaluates against domain criteria:

**For Miscible HC:**
- ✓ Oil viscosity < 35 cp → Satisfied
- ✓ API gravity > 30° → Satisfied
- ✗ Depth > 12,000 ft → Violated
- ⚠ Permeability < 50 md → Warning

Returns:

```python
EngineeringAssessment(
    technique="Miscible HC",
    compatibility_score=0.75,  # 75%
    compatibility_level="HIGH",
    satisfied_criteria=[...],
    violated_criteria=[...],
    recommendations=[...]
)
```

### Step 4: Decision Reconciliation (Phase 4)

`DecisionEngine` applies decision matrix:

| ML | Engineering | Recommendation |
|----|-------------|----------------|
| High (≥70%) | High | 🟢 **Strong candidate** |
| High | Moderate | 🟡 **Candidate** |
| High | Low | 🔴 **Engineering conflict** |
| Moderate | High | 🟡 **Candidate** |
| Moderate | Moderate | 🟡 **Review required** |
| Low (<60%) | High | 🟡 **Engineering review** |
| Low | Low | 🔴 **Weak candidate** |

Returns:

```python
IntegratedAssessment(
    ml_result=PredictionResult(...),
    engineering_assessment=EngineeringAssessment(...),
    recommendation_level="🟢",
    recommendation_text="Strong candidate",
    reasoning=[...]
)
```

---

## 🔑 Key Design Principles

### 1. Separation of Concerns

- **UI** (`app.py`, `ui_components.py`) — Presentation only
- **ML** (`model_service.py`) — CatBoost encapsulation
- **Engineering** (`engineering_rules.py`) — Domain logic
- **Decision** (`decision_engine.py`) — Reconciliation

**No business logic in the UI.**

### 2. Contract-Based Integration

`PredictionResult` and `EngineeringAssessment` are contracts:

- UI doesn't call CatBoost directly
- Engineering rules don't parse ML output
- Decision engine doesn't know about Streamlit

### 3. Explainability

Every recommendation includes reasoning:

```
✓ Reservoir depth is within applicable range
✓ Oil viscosity is compatible
⚠ ML confidence is only 46%
⚠ Steam is a competing ML candidate
```

### 4. Low Confidence Handling

When ML confidence < 60%:

- Display warning
- Emphasize engineering assessment
- Recommend human review

---

## 📋 EOR Techniques Evaluated

1. **Miscible HC** — Hydrocarbon miscible injection
2. **Steam** — Thermal steam injection
3. **Miscible CO₂** — Carbon dioxide miscible
4. **Polymer** — Polymer flooding
5. **ASP** — Alkaline-Surfactant-Polymer

---

## 🧪 Testing

### Unit Tests

```bash
pytest test_eor_atlas.py::TestPredictionResult -v
pytest test_eor_atlas.py::TestEngineeringRuleEngine -v
pytest test_eor_atlas.py::TestDecisionEngine -v
```

### Integration Tests

```bash
pytest test_eor_atlas.py::TestIntegration -v
```

### Test Coverage

```bash
pytest test_eor_atlas.py --cov=. --cov-report=html
```

---

## 🔧 Configuration

Edit `config.py` to customize:

- Model paths and versions
- Feature list and order
- EOR technique classes
- Confidence thresholds
- Engineering rule parameters
- Decision matrix

---

## 📈 Sensitivity Analysis

Explore how decisions change with parameter variations:

```
Viscosity: 5 cp → Miscible HC
Viscosity: 20 cp → Miscible HC
Viscosity: 50 cp → Steam
Viscosity: 80 cp → Steam
```

This helps engineers understand decision stability.

---

## 🚨 Error Handling

The system gracefully handles:

- Missing input features
- Out-of-range values
- Model loading failures
- Prediction errors

Instead of crashing, users see:

```
⚠ ML screening unavailable

The model artifact could not be loaded.

Engineering screening is still available.
```

---

## 📥 Batch Processing

Upload a CSV with multiple reservoirs:

```csv
Depth,Porosity,Permeability,API,Viscosity,...
5000,20,100,32,10,...
7000,18,50,28,25,...
3000,22,200,40,5,...
```

Get bulk screening results in seconds.

---

## 🔍 Explainability Features

### Feature Importance

Shows which reservoir properties had most impact on ML decision.

### Engineering Reasoning

Explains which criteria were satisfied/violated.

### Decision Chain

Documents the complete ML → Engineering → Decision flow.

### Sensitivity Analysis

Demonstrates decision robustness to parameter changes.

---

## 🚀 Next Steps

After Phase 4, consider:

1. **Model Retraining** — Collect new field data, retrain CatBoost
2. **Rule Refinement** — Calibrate engineering thresholds
3. **Deployment** — GitHub Actions CI/CD pipeline
4. **Session Management** — Persistent study storage
5. **Reporting** — Export recommendations as PDF
6. **Analytics** — Track screening trends

---

## 📖 References

- CatBoost: https://catboost.ai/
- Streamlit: https://streamlit.io/
- EOR Techniques: *A Neuro-Fuzzy Approach to Screening Reservoir Candidates for EOR*

---

## ✅ Checklist: Phase 3B Complete

- [x] ML service separated from UI
- [x] `PredictionResult` contract defined
- [x] Feature validation in place
- [x] Confidence classification implemented
- [x] Feature importance extraction working
- [x] Streamlit UI uses only `ModelService`
- [x] Error handling for ML failures

## ✅ Checklist: Phase 4 Complete

- [x] Engineering rule engine implemented
- [x] All 5 EOR techniques evaluated
- [x] Engineering assessment scoring
- [x] Decision matrix reconciliation
- [x] ML + engineering integration
- [x] Explainability framework
- [x] Sensitivity analysis
- [x] Complete test coverage

---

## 📞 Support

For issues or questions, refer to:

1. `README.md` — Architecture overview
2. `test_eor_atlas.py` — Usage examples
3. Docstrings in source files — Implementation details
4. `config.py` — Configuration reference

---

**EOR Atlas v1.0** — Phase 3B & Phase 4 Complete

Last updated: September 2026
