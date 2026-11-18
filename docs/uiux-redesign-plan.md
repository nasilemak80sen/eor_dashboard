# EOR Atlas UI/UX Revamp

## Approved direction
- Visual direction: **A — Enterprise Subsurface**
- Density: **Balanced**
- Navigation: **Persistent, grouped, collapsible sidebar**
- Canvas: light neutral workspace with deep teal navigation, PETRONAS teal accents, restrained lime highlights and consistent white surfaces.
- UX foundations: detail drawers, global search, evidence provenance and saved filters.

## Source baseline
- Repository: nasilemak80sen/eor_dashboard
- Implementation base: fix/rd-lab-evidence-stabilization
- Baseline revision: 3fb8ff5f23c930ed9afbd4bcb33c5ac723a24d93
- Feature branch: feat/eor-atlas-uiux-foundation
- Production entrypoint: src/eor_atlas.py

## Non-negotiable protection boundaries
This is a presentation-layer programme. Do not alter Excel Gate criteria, calculation order, result schema or service invocation; CatBoost artifacts, feature engineering, prediction probabilities or model loading; Decision Fusion weights, eligibility logic, engineering vetoes or ranking calculations; workbook loading, source reconciliation, database schemas or report-card persistence; existing chart definitions, chart data transformations, chart inputs, chart rendering calls or map data semantics; CEOR/WAG source attribution rules, field-unassigned evidence handling or data-quality findings.

New visual states must be derived from actual existing service or source metadata. Do not manufacture timestamps, readiness claims, source dates or engineering statuses.

## Phase 1 — Shared shell and reusable UX foundation

### Scope
1. Replace horizontal nine-button navigation with grouped sidebar navigation while preserving all existing route keys and the atlas_page session-state contract.
2. Set the sidebar to expanded on initial load; retain Streamlit's native collapse affordance.
3. Add global search across page destinations and the already-loaded portfolio register's Field/Reservoir values. Search results route to existing pages; a reservoir selection is handed to the existing Candidates detail selection.
4. Add a reusable right-column detail drawer component and use it for the Candidates reservoir snapshot.
5. Add reusable evidence-provenance cards and use them in CEOR and WAG views using loader-provided workbook, worksheet and hash metadata.
6. Add named candidate filter presets. Phase 1 stores these in Streamlit session state only; they are not shared or durable across sessions.
7. Establish common responsive shell styles and update shell-focused regression tests.

### Deliverables
- Grouped sidebar navigation and status section.
- Global search header.
- Reusable render_detail_drawer, render_evidence_provenance and render_saved_filter_controls primitives.
- Candidate saved-filter integration and detail-drawer integration.
- CEOR/WAG provenance integration.
- Updated shell tests.

### Acceptance criteria
- All nine existing routes still resolve using their original page keys.
- Service initialization remains cached and is not triggered by navigation/search.
- Search uses the workbook already loaded by the application shell; no duplicate workbook load is introduced.
- Candidate filters reapply the exact captured widget values.
- Provenance displays only metadata actually supplied by the evidence loader.
- Existing charts and map implementations remain unchanged.
- Screening and Hybrid submission-driven forms continue to execute only after explicit submission.
- Shell tests, UI import tests and relevant page tests pass.

## Phase 2 — Core engineering workspace layouts

### Phase 2.1 — Executive Overview visual benchmark
**Implemented on the feature branch; automated validation remains pending.**

- Rebalanced portfolio KPIs into three primary indicators (Fields, Reservoirs, RF Gap) and two supporting coverage indicators (Mapped fields, EOR methods).
- Replaced oversized readiness cards with compact workbook and coordinate availability states.
- Promoted the 3D portfolio map into a dedicated, always-visible workspace with its field-focus control immediately above it.
- Kept the existing OpenGlobus field payload, detail mapping, camera-height rules, 620px rendering height and quiet-marker option.
- Separated EOR method coverage from map controls and added a clear source-map interpretation note.
- Retained the existing RF Gap aggregation, Altair encodings, tooltip, chart height and rendering call; only page placement and explanatory hierarchy changed.
- Replaced the tabbed decision-journey table with direct workflow shortcuts to Candidates, EOR Screening and Hybrid Intelligence. These buttons only change the existing page route; they do not execute engineering or ML services.
- Added responsive styling for status rows, field-focus context and workflow action cards.

