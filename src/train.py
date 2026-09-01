"""
EOR Atlas ML Model Training Script

Implements reproducible, versioned training pipeline for the EOR screening neural network.

Usage:
    python train.py --config config.yaml --output model_v1.0
    
Key Features:
- Reproducible with fixed random seeds
- Full training/validation/test split tracking
- Model checkpointing and version control
- Comprehensive performance metrics
- Hyperparameter logging
"""

import json
import logging
from pathlib import Path
from typing import Dict, Tuple, Optional
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
import joblib

# Local imports
from ml.feature_engineering import FeaturePipeline, DataPreprocessor
from ml.model_assessment import ModelAssessment, CalibrationAnalysis
from ml.model_versioning import ModelVersionTracker
from config.settings import settings
from utils.logging_config import logger

# Set random seeds for reproducibility
np.random.seed(42)
tf.random.set_seed(42)


class ModelTrainer:
    """Trains and evaluates the EOR screening neural network."""
    
    def __init__(
        self,
        input_dim: int,
        num_classes: int,
        output_dir: Optional[Path] = None,
    ):
        """
        Initialize trainer.
        
        Args:
            input_dim: Number of input features
            num_classes: Number of output classes (EOR techniques)
            output_dir: Directory to save model and artifacts
        """
        self.input_dim = input_dim
        self.num_classes = num_classes
        self.output_dir = output_dir or settings.model_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.model: Optional[keras.Model] = None
        self.feature_pipeline: Optional[FeaturePipeline] = None
        self.assessment: Optional[ModelAssessment] = None
        self.training_history: Dict = {}
    
    def build_model(
        self,
        hidden_layers: Tuple[int, ...] = (128, 64, 32),
        dropout_rate: float = 0.3,
        activation: str = "relu",
    ) -> keras.Model:
        """
        Build neural network architecture.
        
        **Architecture:**
        ```
        Input Layer (input_dim)
           ↓
        Dense(128, relu) + Dropout(0.3)
           ↓
        Dense(64, relu) + Dropout(0.3)
           ↓
        Dense(32, relu) + Dropout(0.3)
           ↓
        Dense(num_classes, softmax)  ← Output
        ```
        
        Args:
            hidden_layers: Tuple of hidden layer sizes
            dropout_rate: Dropout rate for regularization
            activation: Activation function
        
        Returns:
            Compiled Keras model
        """
        logger.info(f"Building model: {self.input_dim} → {hidden_layers} → {self.num_classes}")
        
        model = keras.Sequential()
        
        # Input layer
        model.add(layers.Input(shape=(self.input_dim,)))
        
        # Hidden layers
        for units in hidden_layers:
            model.add(layers.Dense(units, activation=activation))
            model.add(layers.Dropout(dropout_rate))
            logger.info(f"  Added Dense({units}, {activation}) + Dropout({dropout_rate})")
        
        # Output layer
        model.add(layers.Dense(self.num_classes, activation="softmax"))
        logger.info(f"  Added Dense({self.num_classes}, softmax)")
        
        # Compile
        model.compile(
            optimizer=keras.optimizers.Adam(learning_rate=0.001),
            loss="sparse_categorical_crossentropy",
            metrics=["accuracy"],
        )
        
        self.model = model
        return model
    
    def train(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: np.ndarray,
        y_val: np.ndarray,
        epochs: int = 100,
        batch_size: int = 32,
        verbose: int = 1,
    ) -> Dict:
        """
        Train the model.
        
        Args:
            X_train: Training features
            y_train: Training labels
            X_val: Validation features
            y_val: Validation labels
            epochs: Number of training epochs
            batch_size: Batch size
            verbose: Verbosity level
        
        Returns:
            Training history dictionary
        """
        if self.model is None:
            raise ValueError("Model not built. Call build_model() first.")
        
        logger.info(f"Training on {len(X_train)} samples, validating on {len(X_val)}")
        
        # Early stopping
        early_stop = keras.callbacks.EarlyStopping(
            monitor="val_loss",
            patience=15,
            restore_best_weights=True,
        )
        
        # Fit model
        history = self.model.fit(
            X_train,
            y_train,
            validation_data=(X_val, y_val),
            epochs=epochs,
            batch_size=batch_size,
            callbacks=[early_stop],
            verbose=verbose,
        )
        
        self.training_history = history.history
        
        logger.info(f"Training complete. Final val_accuracy: {history.history['val_accuracy'][-1]:.4f}")
        
        return self.training_history
    
    def evaluate_and_assess(
        self,
        X_test: np.ndarray,
        y_test: np.ndarray,
        class_names: list,
    ) -> ModelAssessment:
        """
        Evaluate model on test set and run comprehensive assessment.
        
        Args:
            X_test: Test features
            y_test: Test labels
            class_names: List of class names
        
        Returns:
            ModelAssessment object
        """
        if self.model is None:
            raise ValueError("Model not built or loaded.")
        
        logger.info(f"Evaluating on {len(X_test)} test samples")
        
        # Get predictions
        y_probs = self.model.predict(X_test, verbose=0)
        y_pred = np.argmax(y_probs, axis=1)
        
        # Create assessment
        self.assessment = ModelAssessment()
        
        # Overall metrics
        self.assessment.evaluate(y_test, y_pred, class_names, split_name="test")
        
        # Per-technique metrics
        self.assessment.evaluate_per_technique(y_test, y_pred, class_names)
        
        # Calibration analysis
        calibration = CalibrationAnalysis.compute_confidence_calibration(y_test, y_probs)
        logger.info(f"Calibration Error: {calibration['overall_calibration_error']:.4f}")
        
        # Confidence thresholds
        threshold, threshold_analysis = CalibrationAnalysis.suggest_confidence_threshold(
            y_test,
            y_probs,
            target_precision=0.95,
        )
        logger.info(f"Suggested confidence threshold: {threshold:.2f}")
        
        return self.assessment
    
    def save_model(self, version: str = "1.0.0") -> Dict[str, Path]:
        """
        Save model and all artifacts.
        
        Args:
            version: Model version string
        
        Returns:
            Dictionary of saved file paths
        """
        if self.model is None or self.feature_pipeline is None:
            raise ValueError("Model or feature pipeline not initialized.")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        paths = {}
        
        # Save model
        model_path = self.output_dir / f"eor_nn_v{version}.keras"
        self.model.save(model_path)
        paths["model"] = model_path
        logger.info(f"Model saved: {model_path}")
        
        # Save feature pipeline (scaler + encoder)
        scaler_path = self.output_dir / f"scaler_v{version}.joblib"
        joblib.dump(self.feature_pipeline.scaler, scaler_path)
        paths["scaler"] = scaler_path
        logger.info(f"Scaler saved: {scaler_path}")
        
        encoder_path = self.output_dir / f"label_encoder_v{version}.joblib"
        joblib.dump(self.feature_pipeline.label_encoder, encoder_path)
        paths["label_encoder"] = encoder_path
        logger.info(f"Label encoder saved: {encoder_path}")
        
        # Save configuration
        config = {
            "model": {
                "version": version,
                "created": datetime.now().isoformat(),
                "input_features": self.feature_pipeline.feature_names,
                "num_classes": self.num_classes,
                "architecture": "Dense NN with dropout regularization",
            },
            "training": {
                "random_seed": 42,
                "epochs_trained": len(self.training_history.get("loss", [])),
                "batch_size": 32,
                "optimizer": "Adam(lr=0.001)",
            },
            "performance": (
                self.assessment.get_model_card()
                if self.assessment
                else {}
            ),
        }
        
        config_path = self.output_dir / f"config_v{version}.json"
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2, default=str)
        paths["config"] = config_path
        logger.info(f"Config saved: {config_path}")
        
        # Save model card
        if self.assessment:
            card_path = self.output_dir / f"model_card_v{version}.json"
            self.assessment.save_model_card(card_path)
            paths["model_card"] = card_path
        
        return paths


