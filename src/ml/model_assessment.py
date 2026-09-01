"""
Model assessment and evaluation metrics for EOR screening.

Tracks performance across training, validation, and test sets.
Includes per-technique metrics, calibration analysis, and model cards.
"""

from typing import Dict, Tuple, List, Optional
import numpy as np
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    classification_report,
)
from dataclasses import dataclass, asdict
import json
import logging

logger = logging.getLogger(__name__)


@dataclass
class TechniqueMetrics:
    """Metrics for a single EOR technique."""
    
    technique: str
    precision: float
    recall: float
    f1: float
    support: int  # Number of test samples
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class ModelPerformance:
    """Overall model performance metrics."""
    
    accuracy: float
    macro_f1: float
    weighted_f1: float
    macro_precision: float
    weighted_precision: float
    macro_recall: float
    weighted_recall: float
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return asdict(self)


class ModelAssessment:
    """Comprehensive model evaluation and assessment."""
    
    def __init__(self):
        """Initialize assessment tracker."""
        self.train_metrics: Optional[ModelPerformance] = None
        self.val_metrics: Optional[ModelPerformance] = None
        self.test_metrics: Optional[ModelPerformance] = None
        self.technique_metrics: Dict[str, TechniqueMetrics] = {}
        self.confusion_matrix: Optional[np.ndarray] = None
        self.class_names: List[str] = []
    
    def evaluate(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        classes: List[str],
        split_name: str = "test",
    ) -> ModelPerformance:
        """
        Evaluate model predictions.
        
        Args:
            y_true: True labels (encoded)
            y_pred: Predicted labels (encoded)
            classes: List of class names
            split_name: Name of data split (train/val/test)
        
        Returns:
            ModelPerformance object
        """
        self.class_names = classes
        
        # Compute metrics
        accuracy = accuracy_score(y_true, y_pred)
        macro_f1 = f1_score(y_true, y_pred, average='macro', zero_division=0)
        weighted_f1 = f1_score(y_true, y_pred, average='weighted', zero_division=0)
        macro_precision = precision_score(y_true, y_pred, average='macro', zero_division=0)
        weighted_precision = precision_score(y_true, y_pred, average='weighted', zero_division=0)
        macro_recall = recall_score(y_true, y_pred, average='macro', zero_division=0)
        weighted_recall = recall_score(y_true, y_pred, average='weighted', zero_division=0)
        
        metrics = ModelPerformance(
            accuracy=accuracy,
            macro_f1=macro_f1,
            weighted_f1=weighted_f1,
            macro_precision=macro_precision,
            weighted_precision=weighted_precision,
            macro_recall=macro_recall,
            weighted_recall=weighted_recall,
        )
        
        # Store by split
        if split_name == "train":
            self.train_metrics = metrics
        elif split_name == "val":
            self.val_metrics = metrics
        elif split_name == "test":
            self.test_metrics = metrics
            self.confusion_matrix = confusion_matrix(y_true, y_pred)
        
        logger.info(f"{split_name.upper()} Metrics:")
        logger.info(f"  Accuracy: {accuracy:.4f}")
        logger.info(f"  Macro F1: {macro_f1:.4f}")
        logger.info(f"  Weighted F1: {weighted_f1:.4f}")
        
        return metrics
    
    def evaluate_per_technique(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        classes: List[str],
    ) -> Dict[str, TechniqueMetrics]:
        """
        Evaluate metrics per EOR technique.
        
        Args:
            y_true: True labels (encoded)
            y_pred: Predicted labels (encoded)
            classes: List of class names
        
        Returns:
            Dictionary mapping technique -> TechniqueMetrics
        """
        self.technique_metrics = {}
        
        # Get per-class metrics
        report = classification_report(
            y_true,
            y_pred,
            output_dict=True,
            zero_division=0,
        )
        
        for idx, technique in enumerate(classes):
            class_key = str(idx)
            if class_key in report:
                metrics_dict = report[class_key]
                
                tech_metrics = TechniqueMetrics(
                    technique=technique,
                    precision=float(metrics_dict['precision']),
                    recall=float(metrics_dict['recall']),
                    f1=float(metrics_dict['f1-score']),
                    support=int(metrics_dict['support']),
                )
                
                self.technique_metrics[technique] = tech_metrics
                
                logger.info(
                    f"{technique}: P={tech_metrics.precision:.3f}, "
                    f"R={tech_metrics.recall:.3f}, F1={tech_metrics.f1:.3f}, "
                    f"N={tech_metrics.support}"
                )
        
        return self.technique_metrics
    
    def get_confusion_matrix_report(self) -> Dict:
        """
        Generate confusion matrix report.
        
        Returns:
            Dictionary with confusion matrix data
        """
        if self.confusion_matrix is None:
            return {}
        
        cm = self.confusion_matrix
        
        report = {
            "matrix": cm.tolist(),
            "classes": self.class_names,
            "interpretation": self._interpret_confusion_matrix(cm),
        }
        
        return report
    
    @staticmethod
    def _interpret_confusion_matrix(cm: np.ndarray) -> Dict:
        """
        Interpret confusion matrix to identify weak areas.
        
        Args:
            cm: Confusion matrix
        
        Returns:
            Dictionary with interpretation
        """
        # Compute True Positives, False Positives, False Negatives
        tp = np.diag(cm)
        fp = cm.sum(axis=0) - tp
        fn = cm.sum(axis=1) - tp
        
        # Identify rows (classes) with high confusion
        confusion_rate = (cm.sum(axis=1) - tp) / cm.sum(axis=1)
        
        return {
            "total_samples": int(cm.sum()),
            "diagonal_sum": int(tp.sum()),
            "high_confusion_classes": [
                cls for i, cls in enumerate(np.arange(len(cm)))
                if confusion_rate[i] > 0.3
            ],
        }
    
    def get_model_card(self) -> Dict:
        """
        Generate comprehensive model card for documentation.
        
        Model card includes:
        - Model name and version
        - Training data information
        - Performance metrics
        - Technique-specific performance
        - Limitations and recommendations
        
        Returns:
            Dictionary representing model card
        """
        model_card = {
            "model_info": {
                "name": "EOR Screening Neural Network",
                "version": "1.0.0",
                "algorithm": "Dense Neural Network",
                "framework": "TensorFlow/Keras",
                "created": "2026-09-01",
            },
            "training_data": {
                "source": "Compiled EOR screening database",
                "size": "TBD",
                "features": 16 + 3 + 7,  # numeric + formation + fuzzy
                "classes": len(self.class_names),
                "class_names": self.class_names,
            },
            "performance": {
                "train": self.train_metrics.to_dict() if self.train_metrics else {},
                "validation": self.val_metrics.to_dict() if self.val_metrics else {},
                "test": self.test_metrics.to_dict() if self.test_metrics else {},
            },
            "technique_performance": {
                tech: metrics.to_dict()
                for tech, metrics in self.technique_metrics.items()
            },
            "confusion_matrix": self.get_confusion_matrix_report(),
            "limitations": [
                "Model trained on limited dataset",
                "Performance varies by formation type",
                "Requires valid fuzzy envelope data",
                "Should be calibrated on new reservoir types",
            ],
            "recommendations": [
                "Use model confidence thresholds >= 0.60",
                "Always validate against engineering rules",
                "Update model with new screening cases quarterly",
                "Monitor performance metrics in production",
                "Consider retraining if accuracy drops below 80%",
            ],
        }
        
        return model_card
    
    def save_model_card(self, filepath: str) -> None:
        """
        Save model card to JSON file.
        
        Args:
            filepath: Path to save model card
        """
        model_card = self.get_model_card()
        
        with open(filepath, 'w') as f:
            json.dump(model_card, f, indent=2, default=str)
        
        logger.info(f"Model card saved to {filepath}")


