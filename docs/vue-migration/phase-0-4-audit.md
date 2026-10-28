# EOR Atlas Vue migration: phases 0–4 baseline audit

**Base branch:** `fix/openglobus-restore-after-revert`  
**Base commit inspected:** `ecf46deb490e73e5baee1cb37116571c466b71cd`  
**Migration branch:** `feat/vue-migration-phases-0-4`

## Scope

This audit supports a Vue 3 + TypeScript frontend and FastAPI backend while preserving existing Python screening, CatBoost, hybrid decision fusion, history, and OpenGlobus. It does not promote a model or change the engineering rules.

## Findings from the inspected branch

- The recommended Streamlit shell is `src/eor_atlas.py`; it delegates UI execution to `src/hybrid_app.py` and the legacy-compatible `src/app_2.py`.
- The production path is documented as Excel Gate → CatBoost → Decision Fusion. The deterministic engineering gate remains authoritative.
- `src/hybrid_app.py` exposes `initialize_services()`, `run_eor_intelligence(...)`, and `_app.ExcelScreeningService().screen(...)` as the most direct current seams for a first API adapter.
- `src/ml/hybrid_intelligence.py` contains the production fusion service and the mapping from CatBoost classes to ScreenTool technique names.
- `src/data/database.py` contains SQLAlchemy models and uses `config.settings.settings` to select `eor_atlas.db`. `src/data/screening_history.py` persists engineering and hybrid report cards.
- Existing tests include `tests/test_hybrid_intelligence.py`, `tests/test_eor_atlas.py`, `tests/test_historical_studies.py`, and `tests/test_database_migration.py`. They should remain the regression baseline.
- Streamlit is imported by current execution modules. The first API adapter therefore uses a compatibility seam; full UI-independent domain extraction remains a follow-up before declaring the backend completely independent of Streamlit.

## Security and data governance finding

The GitHub repository metadata reports **public visibility**. The inspected branch root includes `EOR_Screening_Tool_2026.xlsx`, `Platform.xlsx`, `eor_atlas.db`, and `eor_atlas_corrupted.db`; the `data/` folder also contains workbooks, datasets and report artifacts. This audit has not inspected the binary contents and does not conclude that any specific file contains confidential data.

Before internal deployment, the repository owner must classify these assets and confirm distribution approval. If restricted data is present, follow the organization's incident and repository-history cleanup process and relocate approved runtime data to controlled storage. Do not assume deleting a file from the latest commit removes it from Git history.

## Phase 0 exit status

- [x] Exact base branch and commit recorded.
- [x] Current service seams and test files identified.
- [x] Public visibility and binary data exposure flagged.
- [ ] Business/data owner confirms classification and authoritative database.
- [ ] Platform owner confirms SSO, hosting, and database requirements.

## Phase 1 parity baseline

Use synthetic or approved anonymized cases only. Capture exact request inputs, formation, engineering gate rows, CatBoost probability vector, hybrid ranking, model artifact identifier, feature schema, and rule version. Do not use guessed model outputs as golden results.

## Phase 2 extraction boundary

The adapter introduced in this migration branch deliberately isolates API routes from Streamlit page state. Existing modules still import Streamlit, so this is a compatibility bridge rather than the final pure-domain package. The next extraction should move `ExcelScreeningService`, model invocation and persistence into UI-independent modules, preserving the current behavior through golden-case tests.

## Phase 3 API boundary

- Version all endpoints under `/api/v1`.
- Validate numerical inputs and keep engineering decisions server-side.
- Expose liveness and readiness separately.
- Keep model files, workbook paths, DB paths and exception tracebacks out of HTTP responses.
- Do not allow the browser to override eligibility or the hard-veto result.

## Phase 4 history boundary

- Treat the current DB path as an unverified default until the data owner confirms the source of truth.
- The API history reader is read-only and must be explicitly configured with `EOR_HISTORY_DB_PATH`.
- Do not automatically migrate, create, or write to repository-tracked databases at API startup.
- Before enabling writes, compare schemas and record counts, create a verified backup, implement a versioned migration, and test restore against a copy.

## Acceptance before proceeding to Vue implementation

1. Existing Python regression tests pass in a repository checkout with the pinned dependencies.
2. API contract tests pass without loading real company data or a production model.
3. A local smoke test with approved assets confirms the adapter imports and initializes.
4. Golden-case parity is documented and any differences are resolved.
5. Database authority and repository asset classification are signed off.