def load_training_data(
    csv_path: Path,
    random_state: int = 42,
) -> Tuple[pd.DataFrame, Dict]:
    """
    Load and prepare training data.
    
    **Expected CSV columns:**
    - depth_ft, porosity_pct, perm_md, api, visc_cp, so_pct
    - formation
    - eor_technique (target)
    - [fuzzy scores for each technique]
    
    Args:
        csv_path: Path to training data CSV
        random_state: Random seed
    
    Returns:
        Tuple of (DataFrame, data_info_dict)
    """
    logger.info(f"Loading training data: {csv_path}")
    
    df = pd.read_csv(csv_path)
    logger.info(f"Loaded {len(df)} samples")
    
    # Data info
    data_info = {
        "total_samples": len(df),
        "columns": df.columns.tolist(),
        "missing_values": df.isnull().sum().to_dict(),
        "class_distribution": df.get("eor_technique", pd.Series([])).value_counts().to_dict(),
    }
    
    logger.info(f"Class distribution: {data_info['class_distribution']}")
    
    return df, data_info


def main():
    """
    Main training pipeline.
    
    Steps:
    1. Load and prepare training data
    2. Build feature pipeline
    3. Split into train/val/test
    4. Build and train model
    5. Evaluate and assess
    6. Save model artifacts
    """
    logger.info("="*60)
    logger.info("EOR ATLAS ML TRAINING PIPELINE - v1.0")
    logger.info("="*60)
    
    # Configuration
    config = {
        "random_state": 42,
        "train_ratio": 0.70,
        "val_ratio": 0.15,
        "test_ratio": 0.15,
        "model_version": "1.0.0",
        "hidden_layers": (128, 64, 32),
        "dropout_rate": 0.3,
        "epochs": 100,
        "batch_size": 32,
    }
    
    logger.info(f"Configuration: {json.dumps(config, indent=2)}")
    
    # For demonstration: create synthetic training data
    # In production, this would load real screening data
    logger.info("\n[Step 1] Generating synthetic training data...")
    
    n_samples = 500
    techniques = ["CO2 WAG", "Polymer", "ASP", "Steam", "Hot water", "Miscible acid gas", "IWAG"]
    formations = ["Sandstone", "Carbonates", "Unconsolidated sands"]
    
    # Generate synthetic data
    data = {
        "depth_ft": np.random.uniform(2000, 12000, n_samples),
        "porosity_pct": np.random.uniform(8, 35, n_samples),
        "perm_md": np.random.uniform(1, 500, n_samples),
        "api": np.random.uniform(15, 55, n_samples),
        "visc_cp": np.random.uniform(0.5, 10, n_samples),
        "so_pct": np.random.uniform(30, 80, n_samples),
        "formation": np.random.choice(formations, n_samples),
        "eor_technique": np.random.choice(techniques, n_samples),
    }
    
    df = pd.DataFrame(data)
    
    # Add fuzzy scores (synthetic)
    for technique in techniques:
        df[f"fuzzy_{technique.lower().replace(' ', '_')}"] = np.random.uniform(0, 1, n_samples)
    
    logger.info(f"Generated {len(df)} synthetic samples")
    logger.info(f"Techniques: {techniques}")
    logger.info(f"Formations: {formations}")
    
    # Step 2: Feature Engineering
    logger.info("\n[Step 2] Building feature pipeline...")
    
    feature_pipeline = FeaturePipeline(alpha=0.30)
    techniques_ordered = sorted(techniques)
    
    # Build feature vectors (simplified for demo)
    X_list = []
    y_list = []
    
    for idx, row in df.iterrows():
        # Numeric features
        numeric, _ = feature_pipeline.compute_numeric_features({
            "depth_ft": row["depth_ft"],
            "porosity_pct": row["porosity_pct"],
            "perm_md": row["perm_md"],
            "api": row["api"],
            "visc_cp": row["visc_cp"],
            "so_pct": row["so_pct"],
        })
        
        # Formation features
        form, _ = feature_pipeline.compute_formation_features(row["formation"], formations)
        
        # Fuzzy features
        fuzzy_scores = {t: row.get(f"fuzzy_{t.lower().replace(' ', '_')}", 0.5) 
                       for t in techniques_ordered}
        fuzzy, _ = feature_pipeline.compute_fuzzy_features(fuzzy_scores, techniques_ordered)
        
        # Concatenate
        feature_vector = np.concatenate([numeric, form, fuzzy])
        X_list.append(feature_vector)
        y_list.append(row["eor_technique"])
    
    X = np.array(X_list)
    y = np.array(y_list)
    
    logger.info(f"Features shape: {X.shape}")
    logger.info(f"Classes: {len(np.unique(y))}")
    
    # Fit scalers
    feature_pipeline.fit_scalers(X, y)
    X_scaled = feature_pipeline.transform_features(X)
    y_encoded = feature_pipeline.transform_labels(y)
    
    # Step 3: Train/Val/Test Split
    logger.info("\n[Step 3] Splitting data...")
    
    (X_train, y_train), (X_val, y_val), (X_test, y_test) = DataPreprocessor.create_train_val_test_split(
        X_scaled,
        y_encoded,
        train_ratio=config["train_ratio"],
        val_ratio=config["val_ratio"],
        test_ratio=config["test_ratio"],
    )
    
    # Step 4: Build and Train Model
    logger.info("\n[Step 4] Building and training model...")
    
    trainer = ModelTrainer(
        input_dim=X_scaled.shape[1],
        num_classes=len(np.unique(y_encoded)),
    )
    
    trainer.build_model(
        hidden_layers=config["hidden_layers"],
        dropout_rate=config["dropout_rate"],
    )
    
    trainer.train(
        X_train, y_train,
        X_val, y_val,
        epochs=config["epochs"],
        batch_size=config["batch_size"],
    )
    
    # Step 5: Evaluate
    logger.info("\n[Step 5] Evaluating model...")
    
    trainer.feature_pipeline = feature_pipeline
    trainer.evaluate_and_assess(X_test, y_test, techniques_ordered)
    
    # Step 6: Save
    logger.info("\n[Step 6] Saving model artifacts...")
    
    saved_paths = trainer.save_model(version=config["model_version"])

    tracker = ModelVersionTracker()
    tracker.register_version(
        version=config["model_version"],
        algorithm="Dense Neural Network",
        framework="TensorFlow/Keras",
        test_accuracy=float(trainer.assessment.test_metrics.accuracy) if trainer.assessment and trainer.assessment.test_metrics else None,
        test_weighted_f1=float(trainer.assessment.test_metrics.weighted_f1) if trainer.assessment and trainer.assessment.test_metrics else None,
        training_samples=len(df),
        description="Synthetic training pipeline for EOR technique classification",
    )
    tracker.write_manifest(
        version=config["model_version"],
        model_path=saved_paths["model"],
        scaler_path=saved_paths["scaler"],
        encoder_path=saved_paths["label_encoder"],
        config_path=saved_paths["config"],
        output_dir=settings.model_dir,
    )
    
    logger.info("\n" + "="*60)
    logger.info("TRAINING COMPLETE")
    logger.info("="*60)
    logger.info(f"Model saved to: {settings.model_dir}")
    for artifact, path in saved_paths.items():
        logger.info(f"  {artifact}: {path}")
    
    return trainer, saved_paths


if __name__ == "__main__":
    trainer, paths = main()
