# EOR Atlas Vue frontend

Vue 3 + TypeScript UI for the existing FastAPI and Python engineering services. This is an internal-pilot preview, not a production deployment.

## Prerequisites

- Node.js 20 or newer and npm
- Python 3.13 recommended for the repository's current test environment
- PowerShell on Windows for the commands below

## 1. Quick visual preview

From the repository root:

```powershell
cd frontend
npm install
$env:VITE_EOR_API_BASE_URL = "http://127.0.0.1:8000"
npm run dev
```

Open **http://127.0.0.1:5173**. The UI can be explored while the API is stopped, but it will show an API-unreachable state and evaluation actions will not work until FastAPI is running.

## 2. Run the full local experience

Use four separate PowerShell terminals, all opened at the repository root unless a command says otherwise. Do not use the mock identity issuer outside local development.

### Terminal A: install backend dependencies

```powershell
python -m pip install -e ".\backend[test]"
python -c "import jwt, cryptography; print('PyJWT and Cryptography are ready')"
```

### Terminal B: start the local-only OIDC test issuer

```powershell
python tests\e2e_support\mock_oidc.py
```

Keep this terminal open. It serves a short-lived development token at **http://127.0.0.1:8081/token**. The private key is generated in memory and is not the corporate identity provider.

### Terminal C: start FastAPI

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) "src")
$env:EOR_ENV = "development"
$env:EOR_OIDC_ISSUER = "http://127.0.0.1:8081/"
$env:EOR_OIDC_AUDIENCE = "eor-atlas-e2e"
$env:EOR_OIDC_JWKS_URL = "http://127.0.0.1:8081/jwks"
$env:EOR_OIDC_REQUIRED_SCOPE = "eor.atlas.access"
$env:EOR_ALLOWED_ORIGINS = "http://127.0.0.1:5173"
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Keep this terminal open. In another tab, **http://127.0.0.1:8000/api/v1/health/live** should return a small JSON liveness response. Protected readiness and evaluation endpoints require a token.

### Terminal D: start Vue

```powershell
cd frontend
npm install
$env:VITE_EOR_API_BASE_URL = "http://127.0.0.1:8000"
npm run dev
```

Open **http://127.0.0.1:5173**. In the left sidebar, open **http://127.0.0.1:8081/token** in a separate browser tab, copy the value of `access_token` (not the surrounding JSON), paste it into the Bearer token field, then select **Check connection**. The local token expires after five minutes; refresh the token endpoint to get another.

## 3. Build and browser tests

From the repository root:

```powershell
cd frontend
npm run build
```

To run the authenticated browser tests, install Chromium once and make sure the mock OIDC issuer, FastAPI, and Vue server above are running:

```powershell
node ./node_modules/playwright/cli.js install chromium
$env:EOR_API_URL = "http://127.0.0.1:8000"
$env:EOR_TEST_OIDC_URL = "http://127.0.0.1:8081"
$env:EOR_FRONTEND_URL = "http://127.0.0.1:5173"
npm run test:e2e
```

If Chromium installation fails with `UNABLE_TO_GET_ISSUER_CERT_LOCALLY` on a company network, use the organization's approved proxy/CA configuration. Do **not** disable TLS certificate verification.

## Safety notes

- Prefilled reservoir numbers are illustrative UI inputs, not approved field data or an independent parity fixture.
- Engineering screening and hybrid calculations continue to run through the existing Python services.
- History is read-only. This Vue migration does not save new evaluations, create tables, migrate a database, or enable writes.
- OpenGlobus and production model promotion are separate workstreams. A successful UI build is not proof of engineering parity or production readiness.
