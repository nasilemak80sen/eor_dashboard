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
