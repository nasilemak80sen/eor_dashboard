"""Model versioning helpers for the EOR Atlas ML lifecycle."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from data.queries import ModelVersionRepository


class ModelVersionTracker:
    """Persist and retrieve model metadata for screening runs."""

    def __init__(self, repository: Optional[ModelVersionRepository] = None):
        self.repository = repository or ModelVersionRepository()

    def register_version(
        self,
        version: str,
        algorithm: str = "Dense Neural Network",
        framework: str = "TensorFlow/Keras",
        test_accuracy: Optional[float] = None,
        test_weighted_f1: Optional[float] = None,
        training_samples: Optional[int] = None,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Register a trained model version in the database."""
        model_version = self.repository.register(
            version=version,
            algorithm=algorithm,
            framework=framework,
            test_accuracy=test_accuracy,
            test_weighted_f1=test_weighted_f1,
            training_samples=training_samples,
            description=description,
            training_date=datetime.utcnow(),
        )
        return {
            "id": model_version.id,
            "version": model_version.version,
            "algorithm": model_version.algorithm,
            "framework": model_version.framework,
            "test_accuracy": model_version.test_accuracy,
            "test_weighted_f1": model_version.test_weighted_f1,
            "training_date": model_version.training_date,
        }

    def get_active_version(self) -> Optional[Dict[str, Any]]:
        """Return active model metadata if present."""
        record = self.repository.get_active()
        if record is None:
            return None
        return {
            "id": record.id,
            "version": record.version,
            "algorithm": record.algorithm,
            "framework": record.framework,
            "test_accuracy": record.test_accuracy,
            "test_weighted_f1": record.test_weighted_f1,
        }

    def write_manifest(
        self,
        version: str,
        model_path: Path,
        scaler_path: Path,
        encoder_path: Path,
        config_path: Path,
        output_dir: Path,
    ) -> Path:
        """Write a lightweight version manifest JSON file."""
        manifest = {
            "version": version,
            "timestamp": datetime.utcnow().isoformat(),
            "model_path": str(model_path),
            "scaler_path": str(scaler_path),
            "encoder_path": str(encoder_path),
            "config_path": str(config_path),
        }
        manifest_path = output_dir / f"model_manifest_v{version}.json"
        with open(manifest_path, "w", encoding="utf-8") as handle:
            import json
            json.dump(manifest, handle, indent=2)
        return manifest_path
