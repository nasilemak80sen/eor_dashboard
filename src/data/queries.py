"""
Database query layer and repository pattern for EOR Atlas.

Provides clean abstraction for database operations.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_

from data.database import (
    Field, Reservoir, ScreeningRun, EligibilityResult, FuzzyResult, MLResult,
    Scenario, ModelVersion, RuleVersion, AuditEvent, DatabaseManager
)
from utils.logging_config import logger


class FieldRepository:
    """Repository for Field operations."""
    
    def __init__(self, session: Session = None):
        """Initialize with optional session."""
        self.session = session
    
    def create(
        self,
        name: str,
        location: Optional[str] = None,
        operator: Optional[str] = None,
        country: Optional[str] = None,
    ) -> Field:
        """Create new field."""
        if not self.session:
            self.session = DatabaseManager.get_session()
        
        field = Field(
            name=name,
            location=location,
            operator=operator,
            country=country,
        )
        self.session.add(field)
        self.session.commit()
        logger.info(f"Created field: {name}")
        return field
    
    def get_by_name(self, name: str) -> Optional[Field]:
        """Get field by name."""
        if not self.session:
            self.session = DatabaseManager.get_session()
        
        return self.session.query(Field).filter(Field.name == name).first()
    
    def list_all(self) -> List[Field]:
        """List all fields."""
        if not self.session:
            self.session = DatabaseManager.get_session()
        
        return self.session.query(Field).order_by(Field.name).all()


class ReservoirRepository:
    """Repository for Reservoir operations."""
    
    def __init__(self, session: Session = None):
        """Initialize with optional session."""
        self.session = session
    
    def create(
        self,
        field_id: int,
        name: str,
        formation: str,
        **kwargs
    ) -> Reservoir:
        """Create new reservoir."""
        if not self.session:
            self.session = DatabaseManager.get_session()
        
        reservoir = Reservoir(
            field_id=field_id,
            name=name,
            formation=formation,
            **kwargs
        )
        self.session.add(reservoir)
        self.session.commit()
        logger.info(f"Created reservoir: {name} in formation {formation}")
        return reservoir
    
    def get_by_id(self, reservoir_id: int) -> Optional[Reservoir]:
        """Get reservoir by ID."""
        if not self.session:
            self.session = DatabaseManager.get_session()
        
        return self.session.query(Reservoir).filter(Reservoir.id == reservoir_id).first()
    
    def list_by_field(self, field_id: int) -> List[Reservoir]:
        """List all reservoirs in a field."""
        if not self.session:
            self.session = DatabaseManager.get_session()
        
        return self.session.query(Reservoir).filter(
            Reservoir.field_id == field_id
        ).all()


class ScreeningRepository:
    """Repository for ScreeningRun operations."""
    
    def __init__(self, session: Session = None):
        """Initialize with optional session."""
        self.session = session
    
    def create(
        self,
        formation: str,
        depth_ft: float,
        porosity_pct: float,
        perm_md: float,
        api: float,
        visc_cp: float,
        so_pct: float,
        **kwargs
    ) -> ScreeningRun:
        """Create new screening run."""
        if not self.session:
            self.session = DatabaseManager.get_session()
        
        screening = ScreeningRun(
            formation=formation,
            depth_ft=depth_ft,
            porosity_pct=porosity_pct,
            perm_md=perm_md,
            api=api,
            visc_cp=visc_cp,
            so_pct=so_pct,
            **kwargs
        )
        self.session.add(screening)
        self.session.commit()
        logger.info(f"Created screening run: {screening.id}")
        return screening
    
    def get_by_id(self, screening_id: int) -> Optional[ScreeningRun]:
        """Get screening run by ID."""
        if not self.session:
            self.session = DatabaseManager.get_session()
        
        return self.session.query(ScreeningRun).filter(
            ScreeningRun.id == screening_id
        ).first()
    
    def get_latest_for_reservoir(
        self,
        reservoir_id: int,
        limit: int = 10
    ) -> List[ScreeningRun]:
        """Get latest screening runs for a reservoir."""
        if not self.session:
            self.session = DatabaseManager.get_session()
        
        return self.session.query(ScreeningRun).filter(
            ScreeningRun.reservoir_id == reservoir_id
        ).order_by(
            desc(ScreeningRun.timestamp)
        ).limit(limit).all()
    
    def get_recent(self, days: int = 7) -> List[ScreeningRun]:
        """Get screening runs from last N days."""
        if not self.session:
            self.session = DatabaseManager.get_session()
        
        cutoff = datetime.utcnow() - timedelta(days=days)
        return self.session.query(ScreeningRun).filter(
            ScreeningRun.timestamp >= cutoff
        ).order_by(
            desc(ScreeningRun.timestamp)
        ).all()
    
    def update_results(
        self,
        screening_id: int,
        recommended_technique: str,
        recommendation_status: str,
        recommendation_score: float,
        recommendation_mode: str,
    ) -> None:
        """Update screening with results."""
        if not self.session:
            self.session = DatabaseManager.get_session()

        screening = self.get_by_id(screening_id)
        if screening:
            screening.recommended_technique = recommended_technique
            screening.recommendation_status = recommendation_status
            screening.recommendation_score = recommendation_score
            screening.recommendation_mode = recommendation_mode
            screening.updated_at = datetime.utcnow()
            self.session.commit()
            logger.info(f"Updated screening {screening_id} with results")

    def update_run_metadata(self, screening_id: int, **kwargs) -> Optional[ScreeningRun]:
        """Update arbitrary metadata fields for a run, including evidence and assumptions."""
        if not self.session:
            self.session = DatabaseManager.get_session()

        screening = self.get_by_id(screening_id)
        if screening is None:
            return None

        for key, value in kwargs.items():
            if hasattr(screening, key):
                setattr(screening, key, value)

        self.session.commit()
        return screening

    def get_detail(self, screening_id: int) -> Optional[ScreeningRun]:
        """Return the full screening run detail object, including trace metadata."""
        if not self.session:
            self.session = DatabaseManager.get_session()

        return self.session.query(ScreeningRun).filter(ScreeningRun.id == screening_id).first()

    def compare_runs(self, run_a_id: int, run_b_id: int) -> Dict[str, Any]:
        """Compare two saved screening runs for delta analysis."""
        if not self.session:
            self.session = DatabaseManager.get_session()

        run_a = self.get_by_id(run_a_id)
        run_b = self.get_by_id(run_b_id)
        if run_a is None or run_b is None:
            return {"error": "Both screening runs must exist"}

        return {
            "left": {
                "id": run_a.id,
                "formation": run_a.formation,
                "inputs": run_a.input_payload or {},
                "recommendation": run_a.recommended_technique,
                "status": run_a.recommendation_status,
                "score": run_a.recommendation_score,
            },
            "right": {
                "id": run_b.id,
                "formation": run_b.formation,
                "inputs": run_b.input_payload or {},
                "recommendation": run_b.recommended_technique,
                "status": run_b.recommendation_status,
                "score": run_b.recommendation_score,
            },
            "delta_score": (run_b.recommendation_score or 0.0) - (run_a.recommendation_score or 0.0),
        }
    
    def save_eligibility_results(
        self,
        screening_id: int,
        eligibility_dict: Dict[str, Dict],
    ) -> None:
        """Save eligibility results."""
        if not self.session:
            self.session = DatabaseManager.get_session()
        
        # Clear existing
        self.session.query(EligibilityResult).filter(
            EligibilityResult.screening_id == screening_id
        ).delete()
        
        # Add new
        for technique, result in eligibility_dict.items():
            elig = EligibilityResult(
                screening_id=screening_id,
                technique=technique,
                status=result.get("status", "FAIL"),
                criteria_passed=result.get("criteria_passed"),
                criteria_total=result.get("criteria_total"),
                details=result.get("details"),
            )
            self.session.add(elig)
        
        self.session.commit()
        logger.info(f"Saved eligibility results for screening {screening_id}")
    
    def save_fuzzy_results(
        self,
        screening_id: int,
        fuzzy_dict: Dict[str, float],
        membership_dict: Optional[Dict[str, Dict]] = None,
    ) -> None:
        """Save fuzzy suitability results."""
        if not self.session:
            self.session = DatabaseManager.get_session()
        
        # Clear existing
        self.session.query(FuzzyResult).filter(
            FuzzyResult.screening_id == screening_id
        ).delete()
        
        # Add new
        for technique, score in fuzzy_dict.items():
            fuzzy = FuzzyResult(
                screening_id=screening_id,
                technique=technique,
                suitability_score=score,
                membership_scores=membership_dict.get(technique) if membership_dict else None,
            )
            self.session.add(fuzzy)
        
        self.session.commit()
        logger.info(f"Saved fuzzy results for screening {screening_id}")
    
    def save_ml_results(
        self,
        screening_id: int,
        ml_dict: Dict[str, float],
    ) -> None:
        """Save ML prediction results."""
        if not self.session:
            self.session = DatabaseManager.get_session()
        
        # Clear existing
        self.session.query(MLResult).filter(
            MLResult.screening_id == screening_id
        ).delete()
        
        # Find max probability for top prediction
        max_prob = max(ml_dict.values()) if ml_dict else 0.0
        
        # Add new
        for technique, prob in ml_dict.items():
            ml = MLResult(
                screening_id=screening_id,
                technique=technique,
                probability=prob,
                is_top_prediction=(prob == max_prob),
                confidence=prob,
            )
            self.session.add(ml)
        
        self.session.commit()
        logger.info(f"Saved ML results for screening {screening_id}")


class ModelVersionRepository:
    """Repository for ModelVersion tracking."""
    
    def __init__(self, session: Session = None):
        """Initialize with optional session."""
        self.session = session
    
    def register(
        self,
        version: str,
        algorithm: str,
        framework: str,
        test_accuracy: Optional[float] = None,
        test_weighted_f1: Optional[float] = None,
        **kwargs
    ) -> ModelVersion:
        """Register a new model version."""
        if not self.session:
            self.session = DatabaseManager.get_session()
        
        model_ver = ModelVersion(
            version=version,
            algorithm=algorithm,
            framework=framework,
            test_accuracy=test_accuracy,
            test_weighted_f1=test_weighted_f1,
            **kwargs
        )
        self.session.add(model_ver)
        self.session.commit()
        logger.info(f"Registered model version: {version}")
        return model_ver
    
    def get_active(self) -> Optional[ModelVersion]:
        """Get active model version."""
        if not self.session:
            self.session = DatabaseManager.get_session()
        
        return self.session.query(ModelVersion).filter(
            ModelVersion.is_active == True
        ).order_by(
            desc(ModelVersion.created_at)
        ).first()
    
    def list_versions(self) -> List[ModelVersion]:
        """List all model versions."""
        if not self.session:
            self.session = DatabaseManager.get_session()
        
        return self.session.query(ModelVersion).order_by(
            desc(ModelVersion.created_at)
        ).all()


class AuditRepository:
    """Repository for audit event logging."""
    
    def __init__(self, session: Session = None):
        """Initialize with optional session."""
        self.session = session
    
    def log_event(
        self,
        action: str,
        object_type: str,
        object_id: Optional[int] = None,
        user: Optional[str] = None,
        old_value: Optional[str] = None,
        new_value: Optional[str] = None,
        details: Optional[Dict] = None,
    ) -> AuditEvent:
        """Log an audit event."""
        if not self.session:
            self.session = DatabaseManager.get_session()
        
        event = AuditEvent(
            user=user,
            action=action,
            object_type=object_type,
            object_id=object_id,
            old_value=old_value,
            new_value=new_value,
            details=details,
        )
        self.session.add(event)
        self.session.commit()
        return event
    
    def get_recent(self, limit: int = 50) -> List[AuditEvent]:
        """Get recent audit events."""
        if not self.session:
            self.session = DatabaseManager.get_session()
        
        return self.session.query(AuditEvent).order_by(
            desc(AuditEvent.timestamp)
        ).limit(limit).all()


class RepositoryFactory:
    """Factory for creating repository instances."""
    
    _session: Optional[Session] = None
    
    @classmethod
    def set_session(cls, session: Session) -> None:
        """Set session for all repositories."""
        cls._session = session
    
    @classmethod
    def get_session(cls) -> Session:
        """Get current session or create new one."""
        if cls._session is None:
            cls._session = DatabaseManager.get_session()
        return cls._session
    
    @classmethod
    def field_repo(cls) -> FieldRepository:
        """Get field repository."""
        return FieldRepository(cls.get_session())
    
    @classmethod
    def reservoir_repo(cls) -> ReservoirRepository:
        """Get reservoir repository."""
        return ReservoirRepository(cls.get_session())
    
    @classmethod
    def screening_repo(cls) -> ScreeningRepository:
        """Get screening repository."""
        return ScreeningRepository(cls.get_session())
    
    @classmethod
    def model_version_repo(cls) -> ModelVersionRepository:
        """Get model version repository."""
        return ModelVersionRepository(cls.get_session())
    
    @classmethod
    def audit_repo(cls) -> AuditRepository:
        """Get audit repository."""
        return AuditRepository(cls.get_session())
