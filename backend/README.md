# EOR Atlas API

Versioned FastAPI boundary for the Vue 3 + TypeScript client. Engineering screening, CatBoost inference and hybrid fusion remain server-side in shared Python services.

## Setup (PowerShell)
```powershell
python -m pip install -e .\backend[test]
$env:PYTHONPATH = (Join-Path (Get-Location) "src")
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

## Endpoints
- `GET /api/v1/health/live` (minimal liveness, public)
- `GET /api/v1/health/ready` (identity required)
- `POST /api/v1/screening/evaluate` (identity required)
- `POST /api/v1/intelligence/evaluate` (identity required)
- `GET /api/v1/history?limit=50&offset=0` (identity required)
- `GET /api/v1/history/health` (identity required)
- `GET /api/v1/history/{run_id}` (identity required)
- `GET /docs` (development only; disabled in production)

## Identity and Phase 3
Configure corporate OIDC values through the approved deployment configuration system:
- `EOR_ENV=production`
- `EOR_OIDC_ISSUER`: exact issuer URI
- `EOR_OIDC_AUDIENCE`: registered API audience
- `EOR_OIDC_JWKS_URL`: trusted HTTPS JWKS endpoint
- `EOR_OIDC_REQUIRED_SCOPE`: required API scope
- `EOR_ALLOWED_ORIGINS`: exact comma-separated Vue origins

Bearer tokens are verified with RS256, issuer, audience, expiry, issued-at and subject checks. Production fails closed if identity configuration is missing, issuer/JWKS URLs are not HTTPS, or required scope is absent. CORS is not authentication. Identity-provider registration, TLS, network controls, role policy, secret rotation and security review remain deployment-owner tasks.

## History and Phase 4
Set `EOR_HISTORY_DB_PATH` to an existing database approved by the data owner. SQLite opens in `mode=ro`; the reader validates required summary columns, returns optional evidence/version fields when present, decodes JSON evidence, and reports health without exposing the local path.

No history writes, migrations, DB creation or tracked database replacement are enabled. The data owner must confirm the authoritative source, retention/access rules, backup/restore plan and migration approval before write support is designed.

## Safety and tests
The browser cannot override engineering eligibility. API responses include correlation IDs, no-store and browser security headers, and safe error envelopes. Classify tracked workbook/database artifacts before internal deployment.

```powershell
python -m pip install -e .\backend[test]
$env:PYTHONPATH = (Join-Path (Get-Location) "src")
python -m pytest backend/tests
```
