# Phase 5–6 live integration validation

## Purpose
The live end-to-end workflow boots the Vue dev server and the repository's FastAPI application in one CI job. It does not substitute for approved asset parity testing.

## Checks
- Browser sees the Vue application and can reach the live FastAPI liveness endpoint.
- Protected evaluation without a bearer token returns a surfaced 401 error.
- The workflow generates a short-lived RS256 bearer token from an ephemeral OIDC/JWKS fixture. The key pair is generated in memory each run; no signing key or production secret is committed.
- Valid token is accepted by the real FastAPI server for readiness and an engineering screening request using clearly illustrative UI defaults.
- Browser completes a hybrid evaluation through the actual backend's CatBoost/hybrid path where artifacts are available.
- Authenticated malformed inputs return a safe 422 `invalid_request` envelope with correlation ID and no traceback.
- A validly signed token without the required scope receives 403.
- Browser uncaught runtime errors are treated as failures.

## Limits
- The E2E smoke values are illustrative input data only. They verify wiring and server operation; they are not real-reservoir evidence and do not pass the approved-real-case parity gate.
- The OIDC server exists only for CI integration testing. It uses HTTP loopback and an ephemeral signing key, not a production IdP. It must never be deployed.
- Real field/asset cases must be provided through `tests/fixtures/approved_reservoir_cases.json` with `id`, `approved_by`, `approved_on`, `source`, `formation` and `inputs`; use an authorized, approved dataset. Do not add restricted reservoir data to a public repository without data-owner approval.
- Production still requires corporate OIDC registration and policy, HTTPS/TLS, approved hosting/network controls, repository artifact classification, and resolution of the known scikit-learn serialized-artifact/runtime mismatch.
