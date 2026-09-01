"""
Feature engineering pipeline for EOR screening ML model.

Handles data preparation, feature transformation, and feature versioning.
"""

from typing import Dict, List, Tuple, Optional
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler, LabelEncoder
import logging

logger = logging.getLogger(__name__)


class FeaturePipeline:
    """Feature engineering and transformation pipeline."""
    
    def __init__(self, alpha: float = 0.30):
        """
        Initialize feature pipeline.
        
        Args:
            alpha: Fuzzy envelope fuzzification parameter
        """
        self.alpha = alpha
        self.feature_names: List[str] = []
        self.feature_shapes = {}
        self.scaler: Optional[StandardScaler] = None
        self.label_encoder: Optional[LabelEncoder] = None
        self.version = "1.0.0"
    
    def get_feature_specification(self) -> Dict:
        """
        Get detailed specification of all features.
        
        Returns:
            Dictionary describing feature structure
        """
        return {
            "version": self.version,
            "total_features": len(self.feature_names),
            "feature_groups": {
                "numeric_midpoints": 6,
                "numeric_spans": 6,
                "numeric_derived": 4,
                "formation_onehot": 3,
                "fuzzy_scores": "N_techniques",
            },
            "features": self.feature_names,
            "feature_shapes": self.feature_shapes,
        }
    
    @staticmethod
    def compute_numeric_features(
        values: Dict[str, float],
    ) -> Tuple[np.ndarray, List[str]]:
        """
        Compute base numeric features.
        
        **Raw Features (6):**
        - Depth midpoint, Porosity midpoint, Permeability midpoint
        - API midpoint, Viscosity midpoint, Oil Saturation midpoint
        
        **Span Features (6):**
        - Uncertainty ranges for each (set to 0 for point estimates)
        
        **Derived Features (4):**
        - log10(permeability), log10(viscosity)
        - log10(permeability_span + 1), log10(viscosity_span + 1)
        
        Args:
            values: Input reservoir parameters
        
        Returns:
            Tuple of (feature_array, feature_names)
        """
        depth_mid = values["depth_ft"]
        por_mid = values["porosity_pct"]
        perm_mid = values["perm_md"]
        api_mid = values["api"]
        visc_mid = values["visc_cp"]
        so_mid = values["so_pct"]
        
        # Spans (all zero for point estimates)
        depth_span = 0.0
        por_span = 0.0
        perm_span = 0.0
        api_span = 0.0
        visc_span = 0.0
        so_span = 0.0
        
        eps = 1e-6
        
        numeric = np.array(
            [
                depth_mid,
                por_mid,
                perm_mid,
                api_mid,
                visc_mid,
                so_mid,
                # Spans
                depth_span,
                por_span,
                perm_span,
                api_span,
                visc_span,
                so_span,
                # Derived (log transforms)
                np.log10(max(perm_mid, 0.0) + eps),
                np.log10(max(visc_mid, 0.0) + eps),
                np.log10(perm_span + 1.0 + eps),
                np.log10(visc_span + 1.0 + eps),
            ],
            dtype=float,
        )
        
        feature_names = [
            "depth_ft",
            "porosity_pct",
            "perm_md",
            "api",
            "visc_cp",
            "so_pct",
            "depth_span",
            "por_span",
            "perm_span",
            "api_span",
            "visc_span",
            "so_span",
            "log_perm",
            "log_visc",
            "log_perm_span",
            "log_visc_span",
        ]
        
        return numeric, feature_names
    
    @staticmethod
    def compute_formation_features(
        formation: str,
        formation_categories: List[str] = None,
    ) -> Tuple[np.ndarray, List[str]]:
        """
        Compute one-hot encoded formation features.
        
        **Categorical Encoding (3):**
        - One-hot encoding of formation type
        - [Sandstone, Carbonates, Unconsolidated sands]
        
        Args:
            formation: Formation type name
            formation_categories: List of valid categories
        
        Returns:
            Tuple of (feature_array, feature_names)
        """
        if formation_categories is None:
            formation_categories = ["Sandstone", "Carbonates", "Unconsolidated sands"]
        
        form_onehot = np.array(
            [1.0 if formation == name else 0.0 for name in formation_categories],
            dtype=float,
        )
        
        feature_names = [f"formation_{cat.lower().replace(' ', '_')}" 
                         for cat in formation_categories]
        
        return form_onehot, feature_names
    
    @staticmethod
    def compute_fuzzy_features(
        fuzzy_scores: Dict[str, float],
        techniques: List[str],
    ) -> Tuple[np.ndarray, List[str]]:
        """
        Compute fuzzy envelope suitability features.
        
        **Fuzzy Scores (N):**
        - Fuzzy membership score for each EOR technique
        - Bridges deterministic engineering and ML
        
        Args:
            fuzzy_scores: Dictionary of technique -> suitability score
            techniques: Ordered list of technique names
        
        Returns:
            Tuple of (feature_array, feature_names)
        """
        fuzzy_vec = np.array(
            [fuzzy_scores.get(t, 0.0) for t in techniques],
            dtype=float,
        )
        
        feature_names = [f"fuzzy_{t.lower().replace(' ', '_')}" 
                         for t in techniques]
        
        return fuzzy_vec, feature_names
    
    def build_feature_vector(
        self,
        values: Dict[str, float],
        formation: str,
        techniques: List[str],
        fuzzy_scores: Dict[str, float],
        formation_categories: List[str] = None,
    ) -> np.ndarray:
        """
        Build complete feature vector for model inference.
        
        **Feature Architecture:**
        ```
        [Numeric (16)] + [Formation (3)] + [Fuzzy (N)] = Total Features
        
        Numeric:
        - Raw (6): depth, porosity, perm, api, visc, so
        - Spans (6): uncertainty ranges
        - Derived (4): log transforms
        
        Formation:
        - One-hot (3): Sandstone, Carbonates, Unconsolidated
        
        Fuzzy:
        - Scores (N): One per EOR technique
        ```
        
        Args:
            values: Input reservoir parameters
            formation: Formation type
            techniques: List of EOR techniques
            fuzzy_scores: Fuzzy suitability scores
            formation_categories: List of valid formations
        
        Returns:
            Feature vector ready for model.predict()
        """
        # Compute each feature group
        numeric, numeric_names = self.compute_numeric_features(values)
        form, form_names = self.compute_formation_features(formation, formation_categories)
        fuzzy, fuzzy_names = self.compute_fuzzy_features(fuzzy_scores, techniques)
        
        # Store feature names on first call
        if not self.feature_names:
            self.feature_names = numeric_names + form_names + fuzzy_names
        
        # Concatenate all features
        features = np.concatenate([numeric, form, fuzzy], axis=0)
        
        return features
    
    def fit_scalers(
        self,
        X: np.ndarray,
        y: np.ndarray,
    ) -> None:
        """
        Fit feature scalers on training data.
        
        Args:
            X: Training feature matrix (N_samples, N_features)
            y: Target labels (N_samples,)
        """
        logger.info(f"Fitting scalers on {X.shape[0]} training samples")
        
        # Fit StandardScaler
        self.scaler = StandardScaler()
        self.scaler.fit(X)
        
        # Fit LabelEncoder
        self.label_encoder = LabelEncoder()
        self.label_encoder.fit(y)
        
        logger.info(f"Scaler fitted. Input shape: {X.shape}")
        logger.info(f"Classes: {list(self.label_encoder.classes_)}")
    
    def transform_features(
        self,
        X: np.ndarray,
    ) -> np.ndarray:
        """
        Transform feature matrix using fitted scalers.
        
        Args:
            X: Raw feature matrix
        
        Returns:
            Scaled feature matrix
        """
        if self.scaler is None:
            raise ValueError("Scaler not fitted. Call fit_scalers() first.")
        
        return self.scaler.transform(X)
    
    def transform_labels(
        self,
        y: np.ndarray,
    ) -> np.ndarray:
        """
        Transform labels using fitted encoder.
        
        Args:
            y: Label array
        
        Returns:
            Encoded labels
        """
        if self.label_encoder is None:
            raise ValueError("Label encoder not fitted. Call fit_scalers() first.")
        
        return self.label_encoder.transform(y)
    
    def inverse_transform_labels(
        self,
        y_encoded: np.ndarray,
    ) -> np.ndarray:
        """
        Inverse transform encoded labels back to original.
        
        Args:
            y_encoded: Encoded label array
        
        Returns:
            Original labels
        """
        if self.label_encoder is None:
            raise ValueError("Label encoder not fitted.")
        
        return self.label_encoder.inverse_transform(y_encoded)


