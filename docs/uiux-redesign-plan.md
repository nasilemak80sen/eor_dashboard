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

### Remaining Phase 2 work
Redesign Candidates, EOR Screening and Hybrid Intelligence page hierarchy and action placement. Preserve all current widgets, filters, form keys, service paths, charts and result semantics. Add contextual navigation from candidate discovery to screening only where existing page state can support it safely.

## Phase 3 — Knowledge and R&D workspaces
Redesign EOR Insights, Historical EOR, R&D Laboratory and Challenges & Lessons. Standardise source badges, evidence details, field-level context, report cards and register interactions. Keep shared vs field-attributed evidence visually distinct.

## Phase 4 — Governance, accessibility and release hardening
Redesign System & Model, apply responsive behaviour and keyboard/focus checks, test empty/error/loading states, review long tables, validate chart/map container stability, and run visual regression plus the full regression suite.

## Saved-filter persistence decision
Phase 1 presets are deliberately session-scoped to avoid introducing a new persistence mechanism or database change during a UI-only phase. Durable per-user or shared presets require a separate decision on identity, ownership, storage, schema and retention before implementation.

## Suggested validation commands
    python -m py_compile src/eor_atlas.py src/ui/navigation.py src/ui/app_shell.py src/ui/components.py src/candidate_analytics/ui.py src/pages_ui/rd.py
    PYTHONPATH=src pytest -q tests/test_ui_shell.py tests/test_candidate_analytics.py tests/test_rd_lab_app.py tests/test_rd_lab_evidence.py tests/test_ceor_evidence.py
