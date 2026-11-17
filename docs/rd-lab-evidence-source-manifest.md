# R&D Laboratory evidence source manifest

This manifest records the approved input boundary for the R&D Laboratory stabilization work. The Baronia workbook itself is deliberately excluded from this repository.

## St. Joseph CEOR

- Approved source: repository copy from `fix/restore-original-ceor-charts`.
- Source commit: `0338bcd904fea38f71724c6a67a6cdcdf272a5fa`.
- Git blob SHA: `61001208ab3c2b8611b194c295cff029a432614c`.
- Original filename: `St_Jos CEOR (Shared) (1).xlsx`.
- Active stabilization path: `data/St_Jos CEOR (Shared) (1).xlsx`.
- File size reported by the source Git tree: 7,021,017 bytes.
- Loader runtime computes SHA-256 and exposes it as `metadata.workbook_sha256`.
- Required worksheet and minimum column contracts are validated before any evidence is normalized.

This active-branch copy reuses the exact existing Git blob. It does not alter workbook contents. Do not replace it with an unreviewed upload; changes to this source should be reviewed as source-data changes.

## Baronia IWAG

- Approved source: Library-provided `WAG_Copy(1).xlsx`.
- Local verified SHA-256: `055252fc59121b32992cfd464cd50ec4ab166b2740501abe9e2b708d0b0af8d9`.
- Worksheet inventory: `EOR ATLAS Summary`, `Coreflood Recovery Data`, `Field Information`, `IWAG Results`, and `Core Analysis`.
- Local workbook size: 55,329 bytes.
- Keep the workbook outside GitHub. For local validation, configure `BARONIA_WAG_WORKBOOK` to point to the Library copy or upload it through the WAG workspace. Do not add it to `data/`, fixtures, workflow artifacts or commits.

The checksum and worksheet inventory identify the local test input without publishing the workbook. Future Baronia integration tests should be opt-in/local and should not require the workbook in public CI.

## Branch baseline

- Stabilization branch: `fix/rd-lab-evidence-stabilization`.
- Base branch: `main`.
- Base commit: `556935258058b1cca81b86164dfcb76b3efeaf71`.

All changes in this workstream are isolated to the stabilization branch. No changes are made to `main`.


## Phase 2 source reconciliation findings

These are observed in the approved Library workbook. The stabilization code exposes them as separate comparisons and does not rewrite the source values.

### Recovery evidence
- Coreflood summary: waterflood 64%, final recovery 87%, incremental recovery 23 percentage points.
- IWAG Results sheet: increment 17 percentage points, split into 12 points hysteresis and 5 points gas displacement.
- Recovery-by-cycle table: post-waterflood increments sum to 22 points.
- Recovery curve: 65% at 0.7 PV to 87% at 2.0 PV, implying 22 percentage points.

### Injection-volume evidence
- Design: 1.0 PV initial waterflood plus four cycles of 0.2 PV gas and 0.2 PV water = 2.6 PV.
- Material balance: 1.8 PV water plus 0.8 PV gas = 2.6 PV.
- Field Information total-fluid entry: approximately 2.0 PV.
- Coreflood summary total PV: 2.0 PV.
- Recovery-curve endpoint and production-curve endpoint: 2.0 PV.
- Recovery-curve waterflood endpoint: 0.7 PV, compared with the 1.0 PV design input. The observed post-waterflood span is 1.3 PV against 1.6 PV designed WAG slug volume.

### Injection-cycle evidence
- Four WAG cycles imply eight expected gas/water stage rows.
- The cycle table contains seven post-waterflood rows and does not contain a 4th Water Cycle row.
- The 4th Gas Cycle row begins at 1.9 PV, where the recovery curve labels the phase as 4th Water Slug.
- The loader compares cycle order, PV interval continuity and curve phase labels without changing the source table.

## Local validation using the Library input

The opt-in end-to-end test is intentionally skipped in public CI. The Baronia workbook must remain outside the repository.

Windows PowerShell:

```powershell
$env:BARONIA_WAG_WORKBOOK = "C:\path\outside\repository\WAG_Copy.xlsx"
$env:PYTHONPATH = "src"
python -m pytest -q tests/test_baronia_wag_evidence.py
streamlit run src/eor_atlas.py
```

macOS/Linux:

```bash
export BARONIA_WAG_WORKBOOK="/path/outside/repository/WAG_Copy.xlsx"
export PYTHONPATH=src
python -m pytest -q tests/test_baronia_wag_evidence.py
streamlit run src/eor_atlas.py
```

The expected SHA-256 is pinned in the local-only integration test. The workbook is read from the external path and is not copied into the repository, CI artifacts, or public workflow inputs.


## Phase 3 R&D experience refinement

- The WAG Data Quality tab starts with a compact reconciliation overview:
  - recovery claims in the order coreflood summary / IWAG Results / cycle sum;
  - design total versus recovery-curve endpoint;
  - expected versus present injection stages;
  - cycle-start phase/ordinal label conflicts.
- Total-PV evidence is visualized as a source comparison chart. Initial waterflood PV and post-waterflood span remain in the detailed table so unlike quantities are not mixed.
- Detailed recovery, PV, cycle and raw saturation tables are collapsed by default. The source QA findings remain visible.
- The WAG input message now makes the local/session-only boundary explicit. The app displays the workbook source mode and a short SHA-256 fingerprint.
- Slug-size captions are derived from the loaded design values. The malformed WAG Ratio cell remains withheld.

