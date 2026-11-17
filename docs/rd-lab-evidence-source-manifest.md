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
