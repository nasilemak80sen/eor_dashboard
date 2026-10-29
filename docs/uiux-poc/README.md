# EOR Atlas UI/UX proof of concept

## Decision and scope

This branch (`feat/uiux-poc-streamlit-vue`) prioritises interface design and workflow discovery. FastAPI is removed from this POC branch: Vue has no HTTP client, and the POC run instructions and CI do not start or install the API. The original API implementation remains intact on `feat/vue-migration-phases-0-4` for the Enterprise Digital Team handoff.

The POC contains two intentionally different experiences:

- **Streamlit POC:** uses the existing local Python engineering/ML services when the user explicitly submits the form. A local SQLite database is used only for local POC accounts. Screening and hybrid results stay in Streamlit session memory, the Historical page uses synthetic read-only rows, and this entrypoint does not use the engineering history database.
- **Vue POC:** a standalone UX prototype using synthetic fixtures only. It makes no API calls and does not connect to SQLite or run the Python engine. Scores, statuses, rankings, model details and sample history are labelled as illustrative.

The Vue browser cannot safely connect directly to a SQLite file. The Streamlit POC owns the local SQLite login flow; a real shared Vue login and API contract should be designed by the Enterprise Digital Team. This prototype is not enterprise authentication.

## Run the Vue prototype

Prerequisites: Node.js 20+ and npm.

From the repository root:

```powershell
cd frontend
npm install
npm run dev
```

Open http://127.0.0.1:5173. No FastAPI server, token, database or OIDC mock is needed.

## Run the Streamlit POC

Run from the repository root with the project's existing Python environment:

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) "src")
streamlit run src/eor_atlas_poc.py --server.address 127.0.0.1
```

The first visit asks you to create a local username and password. Username and password hashes are stored in a dedicated ignored file:

`.local/eor_atlas_poc_auth.sqlite3`

This file is separate from `eor_atlas.db`. No default account or password is shipped. Passwords are salted and hashed with PBKDF2-HMAC-SHA256. This is a development stepping stone only: no account recovery, roles, rate limiting, multi-user hosting controls or corporate SSO are provided. Keep the app bound to localhost and do not reuse production passwords.

If required dependencies are not installed in your current environment:

```powershell
python -m pip install -r requirements.txt
```

The POC does not create or migrate the engineering history schema. Screening/hybrid calculations are not saved, and the POC Historical page shows synthetic examples instead of querying the existing history database. Only the separate local account database is written.

## Validate the POC

Vue production build:

```powershell
cd frontend
npm run build
```

Vue browser tests (Chromium required; Playwright starts Vite automatically):

```powershell
node ./node_modules/playwright/cli.js install chromium
npm run test:e2e
```

Python auth and UI-shell checks from the repository root:

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) "src")
python -m pytest -q tests/test_local_auth_poc.py tests/test_uiux_poc_boundaries.py tests/test_ui_shell.py
```

On a company network, use the approved proxy/CA configuration if Chromium download fails due to TLS certificate trust. Do not disable TLS verification.

## Out of scope and handoff

1. FastAPI endpoint design, implementation and deployment.
2. Enterprise OIDC/SSO, role mapping, authorization policies and audit requirements.
3. Shared login contract between Vue and Streamlit.
4. Production persistence, writes, migration of engineering history and database lifecycle.
5. Real-case parity approval, model promotion and production acceptance.
6. OpenGlobus changes.

The POC goal is to review navigation, form groups, validation, decision presentation, history browsing, local access flow and user feedback before the Enterprise Digital Team defines the service/API integration. Green UI checks do not certify engineering parity or production readiness.
