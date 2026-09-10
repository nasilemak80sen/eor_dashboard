"""Train the next engineering-aware EOR CatBoost model.

IMPORTANT:
    This pipeline requires a labelled historical dataset with an actual EOR
    technique target. ScreenTool outputs are deliberately NOT used as labels.

The current repository's v1 model remains the live compatibility model until
this richer labelled dataset is assembled and this trainer produces validated
v2 artifacts.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from catboost import CatBoostClassifier
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import StratifiedKFold
from sklearn.preprocessing import LabelEncoder

from ml.hybrid_feature_builder import FEATURE_NAMES, build_hybrid_features
from ml.hybrid_model_assessment import (
    assess_training_readiness,
    expected_calibration_error,
)

TARGET_COLUMN = "technique"
FORMATION_COLUMN = "formation_category"
GROUP_COLUMN = "Field"

DEFAULT_PARAMS = {
    "loss_function": "MultiClass",
    "eval_metric": "TotalF1:average=Macro",
    "iterations": 600,
    "depth": 6,
    "learning_rate": 0.04,
    "l2_leaf_reg": 4.0,
    "random_seed": 56,
    "verbose": False,
    "allow_writing_files": False,
}


def _load_dataset(path: Path) -> pd.DataFrame:
    if not path.is_file():
        raise FileNotFoundError(f"Training dataset not found: {path}")
    if path.suffix.lower() in {".xlsx", ".xls", ".xlsm"}:
        df = pd.read_excel(path, engine="openpyxl")
    elif path.suffix.lower() == ".csv":
        df = pd.read_csv(path)
    else:
        raise ValueError(f"Unsupported dataset format: {path.suffix}")
    if df.empty:
        raise ValueError("Training dataset is empty.")
    return df


def _validate_columns(df: pd.DataFrame) -> None:
    required = {TARGET_COLUMN, FORMATION_COLUMN}
    missing = sorted(required.difference(df.columns))
    if missing:
        raise ValueError(f"Training dataset is missing required columns: {missing}")


def build_training_matrix(df: pd.DataFrame) -> tuple[pd.DataFrame, np.ndarray, LabelEncoder]:
    _validate_columns(df)

    encoder = LabelEncoder()
    labels = encoder.fit_transform(df[TARGET_COLUMN].astype(str).str.strip())

    rows = []
    for _, row in df.iterrows():
        values = row.to_dict()
        rows.append(
            build_hybrid_features(
                values,
                str(row[FORMATION_COLUMN]),
            ).iloc[0].to_dict()
        )

    features = pd.DataFrame(rows, columns=FEATURE_NAMES)
    if features.isnull().any().any():
        raise ValueError("Hybrid feature matrix contains missing values.")
    return features, labels, encoder


def _class_weights(y: np.ndarray) -> dict[int, float]:
    counts = np.bincount(y)
    total = len(y)
    n_classes = len(counts)
    return {
        idx: float(total / max(n_classes * count, 1))
        for idx, count in enumerate(counts)
        if count > 0
    }


def cross_validate(
    X: pd.DataFrame,
    y: np.ndarray,
    params: dict[str, Any],
    *,
    groups: np.ndarray | None = None,
    folds: int = 5,
) -> dict[str, float | str]:
    """Run stratified validation and report performance plus calibration."""
    class_counts = np.bincount(y)
    nonzero = class_counts[class_counts > 0]
    if len(nonzero) == 0:
        raise ValueError("No training classes were found.")

    min_class = int(nonzero.min())
    actual_folds = min(folds, min_class)
    if actual_folds < 2:
        raise ValueError("At least two samples per class are required for stratified validation.")

    # Group-aware splitting is preferred when Field identifiers are available.
    if groups is not None and len(np.unique(groups)) >= actual_folds:
        try:
            from sklearn.model_selection import StratifiedGroupKFold

            splitter = StratifiedGroupKFold(
                n_splits=actual_folds,
                shuffle=True,
                random_state=56,
            )
            split_iterator = splitter.split(X, y, groups)
            split_method = "StratifiedGroupKFold"
        except ImportError:
            splitter = StratifiedKFold(
                n_splits=actual_folds,
                shuffle=True,
                random_state=56,
            )
            split_iterator = splitter.split(X, y)
            split_method = "StratifiedKFold"
    else:
        splitter = StratifiedKFold(
            n_splits=actual_folds,
            shuffle=True,
            random_state=56,
        )
        split_iterator = splitter.split(X, y)
        split_method = "StratifiedKFold"

    accuracies = []
    balanced_f1s = []
    calibration_errors = []

    for train_idx, test_idx in split_iterator:
        model_params = dict(params)
        model_params["class_weights"] = _class_weights(y[train_idx])
        model = CatBoostClassifier(**model_params)
        model.fit(X.iloc[train_idx], y[train_idx])

        pred = model.predict(X.iloc[test_idx]).reshape(-1).astype(int)
        probabilities = model.predict_proba(X.iloc[test_idx])

        accuracies.append(float(accuracy_score(y[test_idx], pred)))
        balanced_f1s.append(float(f1_score(y[test_idx], pred, average="macro", zero_division=0)))
        calibration_errors.append(float(expected_calibration_error(y[test_idx], probabilities)))

    return {
        "folds": float(actual_folds),
        "split_method": split_method,
        "accuracy_mean": float(np.mean(accuracies)),
        "accuracy_std": float(np.std(accuracies)),
        "macro_f1_mean": float(np.mean(balanced_f1s)),
        "macro_f1_std": float(np.std(balanced_f1s)),
        "ece_mean": float(np.mean(calibration_errors)),
        "ece_std": float(np.std(calibration_errors)),
    }


def train_and_save(
    dataset_path: Path,
    output_dir: Path,
    version: str = "2.0.0",
) -> dict[str, Any]:
    df = _load_dataset(dataset_path)
    X, y, encoder = build_training_matrix(df)

    if len(encoder.classes_) < 2:
        raise ValueError("At least two EOR technique classes are required.")

    readiness = assess_training_readiness(y, list(encoder.classes_), minimum_samples_per_class=5)
    if not readiness["ready"]:
        raise ValueError(
            "Training dataset does not meet minimum class-support requirements: "
            f"{readiness['sparse_classes']}"
        )

    groups = df[GROUP_COLUMN].astype(str).to_numpy() if GROUP_COLUMN in df.columns else None

    params = dict(DEFAULT_PARAMS)
    validation = cross_validate(X, y, params, groups=groups)

    final_params = dict(params)
    final_params["class_weights"] = _class_weights(y)
    final_model = CatBoostClassifier(**final_params)
    final_model.fit(X, y)

    output_dir.mkdir(parents=True, exist_ok=True)
    model_path = output_dir / f"eor_catboost_v{version}.joblib"
    encoder_path = output_dir / f"label_encoder_catboost_v{version}.joblib"
    config_path = output_dir / f"config_catboost_v{version}.json"

    joblib.dump(final_model, model_path)
    joblib.dump(encoder, encoder_path)

    config = {
        "model_name": "EOR Hybrid CatBoost",
        "version": version,
        "algorithm": "CatBoostClassifier",
        "feature_names": FEATURE_NAMES,
        "feature_count": len(FEATURE_NAMES),
        "classes": [str(x) for x in encoder.classes_],
        "training_rows": int(len(df)),
        "target_column": TARGET_COLUMN,
        "formation_column": FORMATION_COLUMN,
        "group_column": GROUP_COLUMN if GROUP_COLUMN in df.columns else None,
        "screening_gate_separate": True,
        "fuzzy_used_as_model_feature": False,
        "v3_features": [
            "sorw_pct",
            "movable_oil_saturation_pct",
            "produced_gor_log10",
            "gor_category",
        ],
        "parameters": params,
        "validation": validation,
        "training_readiness": readiness,
        "training_source": str(dataset_path),
        "warning": (
            "Validation statistics are meaningful only when labels are reliable, "
            "classes have sufficient support, and the split strategy reflects field-level generalization."
        ),
    }

    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return {
        "model": str(model_path),
        "encoder": str(encoder_path),
        "config": str(config_path),
        "validation": validation,
        "training_readiness": readiness,
        "classes": list(encoder.classes_),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the EOR Hybrid CatBoost model.")
    parser.add_argument("dataset", type=Path, help="Labelled historical EOR dataset (.xlsx/.csv).")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/model_artifacts"),
        help="Artifact output directory.",
    )
    parser.add_argument("--version", default="2.0.0", help="Model version label.")
    args = parser.parse_args()

    result = train_and_save(args.dataset, args.output_dir, args.version)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
