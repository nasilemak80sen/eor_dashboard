# EOR Atlas Vue UI/UX POC

This folder is a **local-only interaction prototype**. It deliberately does not call FastAPI, access SQLite, run engineering rules, or invoke the CatBoost model. Screening and hybrid results are synthetic fixtures labelled in the UI so workflows can be reviewed without confusing a mock result with an engineering decision.

## Run the Vue prototype

Prerequisites: Node.js 20+ and npm.

From the repository root:

```powershell
cd frontend
npm install
npm run dev
```

Open **http://127.0.0.1:5173**. No API server, bearer token, database, or external identity provider is needed. You can explore Engineering Screening, Hybrid Intelligence, advanced input groups, validation, result layouts and example history.

## Run UI checks

From the `frontend` directory:

```powershell
npm run build
```

To run the Playwright browser checks, install Chromium once, then run the tests:

```powershell
node ./node_modules/playwright/cli.js install chromium
npm run test:e2e
```

The Playwright config starts the Vite development server automatically. On a company network, use the approved proxy/CA configuration if browser installation fails with a certificate error. Do not disable TLS certificate verification.

## Authentication boundary

The Vue prototype is intentionally open for UI review and does not implement authentication. The local SQLite-backed account flow is implemented in the separate Streamlit POC. A shared browser authentication design and enterprise identity integration should be defined by the Enterprise Digital Team; browser code must not connect directly to SQLite.

## Safety boundary

- Prefilled values, scores, rankings, model details and history rows are synthetic UI fixtures.
- The Vue POC does not call the Python engine or any backend.
- This is not an engineering calculator, a model benchmark, or production-ready software.