class DataPreprocessor:
    """Preprocesses raw EOR screening data for model training."""
    
    @staticmethod
    def validate_dataset(
        df: pd.DataFrame,
        required_columns: List[str],
    ) -> Tuple[bool, List[str]]:
        """
        Validate dataset has required columns.
        
        Args:
            df: Input DataFrame
            required_columns: List of required column names
        
        Returns:
            Tuple of (is_valid, missing_columns)
        """
        missing = [col for col in required_columns if col not in df.columns]
        return len(missing) == 0, missing
    
    @staticmethod
    def remove_outliers(
        df: pd.DataFrame,
        columns: List[str],
        z_threshold: float = 3.0,
    ) -> pd.DataFrame:
        """
        Remove rows with outlier values.
        
        Args:
            df: Input DataFrame
            columns: Columns to check for outliers
            z_threshold: Z-score threshold for outlier detection
        
        Returns:
            DataFrame with outliers removed
        """
        df_clean = df.copy()
        
        for col in columns:
            if df_clean[col].dtype in ['float64', 'int64']:
                z_scores = np.abs((df_clean[col] - df_clean[col].mean()) / df_clean[col].std())
                df_clean = df_clean[z_scores < z_threshold]
        
        logger.info(f"Removed {len(df) - len(df_clean)} outlier rows")
        return df_clean
    
    @staticmethod
    def handle_missing_values(
        df: pd.DataFrame,
        strategy: str = "drop",
    ) -> pd.DataFrame:
        """
        Handle missing values in dataset.
        
        Args:
            df: Input DataFrame
            strategy: 'drop' or 'mean' for imputation
        
        Returns:
            DataFrame with missing values handled
        """
        if strategy == "drop":
            return df.dropna()
        elif strategy == "mean":
            numeric_cols = df.select_dtypes(include=[np.number]).columns
            return df.fillna(df[numeric_cols].mean())
        else:
            raise ValueError(f"Unknown strategy: {strategy}")
    
    @staticmethod
    def create_train_val_test_split(
        X: np.ndarray,
        y: np.ndarray,
        train_ratio: float = 0.7,
        val_ratio: float = 0.15,
        test_ratio: float = 0.15,
        random_state: int = 42,
    ) -> Tuple[
        Tuple[np.ndarray, np.ndarray],
        Tuple[np.ndarray, np.ndarray],
        Tuple[np.ndarray, np.ndarray],
    ]:
        """
        Split data into train/validation/test sets.
        
        Args:
            X: Feature matrix
            y: Target labels
            train_ratio: Proportion for training
            val_ratio: Proportion for validation
            test_ratio: Proportion for testing
            random_state: Random seed
        
        Returns:
            Three tuples: (X_train, y_train), (X_val, y_val), (X_test, y_test)
        """
        np.random.seed(random_state)
        n_samples = len(X)
        
        # Shuffle indices
        indices = np.random.permutation(n_samples)
        X_shuffled = X[indices]
        y_shuffled = y[indices]
        
        # Split points
        train_end = int(n_samples * train_ratio)
        val_end = train_end + int(n_samples * val_ratio)
        
        # Split data
        X_train, y_train = X_shuffled[:train_end], y_shuffled[:train_end]
        X_val, y_val = X_shuffled[train_end:val_end], y_shuffled[train_end:val_end]
        X_test, y_test = X_shuffled[val_end:], y_shuffled[val_end:]
        
        logger.info(
            f"Train: {len(X_train)}, Val: {len(X_val)}, Test: {len(X_test)}"
        )
        
        return (X_train, y_train), (X_val, y_val), (X_test, y_test)
