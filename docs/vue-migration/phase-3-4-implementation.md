# EOR Atlas migration: Phase 3–4 implementation

## Phase 3: API boundary
- Protected evaluation, history and readiness routes use configurable OIDC bearer verification.
- Production requires HTTPS issuer/JWKS, audience and an explicit required scope; JWT checks RS256, issuer, audience, expiry, issued-at and subject.
- Production OpenAPI docs are disabled. Wildcard CORS is rejected.
- API responses receive validated correlation IDs, no-store and browser security headers; error responses do not expose stack traces.
- Deployment still needs company-specific identity-provider registration, TLS, approved hosting/network boundaries and security review.

## Phase 4: history
- The history reader stays read-only and opens SQLite with `mode=ro`.
- Required summary schema is validated; optional inputs, evidence and version columns are returned when available.
- JSON-encoded evidence columns are decoded when possible, while legacy text is preserved.
- A history health endpoint reports configured/readable/schema-valid state and record count without exposing a local filesystem path.
- Writes and migrations remain disabled pending approval of authoritative database, retention/access rules, backup/restore plan and migration. No tracked database was modified.

## Validation
Tests are added for fail-closed production auth configuration and read-only history diagnostics/evidence decoding. Run the API and legacy regression workflows on the branch before treating the phase gates as passed.
