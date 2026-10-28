# EOR Atlas API (migration scaffold)

This package establishes the API boundary for the Vue migration while reusing
the current Python engineering and hybrid services. It does not change model
training, rules, or the existing Streamlit UI.

## Setup

From the repository root, use the project's approved Python environment and
install the API extras:

```powershell
python -m pip install -e .\backend[test]
$env:PYTHONPATH = (Join-Path (Get-Location) "src")
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

The current execution modules still import Streamlit, so the existing
repository requirements must be installed for the compatibility adapter to
initialize. This is transitional; the domain/service layer should be extracted
from Streamlit before the API is considered fully independent.

## Endpoints

- `GET /api/v1/health/live`
- `GET /api/v1/health/ready`
- `POST /api/v1/screening/evaluate`
- `POST /api/v1/intelligence/evaluate`
- `GET /api/v1/history?limit=50&offset=0`
- `GET /api/v1/history/{run_id}`
- `GET /docs` (interactive OpenAPI documentation)

The evaluation request requires `formation` and an `inputs` object containing
the core numerical values. Optional ScreenTool context values are passed through
unchanged. The browser cannot set engineering eligibility or override gate
failures.

## History safety

History access is read-only and disabled unless `EOR_HISTORY_DB_PATH` points
to an existing, approved database file with the supported `screening_runs`
columns. The API does not create a DB, run migrations or write report cards.
This is intentional until the database owner confirms the authoritative source
and a migration/back-up/restore plan is approved.

## Internal deployment

Set `EOR_ENV`, `EOR_ALLOWED_ORIGINS`, `EOR_HISTORY_DB_PATH` and model/workbook
configuration using the company's approved deployment and secret-management
systems. The CORS setting is not authentication. Do not expose the API directly
to untrusted networks. Corporate SSO, backend authorization, TLS, logging,
dependency scanning, and approved storage must be completed before production.

## Tests

From `backend/` after installing the optional test dependencies:

```powershell
python -m pytest
```

The tests use injected fake services and temporary SQLite fixtures. They do not
load company data or modify the repository's tracked database.
