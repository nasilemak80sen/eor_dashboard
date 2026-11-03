# EOR Atlas Vue migration: Phases 5–6

## Phase 5: Vue frontend foundation
- Added a Vue 3 + TypeScript + Vite application under frontend/.
- Added a typed API client for liveness/readiness, screening, hybrid intelligence and read-only history.
- API base URL is configured with VITE_EOR_API_BASE_URL; see frontend/.env.example.
- Bearer tokens remain in page memory and are not written to localStorage or sessionStorage.
- Added responsive styling and a frontend CI build/type-check workflow.
- The UI reports API correlation IDs when returned by the server.

## Phase 6: workflow integration
- Added a reservoir profile form for the current API contract: depth, pressure, temperature, viscosity, API gravity, permeability, porosity fraction/percentage, oil saturation and formation.
- Added engineering screening and hybrid intelligence requests against the existing FastAPI v1 routes.
- Results display engineering screening rows and, for hybrid evaluations, model metadata and a complete response inspector.
- Added read-only history browsing and API readiness indicators.
- No frontend-side engineering rules, model inference, database writes or model promotion were added.

## Safety and scope boundaries
- Backend remains authoritative for engineering eligibility, screening calculations, CatBoost inference and hybrid fusion.
- Engineering failure/veto must not be overridden by a probability or hybrid ranking in the interface.
- Prefilled values are illustrative test inputs only. They are not approved real-reservoir golden cases and do not satisfy the real-case parity gate.
- Bearer-token entry is a development integration seam, not corporate SSO. Do not paste production credentials into an unapproved browser environment.
- Production deployment still requires corporate OIDC integration, approved hosting/TLS/network controls, classification of repository workbook/database artifacts, reconciliation of the scikit-learn artifact/runtime warning, and approved real-reservoir parity cases.
- History remains read-only; the UI does not write evaluations or alter the database.

## Local development
PowerShell:
```powershell
cd frontend
Copy-Item .env.example .env
npm install
npm run dev
```

In a second terminal from repository root:
```powershell
python -m pip install -e .\backend[test]
$env:PYTHONPATH = (Join-Path (Get-Location) "src")
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

The frontend defaults to http://127.0.0.1:8000. Configure backend CORS for the frontend origin. Protected routes require a valid bearer token when authentication is enabled. Production must use the corporate identity provider and remain fail-closed.

## Validation
GitHub Actions runs TypeScript checking and a Vite production build. API/legacy regression workflows remain authoritative for backend behavior. Passing a frontend build does not prove live API parity; approved real-reservoir cases must be run through both the legacy Streamlit and Vue/API paths before accepting behavioral parity.