**Protection notes:** Workbook loading, KPI calculations, `_map_summary`, OpenGlobus rendering parameters, RF Gap aggregation and chart rendering semantics are preserved.

### Phase 2.2 — Candidates portfolio discovery
**Implemented on the feature branch; automated validation remains pending.**

- Aligned Candidates with the Executive Overview header and page hierarchy; removed the nested page tabs so the discovery workspace reads as one continuous portfolio experience.
- Reorganised filters into a compact portfolio control surface. Existing multiselects, engineering range sliders, saved-filter snapshots and widget/session-state keys are retained.
- Promoted filtered-population indicators into a clear portfolio snapshot. Reservoir and field counts are primary; STOIIP and CR volume potential are supporting descriptive measures, not suitability or screening scores.
- Promoted the reactive OpenGlobus candidate map into the primary discovery flow, using the same filtered candidate population and preserving its marker payload, detail mapping, field-focus behaviour and camera configuration.
- Kept the relationship scatter chart, axis/group controls and legend interaction intact, with the chart placed after the map as a complementary analytical view.
- Retained the reservoir register, selected-reservoir detail drawer, full engineering record and source/quality disclosure.
- Preserved the existing global-search reservoir hand-off and reset scope. No Excel Gate, fuzzy suitability, CatBoost, or Decision Fusion path is invoked by this page.

**Protection notes:** Candidate filtering arguments and widget keys remain unchanged. The scatter-chart implementation and both map renderers are not rewritten. The redesigned page changes hierarchy and placement only.

### Phase 2.3 — EOR Screening engineering workspace
**Implemented on the feature branch; automated validation remains pending.**

- Replaced the nested Reservoir Inputs / Engineering Gate tabs with a single guided page flow: reservoir context, explicit submit action, engineering result and audit-record status.
- Adopted the shared Engineering Workspace header, reset action, section hierarchy, KPI cards and workflow progression.
- Kept the existing form identifier `screening_reservoir_form`, the `screening` input prefix and the shared `render_eor_input_form("screening")` schema unchanged.
- Preserved the explicit `st.form_submit_button` boundary. The Excel Screening service invocation and `persist_engineering_run` call remain inside the existing `if submitted` handler and in the same order.
- Retained the `excel_screening_result` and `screening_last_run` session-state contracts, existing decision summary and `render_excel_screening_result` renderer.
- Clarified that this workspace runs the deterministic Excel Gate only; CatBoost and Decision Fusion remain in the separate Hybrid Intelligence workflow.
- Added source-level regression assertions for the guided layout, form contract, submit-only execution boundary, result summary and result renderer.

**Protection notes:** No Excel Gate criteria, calculation logic, service calls, result schema, input field keys, report-card persistence logic or Hybrid Intelligence code was changed.

### Phase 2.4 — Hybrid Intelligence decision workspace
**Implemented on the feature branch; automated validation remains pending.**

- Replaced the nested Reservoir Inputs / Hybrid Decision tabs with one guided page flow that retains the existing reservoir form and submit-driven execution boundary.
- Adopted the shared Engineering + Machine Learning header, reset action, workspace hierarchy, state KPIs and workflow progression.
- Kept the existing form identifier `hybrid_reservoir_form`, the `intel` form prefix, `_run_intelligence_from_current_inputs(services, inputs, formation)`, and the `eor_intelligence_result` / `intelligence_last_run` session-state contracts.
- Preserved `persist_hybrid_run(result)` after the existing hybrid execution function, inside the explicit `if submitted` handler.
- Split the result presentation into three separate layers: technique-level deterministic engineering gate outcomes, CatBoost class probabilities, and the final Decision Fusion recommendation/ranking.
- Explicitly label CatBoost values as class-level model probabilities, not engineering feasibility or eligibility. The gate section distinguishes PASS, CONDITIONAL and FAIL/FAIL (CRITICAL) outcomes.
- Clarified that Hybrid rank score is normalized over the displayed Top-N ranking and is not a CatBoost probability or an independent estimate of technical success.
- Kept the original `render_eor_intelligence_result` renderer available inside a collapsed detail expander for the full ScreenTool context, model information and fusion configuration.
- Added source-level regression assertions for layer separation, form keys, submit-only model execution and persistence, and the original result renderer.

