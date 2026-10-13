"""Reconstruct CatBoost v1.0.0 training-row membership from its historical source.

This is a provenance reconstruction, not a training run. It verifies the historical
notebook/config/artifact commit, replays the old row filters, and cross-checks that
the current workbook's original 15 columns remain cell-identical.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
from collections import Counter
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
TRAINING_COMMIT = "21a3f0aa18b9acfe5cb59e810015478a6e4c7fbb"
HISTORICAL_WORKBOOK_PATH = "src/notebooks/ml_data/OGJ2014_extracted_vs_Table1.xlsx"
CURRENT_WORKBOOK = ROOT / HISTORICAL_WORKBOOK_PATH
HISTORICAL_CONFIG_PATH = "outputs/model_artifacts/config_catboost_v1.0.0.json"
ARTIFACT_GIT_PATH = "outputs/model_artifacts/eor_catboost_v1.0.0.joblib"
ARTIFACT_PATH = ROOT / ARTIFACT_GIT_PATH
MANIFEST_PATH = ROOT / "data" / "provenance" / "catboost_v1.0.0_training_manifest.csv"
REPORT_PATH = ROOT / "data" / "provenance" / "catboost_v1.0.0_training_membership.json"
EXPECTED_TRAINING_ROWS = 526
SHEET = "OGJ2014_Extracted_Rows"
REQUIRED = [
    "technique", "formation", "depth_min", "depth_max", "por_min", "por_max",
    "perm_min", "perm_max", "api_min", "api_max", "visc_min", "visc_max",
    "so_min", "so_max",
]
COLUMN_ALIASES = {
    "technique": ["EOR technique", "EOR Technique", "technique", "Technique", "EOR_Technique", "EOR Method", "Method"],
    "formation": ["Formation type", "formation_category", "Formation", "Formation Type", "Rock Type", "rock_type"],
    "depth_min": ["Depth min (ft)", "depth_min_ft", "Depth_min_ft", "depth_min"],
    "depth_max": ["Depth max (ft)", "depth_max_ft", "Depth_max_ft", "depth_max"],
    "por_min": ["Porosity min (%)", "porosity_min_pct", "por_min"],
    "por_max": ["Porosity max (%)", "porosity_max_pct", "por_max"],
    "perm_min": ["Permeability min (mD)", "perm_min_md", "permeability_min_md", "perm_min"],
    "perm_max": ["Permeability max (mD)", "perm_max_md", "permeability_max_md", "perm_max"],
    "api_min": ["Oil gravity min (°API)", "api_min", "API min", "oil_api_min"],
    "api_max": ["Oil gravity max (°API)", "api_max", "API max", "oil_api_max"],
    "visc_min": ["Oil viscosity min (cp)", "visc_min_cp", "viscosity_min_cp", "visc_min"],
    "visc_max": ["Oil viscosity max (cp)", "visc_max_cp", "viscosity_max_cp", "visc_max"],
    "so_min": ["So at start min (%)", "so_start_min_pct", "so_min"],
    "so_max": ["So at start max (%)", "so_start_max_pct", "so_max"],
}


def git_bytes(spec: str) -> bytes:
    result = subprocess.run(
        ["git", "show", spec],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout


def normalize_cell(value):
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def row_payload(values) -> bytes:
    return json.dumps(
        [normalize_cell(value) for value in values],
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def matrix_sha256(rows) -> str:
    digest = hashlib.sha256()
    for row in rows:
        digest.update(row_payload(row))
        digest.update(b"\n")
    return digest.hexdigest()


def sheet_matrix(path: Path) -> tuple[list[str], list[list[object]]]:
    book = load_workbook(path, data_only=True, read_only=True)
    if SHEET not in book.sheetnames:
        raise ValueError(f"{path}: source sheet {SHEET!r} missing")
    sheet = book[SHEET]
    values = [[cell for cell in row] for row in sheet.iter_rows(values_only=True)]
    book.close()
    if not values:
        raise ValueError(f"{path}: source sheet is empty")
    return [str(value) if value is not None else "" for value in values[0]], values


def find_column(columns: list[str], aliases: list[str]) -> str:
    exact = {str(value).strip().casefold(): str(value) for value in columns}
    for alias in aliases:
        if alias.strip().casefold() in exact:
            return exact[alias.strip().casefold()]
    def normalize(value: str) -> str:
        import re
        return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")
    normalized = {normalize(value): value for value in columns}
    for alias in aliases:
        if normalize(alias) in normalized:
            return normalized[normalize(alias)]
    raise ValueError(f"Could not find any alias {aliases!r} in source columns {columns!r}")


def historical_cleaning_mask(source_df: pd.DataFrame) -> tuple[pd.DataFrame, list[int]]:
    """Replay historic standardize_training_table row filtering (not modern cleanup)."""
    out = pd.DataFrame(index=source_df.index)
    for name, aliases in COLUMN_ALIASES.items():
        source_column = find_column([str(value) for value in source_df.columns], aliases)
        out[name] = source_df[source_column]
    for column in REQUIRED:
        if column not in {"technique", "formation"}:
            out[column] = pd.to_numeric(out[column], errors="coerce")
    out["technique"] = out["technique"].astype(str).str.strip()
    out["formation"] = out["formation"].astype(str).str.strip().replace({
        "Carbonate": "Carbonates",
        "Unconsolidated Sand": "Unconsolidated sands",
    })
    out = out.replace([float("inf"), float("-inf")], float("nan")).dropna(subset=REQUIRED).copy()
    for low, high in [
        ("depth_min", "depth_max"), ("por_min", "por_max"), ("perm_min", "perm_max"),
        ("api_min", "api_max"), ("visc_min", "visc_max"), ("so_min", "so_max"),
    ]:
        out = out[out[high] >= out[low]]
    return out, [int(index) for index in out.index]


def make_record_ids(original_rows: list[list[object]]) -> list[str]:
    counts: Counter[str] = Counter()
    ids = []
    for values in original_rows[1:]:
        content = "\x1f".join("" if value is None else str(value) for value in values[:15])
        key = hashlib.sha256(content.encode("utf-8")).hexdigest()[:12]
        counts[key] += 1
        ids.append(f"REC-{key}-{counts[key]:02d}")
    return ids


def main() -> None:
    if not CURRENT_WORKBOOK.is_file():
        raise FileNotFoundError(CURRENT_WORKBOOK)
    historic_workbook_bytes = git_bytes(f"{TRAINING_COMMIT}:{HISTORICAL_WORKBOOK_PATH}")
    historic_config_bytes = git_bytes(f"{TRAINING_COMMIT}:{HISTORICAL_CONFIG_PATH}")
    historic_artifact_bytes = git_bytes(f"{TRAINING_COMMIT}:{ARTIFACT_GIT_PATH}")
    current_artifact_bytes = ARTIFACT_PATH.read_bytes()
    current_config_bytes = (ROOT / HISTORICAL_CONFIG_PATH).read_bytes()

    config = json.loads(historic_config_bytes.decode("utf-8"))
    if int(config.get("training_rows", -1)) != EXPECTED_TRAINING_ROWS:
        raise ValueError(f"Historical config says unexpected training count: {config.get('training_rows')}")
    source_config = config.get("training_source", {})
    if source_config.get("sheet") != SHEET or source_config.get("rows") != 624:
        raise ValueError(f"Historical config source differs from expected OGJ source: {source_config}")
    if current_artifact_bytes != historic_artifact_bytes:
        raise ValueError("Current production model artifact bytes differ from the historical v1.0.0 artifact.")
    if current_config_bytes != historic_config_bytes:
        raise ValueError("Current production v1.0.0 config differs from historical training config.")

    with tempfile.TemporaryDirectory(prefix="eor-catboost-v1-provenance-") as directory:
        historic_path = Path(directory) / "historic_ogj2014.xlsx"
        historic_path.write_bytes(historic_workbook_bytes)
        source_df = pd.read_excel(historic_path, sheet_name=SHEET, engine="openpyxl")
        retained, kept_indices = historical_cleaning_mask(source_df)
        historical_headers, historical_rows = sheet_matrix(historic_path)

    current_headers, current_rows = sheet_matrix(CURRENT_WORKBOOK)
    if historical_headers != current_headers[:15]:
        raise ValueError("Current workbook's first 15 source headers differ from the historic training source.")
    if len(historical_rows) != len(current_rows):
        raise ValueError("Current workbook source row count differs from historical training source.")
    mismatches = []
    for index, (historic_row, current_row) in enumerate(zip(historical_rows, current_rows), start=1):
        for column in range(15):
            if historic_row[column] != current_row[column]:
                mismatches.append((index, column + 1, historic_row[column], current_row[column]))
                if len(mismatches) >= 5:
                    break
        if mismatches:
            break
    if mismatches:
        raise ValueError(f"Original 15 source columns are not cell-identical: {mismatches}")
    historic_matrix_hash = matrix_sha256(historical_rows)
    current_source_matrix_hash = matrix_sha256([row[:15] for row in current_rows])
    if historic_matrix_hash != current_source_matrix_hash:
        raise ValueError("Historical/current original source-matrix SHA-256 values do not match.")

    if len(kept_indices) != EXPECTED_TRAINING_ROWS:
        raise ValueError(
            f"Historic preprocessing reproduced {len(kept_indices)} rows, expected {EXPECTED_TRAINING_ROWS}. "
            "Do not claim recovered production membership."
        )

    ids = make_record_ids(historical_rows)
    current_ids = []
    # The current workbook provides occurrence-aware record IDs derived from the same
    # first 15 original cell values. Verify against the current appended ID column.
    current_book = load_workbook(CURRENT_WORKBOOK, data_only=True, read_only=True)
    current_sheet = current_book[SHEET]
    headers = [cell.value for cell in current_sheet[1]]
    if "record_id" in headers:
        id_column = headers.index("record_id") + 1
        current_ids = [current_sheet.cell(row=index + 2, column=id_column).value for index in range(len(ids))]
    current_book.close()
    if current_ids and any(str(a) != str(b) for a, b in zip(ids, current_ids)):
        # Excel/OpenPyXL vs pandas string conversions can differ for numeric cell
        # representations. Record IDs are reproducibly generated from the original
        # workbook's cell payload, so fail closed rather than inventing an alignment.
        raise ValueError("Reconstructed record IDs do not match the IDs published in the current workbook.")
    record_ids = current_ids if current_ids else ids
    train_ids = [record_ids[index] for index in kept_indices]
    train_rows = [historical_rows[index + 1] for index in kept_indices]
    row_hashes = [hashlib.sha256(row_payload(row[:15])).hexdigest() for row in train_rows]

    manifest = pd.DataFrame({
        "record_id": train_ids,
        "source_excel_row": [index + 2 for index in kept_indices],
        "source_row_sha256": row_hashes,
        "original_technique_label": [str(source_df.iloc[index][find_column(list(map(str, source_df.columns)), COLUMN_ALIASES["technique"])]) for index in kept_indices],
        "retained_by_historical_cleaner": True,
    })
    manifest = manifest.sort_values("source_excel_row")
    member_digest = hashlib.sha256(("\n".join(manifest["record_id"].astype(str)) + "\n").encode("utf-8")).hexdigest()
    dataset_matrix_digest = matrix_sha256(historical_rows)
    report = {
        "status": "reconstructed_and_verified",
        "interpretation": (
            "The original training notebook did not persist row IDs. Membership has been reconstructed by "
            "replaying its historical standardization/filter rules against the exact historical source workbook, "
            "then verified against the current workbook's unchanged original 15 columns. This is a provenance "
            "reconstruction, not a claim that the model internally stored these row IDs."
        ),
        "production_model": config.get("model_name"),
        "production_model_version": config.get("version"),
        "training_commit": TRAINING_COMMIT,
        "training_workbook_path": HISTORICAL_WORKBOOK_PATH,
        "training_sheet": SHEET,
        "training_rows_expected": EXPECTED_TRAINING_ROWS,
        "training_rows_reconstructed": len(manifest),
        "historic_source_workbook_sha256": hashlib.sha256(historic_workbook_bytes).hexdigest(),
        "historical_source_git_blob_sha": subprocess.check_output(
            ["git", "rev-parse", f"{TRAINING_COMMIT}:{HISTORICAL_WORKBOOK_PATH}"], cwd=ROOT, text=True
        ).strip(),
        "historical_source_matrix_sha256": dataset_matrix_digest,
        "current_original_15_column_matrix_sha256": matrix_sha256([row[:15] for row in current_rows]),
        "current_original_15_columns_cell_identical": True,
        "historical_and_current_source_matrix_hashes_match": matrix_sha256(historical_rows) == matrix_sha256([row[:15] for row in current_rows]),
        "historical_config_sha256": hashlib.sha256(historic_config_bytes).hexdigest(),
        "historical_model_artifact_sha256": hashlib.sha256(historic_artifact_bytes).hexdigest(),
        "current_model_artifact_sha256": hashlib.sha256(current_artifact_bytes).hexdigest(),
        "historical_model_artifact_git_blob_sha": subprocess.check_output(
            ["git", "rev-parse", f"{TRAINING_COMMIT}:{ARTIFACT_GIT_PATH}"], cwd=ROOT, text=True
        ).strip(),
        "current_model_artifact_git_blob_sha": subprocess.check_output(
            ["git", "rev-parse", f"HEAD:{ARTIFACT_GIT_PATH}"], cwd=ROOT, text=True
        ).strip(),
        "training_membership_sha256_ordered_record_ids": member_digest,
        "training_row_manifest_path": str(MANIFEST_PATH.relative_to(ROOT)),
        "training_record_ids_stored_by_original_artifact": False,
        "training_recipe_source": "eor_ml_research_layer/notebooks/05_export_artifact.ipynb at the training commit",
        "historical_preprocessing_replay": (
            "Alias-normalize the original 15-column sheet, convert the 12 numeric endpoints, replace infinities "
            "with missing values, drop rows with missing required technique/formation/range values, and retain only "
            "rows for which each min <= max. No row deduplication or numeric-profile merge."
        ),
        "no_model_file_modified": True,
    }
    if report["historical_model_artifact_sha256"] != report["current_model_artifact_sha256"]:
        raise ValueError("Historical and current artifact SHA-256 values differ.")
    if report["historical_model_artifact_git_blob_sha"] != report["current_model_artifact_git_blob_sha"]:
        raise ValueError("Historical and current artifact Git blob IDs differ.")

    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    manifest.to_csv(MANIFEST_PATH, index=False, encoding="utf-8-sig")
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