class CalibrationAnalysis:
    """Analyze and improve model calibration."""
    
    @staticmethod
    def compute_confidence_calibration(
        y_true: np.ndarray,
        y_probs: np.ndarray,
        n_bins: int = 10,
    ) -> Dict:
        """
        Analyze model confidence calibration.
        
        Compares predicted confidence with actual accuracy.
        
        Args:
            y_true: True labels
            y_probs: Predicted probabilities (N_samples, N_classes)
            n_bins: Number of bins for calibration curve
        
        Returns:
            Dictionary with calibration metrics
        """
        # Get predicted class and confidence
        y_pred = np.argmax(y_probs, axis=1)
        confidences = np.max(y_probs, axis=1)
        
        # Bin by confidence
        bin_edges = np.linspace(0, 1, n_bins + 1)
        bin_indices = np.digitize(confidences, bin_edges) - 1
        
        calibration_data = {
            "bins": [],
            "expected_accuracy": [],
            "actual_accuracy": [],
            "calibration_error": [],
        }
        
        for bin_idx in range(n_bins):
            mask = bin_indices == bin_idx
            
            if mask.sum() == 0:
                continue
            
            # Expected accuracy = average confidence in bin
            expected = confidences[mask].mean()
            
            # Actual accuracy = proportion of correct predictions
            actual = (y_true[mask] == y_pred[mask]).astype(float).mean()
            
            calibration_data["bins"].append(
                f"{bin_edges[bin_idx]:.2f}-{bin_edges[bin_idx+1]:.2f}"
            )
            calibration_data["expected_accuracy"].append(float(expected))
            calibration_data["actual_accuracy"].append(float(actual))
            calibration_data["calibration_error"].append(float(abs(expected - actual)))
        
        # Overall calibration metrics
        overall_ce = np.mean(calibration_data["calibration_error"])
        
        return {
            "calibration_curve": calibration_data,
            "overall_calibration_error": float(overall_ce),
            "is_well_calibrated": overall_ce < 0.05,
            "interpretation": (
                "Model is well-calibrated (confidence matches accuracy)"
                if overall_ce < 0.05
                else "Model needs calibration adjustment (confidence != accuracy)"
            ),
        }
    
    @staticmethod
    def suggest_confidence_threshold(
        y_true: np.ndarray,
        y_probs: np.ndarray,
        target_precision: float = 0.95,
    ) -> Tuple[float, Dict]:
        """
        Suggest confidence threshold for high-precision predictions.
        
        Args:
            y_true: True labels
            y_probs: Predicted probabilities
            target_precision: Desired precision level
        
        Returns:
            Tuple of (recommended_threshold, analysis_dict)
        """
        y_pred = np.argmax(y_probs, axis=1)
        confidences = np.max(y_probs, axis=1)
        
        # Correct predictions
        correct = (y_true == y_pred).astype(float)
        
        # Try different thresholds
        thresholds = np.linspace(0, 1, 101)
        results = []
        
        for threshold in thresholds:
            mask = confidences >= threshold
            
            if mask.sum() == 0:
                continue
            
            precision = correct[mask].mean()
            coverage = mask.mean()
            
            results.append({
                "threshold": float(threshold),
                "precision": float(precision),
                "coverage": float(coverage),
            })
        
        # Find threshold closest to target precision
        best_result = min(
            results,
            key=lambda x: abs(x["precision"] - target_precision),
        )
        
        return best_result["threshold"], {
            "recommended_threshold": best_result["threshold"],
            "expected_precision": best_result["precision"],
            "expected_coverage": best_result["coverage"],
            "analysis": results,
        }