## Phase 3 local workbook review

The approved Library workbook was read directly and its source tables independently reconciled. Results:

- Design schedule: 1.0 PV initial waterflood + 4 × (0.2 PV gas + 0.2 PV water) = 2.6 PV.
- Material balance: 1.8 PV water + 0.8 PV gas = 2.6 PV.
- Field Information reports approximately 2.0 PV; coreflood summary and recovery/production curve endpoints are 2.0 PV.
- Recovery curve places the end of primary waterflood at 0.7 PV and 65% recovery; design says 1.0 PV for initial waterflood.
- Recovery-curve final recovery is 87%, giving 22 percentage points above its 65% curve waterflood endpoint.
- Post-waterflood injection-cycle increments sum to 22 percentage points. The cycle table contains seven post-waterflood stage rows against eight expected stages; the missing stage is the 4th Water Cycle.
- Reported cycle PV intervals are contiguous; the current workbook review found no gaps or overlaps.
- Five cycle start points disagree with the recovery-curve phase label or cycle ordinal. This is distinct from the missing-row issue and is surfaced separately in the UI.
- Recovery sources still report 23 pp (summary) and 17 pp (IWAG Results), versus 22 pp from cycle and curve arithmetic.

No source values were rewritten, estimated, rebased or designated as authoritative. These are review findings only. The local-only pytest integration test remains opt-in through `BARONIA_WAG_WORKBOOK`; public CI does not receive the Library workbook.


## Phase 4 regression and acceptance

Phase 4 is an acceptance gate, not a new evidence-normalization phase. Its purpose is to prove that the R&D Laboratory's existing source contracts, QA findings and navigation remain stable.

### Automated acceptance coverage

- `tests/test_rd_lab_app.py` uses Streamlit AppTest to exercise the CEOR default/all-fields view, the St. Joseph field-specific route, and the WAG method switch. It asserts the Fluid–Fluid and Fluid–Rock tabs and all four WAG workspace tabs render without Streamlit exceptions.
- `tests/test_baronia_wag_acceptance.py` verifies that an incomplete workbook is rejected at the required-worksheet boundary before normalization.
- `tests/test_ceor_evidence.py` retains the St. Joseph source-count regression checks for rheology, phase points, phase tests, IFT, adsorption, coreflood and Sor evidence.
- `tests/test_baronia_wag_evidence.py` retains synthetic recovery/PV/cycle QA tests and the opt-in exact Library workbook integration test.
- GitHub Actions runs the maintained Python regression set under `tests/` and `src/tests/` with `PYTHONPATH=.:src` and `pytest -q tests src/tests --ignore=tests/test_eor_atlas.py --ignore=tests/test_portfolio_globe.py --ignore=tests/test_screening_safety.py`.
- Three unrelated legacy suites are explicitly excluded from this R&D acceptance gate: `tests/test_eor_atlas.py` imports retired `src.config.FEATURES` and `src.config.EOR_TECHNIQUES` exports; `tests/test_portfolio_globe.py` expects a literal field name in the Plotly hover-template instead of checking the trace's `customdata`; and `tests/test_screening_safety.py` unpacks the old two-value `InputValidator.validate_inputs` return contract. These are separate test-maintenance items, not silently counted as passing.

### Exact Baronia Library workbook test

The Baronia workbook remains outside GitHub, CI inputs, fixtures and workflow artifacts. Run the pinned end-to-end test locally against the approved Library copy:

Windows PowerShell:

```powershell
$env:BARONIA_WAG_WORKBOOK = "C:\path\outside\repository\WAG_Copy.xlsx"
$env:PYTHONPATH = "src"
python -m pytest -q tests/test_baronia_wag_evidence.py

# Maintained repository regression suite (legacy test noted above is excluded)
$env:PYTHONPATH = ".;src"
python -m pytest -q tests src/tests --ignore=tests/test_eor_atlas.py
```

The local test checks the approved workbook SHA-256, worksheet inventory, independent recovery claims, PV evidence, missing cycle stage and five cycle/curve phase-label conflicts. Public CI skips this one test unless an external workbook path is explicitly supplied.

### Manual browser acceptance checklist

After starting the app with `streamlit run src/eor_atlas.py`:

1. Open R&D Laboratory from the main navigation.
2. In CEOR, verify All fields and St. Joseph can be selected and both Fluid–Fluid and Fluid–Rock tabs render.
3. In WAG, verify IWAG Performance, Injection & Model, Field & Core and Data Quality tabs render.
4. With no local Baronia path configured, verify the page explains the local/session-only upload path and does not save the upload to the repository.
5. With the approved workbook loaded, verify the source mode and SHA-256 fingerprint are visible and the Data Quality findings remain visible.
6. Confirm source disagreements remain separate: 17/22/23 percentage-point recovery claims; 2.0/2.6 PV totals; seven of eight expected WAG stages; five phase-label conflicts.
7. Confirm no source value is silently corrected, imputed, averaged or presented as authoritative.

### Phase 4 exit criteria

- Maintained repository regression suite and GitHub Actions are green; the excluded legacy test is documented as a separate migration item.
- Streamlit AppTest covers both methods, the St. Joseph field route and all R&D tabs without exceptions.
- The exact approved Baronia Library workbook integration test passes locally.
- Manual browser smoke review shows stable navigation, usable tabs and source/QA provenance.
- The Baronia workbook remains untracked and absent from repository history additions.
- No engineering evidence is silently rewritten and no unlike quantities are combined in visualizations.
