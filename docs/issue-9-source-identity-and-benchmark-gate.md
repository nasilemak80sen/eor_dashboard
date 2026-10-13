# Issue #9: Source identity review and production-model benchmark gate

Status: in progress. No model promotion is authorized by this document.

## Source-document findings

The authoritative source is the corrected Oil & Gas Journal **2014 worldwide EOR survey** PDF:

- Source: https://img.ogj.com/files/base/ebm/ogj/document/2014/05/content_dam_ogj_en_downloadables_survey_downloads_worldwide_eor_2014_leftcolumn_downloadable_140505ogj_world_eor_corrected_79_91.pdf
- The PDF identifies the survey and its tables on pages 1–13.
- Table E (PDF page 10 in the viewer, printed page 9) explicitly has columns **Country and area, Operator, Type/project, Field, Start date**. Several source rows contain a field name, for example Buracica, Rio Pojuca, Miranga, Carmopolis, Fazenda Alegre, Estreito, Alto do Rodrigues, Issaran, Emlichheim blocks, Duri, Schoonebeek, Ula, Magnus, Block E, Area 2102, and Bati Raman.
- The previous provenance builder treated the Table E Field cell as blank and stored its parsed field value as a project identifier. That interpretation is inconsistent with the source table layout. The builder now extracts the explicit Field value as `field_id`, leaves `project_id` blank unless an independent project identifier is evidenced, and retains ambiguous partial pay-zone fragments as unresolved.
- A regression test checks Table E field extraction against explicit rows from the PDF.
- The duplicate-name candidate **Salt Creek** must remain split: the source lists Anadarko Salt Creek in Wyoming and Occidental Salt Creek in Texas. Same spelling is not sufficient evidence to merge fields; operator and geography distinguish these records.

## What remains unresolved

1. The generated provenance workbook and CI audit must be regenerated from the corrected parser before reporting a new unresolved count or class support.
2. Partial fragments that contain only pay-zone/reservoir text and numeric values remain quarantined unless the source table unambiguously maps the exact row. Adjacent-row guessing is prohibited.
3. The 109 explicit-text and 70 source-section technique conflicts must retain the original structured label and raw source text. A source-adjudicated label may be recorded only when the exact source row and its technique column are confirmed; unsupported subtypes remain unresolved rather than being mapped to the nearest model class.
4. The six-confirmed-independent-fields-per-class gate is evaluated only after identity and label adjudication. A parser-derived ID, project name, pay zone, or duplicate source row is not an independent confirmed field.

## Production-model comparison blocker

The current production artifact manifest/config identifies the model as **EOR CatBoost v1.0.0**, with 17 features, 9 classes, and `training_rows: 526` from the same 624-row OGJ2014 workbook/sheet used by this research. The config does not contain the exact training record IDs, a training-data hash, or a reproducible fold assignment.

Consequently, scoring the existing artifact on folds drawn from this workbook would risk evaluating rows the model has already seen. That result would not be a valid held-out comparison. The current artifact must not be reported as fairly benchmarked until its training-row provenance is recovered and overlap is ruled out.

A defensible next comparison is one of:

- recover the exact training record IDs/data hash and evaluate the existing artifact only on source-reviewed, genuinely unseen fields; or
- benchmark a **fold-retrained production-compatible CatBoost recipe** against the research CatBoost, linear baseline, and DummyPrior on identical field-grouped splits, using the production 17-feature schema and documented parameters. Clearly label this as a retrained recipe comparison, not a test of the deployed artifact.

No promotion decision should be made from the current preliminary research metrics. The OGJ2014 table describes reported technique associations, not project success, recovery uplift, or economic value.
