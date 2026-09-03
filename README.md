# 🛢️ EOR Atlas

### Enhanced Oil Recovery Screening & Decision Support Platform

**EOR Atlas** is an engineering-first decision-support platform for **Enhanced Oil Recovery (EOR)** screening, reservoir suitability assessment, and data-driven EOR intelligence.

The platform combines **deterministic engineering screening**, **fuzzy suitability analysis**, and **CatBoost machine learning** within a single Streamlit dashboard.

> **Engineering feasibility remains authoritative. ML and fuzzy logic provide independent decision-support signals.**

---

## 📌 Overview

EOR Atlas was developed to support reservoir engineers in evaluating potential EOR opportunities using a structured and repeatable workflow.

The platform brings together three independent analytical layers:

| Layer                       | Purpose                                      | Output                    |
| --------------------------- | -------------------------------------------- | ------------------------- |
| **Deterministic Screening** | Engineering rule-based screening             | PASS / CONDITIONAL / FAIL |
| **Fuzzy Suitability**       | Evaluate reservoir fit against EOR envelopes | Suitability ranking       |
| **ML Intelligence**         | Learn patterns from historical EOR data      | Probabilistic EOR ranking |

This separation ensures that machine learning does not override established engineering constraints.

---

## 🚀 Key Capabilities

### 🔍 EOR Screening

Performs deterministic screening using reservoir and operational inputs such as:

* Depth
* Temperature
* Oil viscosity
* API gravity
* Permeability
* Porosity
* Oil saturation
* Reservoir characteristics
* Waterflood history
* Injection facilities
* Gas availability
* Mobility considerations
* Field maturity
* Other EOR-specific constraints

The screening layer provides:

* EOR technique eligibility
* Engineering suitability
* Screening score
* Estimated incremental recovery
* Failure / conditional reasoning

---

### 🧠 EOR Intelligence

The EOR Intelligence layer provides two independent analytical perspectives.

#### CatBoost ML Ranking

The embedded CatBoost model provides a probabilistic ranking of EOR techniques based on engineered reservoir features.

Current production feature space:

```text
17 engineered features
```

including:

* Reservoir depth
* Porosity
* Permeability
* API gravity
* Oil viscosity
* Oil saturation
* Feature spans
* Log-transformed permeability
* Log-transformed viscosity
* Formation-type indicators

The model returns:

* Top EOR candidates
* Class probabilities
* Ranking
* Confidence information

#### Fuzzy Suitability

The fuzzy layer evaluates the reservoir against predefined EOR suitability envelopes.

This provides an independent suitability perspective without combining the score with the ML probability.

---

## 🏗️ Decision Architecture

```text
                    EOR Atlas
                       │
                       ▼
             Reservoir / Field Inputs
                       │
          ┌────────────┼────────────┐
          │            │            │
          ▼            ▼            ▼
    Deterministic     Fuzzy       CatBoost
      Screening     Suitability      ML
          │            │            │
          ▼            ▼            ▼
    Engineering      Envelope     Data-driven
     Feasibility     Ranking       Ranking
          │            │            │
          └────────────┼────────────┘
                       ▼
              Engineering Decision
```

### Design Principle

The analytical layers are intentionally independent.

```text
Deterministic Screening
        ↓
Engineering feasibility

Fuzzy Suitability
        ↓
Reservoir-envelope compatibility

CatBoost ML
        ↓
Historical/data-driven similarity
```

No arbitrary weighted ensemble is used to combine these signals.

---

## 🗂️ Dashboard

The Streamlit dashboard currently provides the following modules:

### 🏠 Executive Overview

Portfolio-level overview including:

* Field and reservoir metrics
* EOR opportunity indicators
* Field opportunity visualization
* Portfolio statistics

### 🔍 EOR Screening

Interactive reservoir screening using deterministic engineering logic.

### 🗺️ Field / Reservoir Candidates

Candidate reservoir comparison with technical indicators and EOR method suggestions.

### 🧪 CEOR — Fluid / Fluid

Chemical EOR laboratory-style analytics covering areas such as:

* Rheology
* Thermal stability
* Formulation behaviour

### 🪨 CEOR — Fluid / Rock

Fluid-rock interaction and compatibility analysis.

### 📚 Past EOR Results

Historical EOR study and assessment records stored in the application database.

### ⚠️ Challenges & Lessons

Engineering observations, limitations, and lessons learned from EOR application.

### 🤖 EOR Intelligence

Integrated view of:

* CatBoost Top 3 EOR predictions
* Fuzzy Top 5 suitability ranking
* ML probability distribution
* Fuzzy suitability distribution
* Model metadata

---

## 🧰 Technology Stack

### Application

* Python
* Streamlit
* Pandas
* NumPy
* SciPy

### Machine Learning

* CatBoost
* Scikit-learn
* Joblib

### Engineering Intelligence

* Deterministic rule-based screening
* Fuzzy envelope suitability analysis