**Protection notes:** No CatBoost feature engineering, model loading/inference, technique taxonomy mapping, Excel Gate execution, Decision Fusion weights, hard-failure exclusion, ranking calculation or report-card persistence implementation was changed.

### Remaining Phase 2 work
Phase 2 core engineering workspace layouts are implemented. Proceed to validation, responsive/accessibility review and release hardening before treating the redesign as regression-tested.

## Phase 3 — Knowledge and R&D workspaces
Redesign EOR Insights, Historical EOR, R&D Laboratory and Challenges & Lessons. Standardise source badges, evidence details, field-level context, report cards and register interactions. Keep shared vs field-attributed evidence visually distinct.

## Phase 4 — Governance, accessibility and release hardening
Redesign System & Model, apply responsive behaviour and keyboard/focus checks, test empty/error/loading states, review long tables, validate chart/map container stability, and run visual regression plus the full regression suite.

## Saved-filter persistence decision
Phase 1 presets are deliberately session-scoped to avoid introducing a new persistence mechanism or database change during a UI-only phase. Durable per-user or shared presets require a separate decision on identity, ownership, storage, schema and retention before implementation.

## Suggested validation commands
    python -m py_compile src/eor_atlas.py src/ui/navigation.py src/ui/app_shell.py src/ui/components.py src/candidate_analytics/ui.py src/pages_ui/rd.py
    PYTHONPATH=src pytest -q tests/test_ui_shell.py tests/test_candidate_analytics.py tests/test_rd_lab_app.py tests/test_rd_lab_evidence.py tests/test_ceor_evidence.py

## Evidence close-out review — 18 November 2026

### Approved Baronia IWAG workbook

- Approved Library workbook: `WAG_Copy.xlsx`; SHA-256 `055252fc59121b32992cfd464cd50ec4ab166b2740501abe9e2b708d0b0af8d9`.
- All five required worksheets are present. The workbook has 21 recovery-curve rows, 21 production-curve rows, and eight labelled injection-cycle rows.
- Independent source-table extraction confirms: design-derived total injection = 2.6 PV; material-balance water + gas = 2.6 PV; source-reported total fluid injected = approximately 2.0 PV; summary and curve endpoints = 2.0 PV; observed WAG span after the waterflood endpoint = 1.3 PV.
- Recovery evidence also conflicts: summary incremental recovery = 23 percentage points; IWAG Results increment = 17 points; cycle increments and the recovery-curve increment = 22 points. One expected stage (4th Water Cycle) is absent, and five cycle/curve phase labels conflict.
- The existing `test_approved_library_baronia_workbook_end_to_end` acceptance test encodes these source values and expects the discrepancies to remain visible. It was **not executed through the application loader in this environment**: Streamlit is not installed in this local runner, and the approved workbook is intentionally not committed to the repository. Do not report the loader acceptance test as passed until it is run with `BARONIA_WAG_WORKBOOK` set in a full application environment.

### Approved reservoir numeric reference

- Added `tests/fixtures/approved_reservoir_cases.json` from page 2 of the historical `eor_latest.pdf` Library snapshot, with a regression test that preserves the displayed input/output values and explicitly records undisclosed inputs as null.
- The screenshot reports OOIP = 111 MMstb, incremental recovery factor = 16.50%, and incremental CR = 56.84 MMstb. A simple OOIP × incremental-RF calculation gives 18.315 MMstb, a 38.525 MMstb difference from the displayed CR.
- This is a **review-required legacy reference**, not a pass/fail parity fixture for the current Hybrid Intelligence pipeline: key gate inputs are not visible and the source has no technique rows, CatBoost probabilities or Decision Fusion ranking. Current pipeline values must not be backfilled with Streamlit defaults and compared as though they were source facts.

### Browser interaction coverage

- Added a non-visual test bridge in the OpenGlobus iframe that dispatches the same renderer `lclick` event used by the entity picker.
- Expanded the Playwright browser check to select two distinct candidate reservoir entities, verify their individual detail-drawer identity and coordinates, close the drawer, click a legend-bound group and verify that the plotted reservoir population is filtered.
- These browser checks are committed but remain pending an actual CI browser run. A dispatched renderer event verifies the production selection handler; it is not a substitute for pixel-coordinate hit-testing by a physical pointer on the WebGL canvas.