### Data & Persistence

* Excel workbooks
* OpenPyXL
* SQLite
* SQLAlchemy

### Visualization

* Streamlit charts
* PyDeck
* Interactive geographic visualization

---

## 📁 Project Structure

```text
EORWEBDEV/
│
├── data/
│   └── NeuroFuzzy_EOR_Extracted_Tables.xlsx
│
├── outputs/
│   └── model_artifacts/
│       ├── eor_catboost_v1.0.0.joblib
│       ├── label_encoder_catboost_v1.0.0.joblib
│       ├── config_catboost_v1.0.0.json
│       └── model_manifest_catboost_v1.0.0.json
│
├── src/
│   ├── app_2.py
│   │
│   ├── config/
│   │   └── settings.py
│   │
│   ├── data/
│   │   ├── database.py
│   │   ├── queries.py
│   │   └── repositories.py
│   │
│   ├── domain/
│   │   └── fuzzy_engine.py
│   │
│   ├── ml/
│   │   ├── feature_builder.py
│   │   ├── model_service.py
│   │   ├── prediction.py
│   │   └── validators.py
│   │
│   └── utils/
│
├── EOR_Screening_Tool_2026.xlsx
├── requirements.txt
└── README.md
```

---

## ⚙️ Installation

### 1. Clone the repository

```bash
git clone https://github.com/nasilemak80sen/eor_dashboard.git
cd eor_dashboard
```

### 2. Create a virtual environment

#### Windows

```bash
python -m venv .venv
.venv\Scripts\activate
```

#### Linux / macOS

```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

---

## ▶️ Running the Application

From the project root:

```bash
streamlit run src/app_2.py
```

The application will open in the browser at the Streamlit local URL.

---

## 📊 Data Sources

EOR Atlas uses several data sources.

### Engineering Screening Workbook

```text
EOR_Screening_Tool_2026.xlsx
```

Used for deterministic engineering screening and workbook-parity logic.

### Fuzzy Envelope Dataset

```text
data/NeuroFuzzy_EOR_Extracted_Tables.xlsx
```

Contains the extracted EOR suitability envelopes used by the fuzzy analysis layer.

### Historical / Application Data

The application can persist assessment and historical information through the SQLite database layer.

---

## 🤖 Machine Learning Model

The production ML artifact is a **CatBoost classifier**.

### Current model

```text
Model: CatBoost
Version: 1.0.0
Feature count: 17
Classes: 9
```

The model is loaded through a dedicated `ModelService`, which is responsible for:

1. Loading model artifacts
2. Validating artifact paths
3. Validating feature schema
4. Building engineered features
5. Running prediction
6. Generating ranked candidates
7. Returning structured prediction results

The UI does not directly interact with raw CatBoost objects.

---

## 🔐 ML / Engineering Boundaries

EOR Atlas intentionally separates machine learning from deterministic engineering logic.

### ML does NOT:

* Override critical engineering constraints
* Replace deterministic screening
* Automatically approve an EOR project
* Represent a field development decision

### ML DOES:

* Identify patterns in historical data
* Rank potential EOR techniques
* Provide probabilistic guidance
* Support engineering review

The final interpretation remains subject to reservoir engineering judgement and available field-specific data.

---

## ⚠️ Limitations

EOR Atlas is a **screening and decision-support platform**, not a full-field reservoir simulator or final project-design tool.

Results depend on:

* Input quality
* Historical data coverage
* Engineering assumptions
* Availability of field-specific laboratory and reservoir data
* Applicability of historical ML training patterns

ML predictions should therefore be interpreted as **decision-support evidence rather than deterministic recommendations**.

---

## 🔮 Future Development

Planned development areas include:

* Portfolio-scale EOR opportunity mapping
* Improved field and reservoir data integration
* Additional historical EOR datasets
* Expanded ML training data
* Model monitoring and validation
* Sensitivity analysis
* Batch reservoir screening
* Explainable ML
* Engineering evidence traceability
* Scenario-based EOR comparison
* Improved geospatial analytics

---

## 🎯 Engineering Philosophy

EOR Atlas follows an engineering-first philosophy:

> **Screen first. Understand the envelope. Use data-driven intelligence to support the decision.**

The platform is designed to make EOR screening more:

* Structured
* Repeatable
* Transparent
* Data-driven
* Scalable

while keeping engineering judgement at the centre of the decision process.

---

## 📄 Project Status

**Current Status: Operational Prototype / Development Release**

The Streamlit dashboard is operational with:

* Deterministic EOR screening
* Fuzzy suitability analysis
* Embedded CatBoost ML intelligence
* Workbook integration
* Database integration
* Interactive dashboard visualizations
* Cloud deployment support
---

## 📜 Disclaimer

This platform is intended for **screening, analytical support, and technical demonstration purposes**.
Outputs should be reviewed by qualified reservoir engineering and EOR specialists before being used in technical decisions, field development planning, or project execution.
