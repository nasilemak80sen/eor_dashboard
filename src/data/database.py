"""
SQLite database models and schema for EOR Atlas.

Implements persistent storage for:
- Screening results and history
- Reservoir and field information
- Scenarios and case comparisons
- Model versioning
- Audit trails
"""

from sqlalchemy import (
    create_engine, Column, Integer, String, Float, DateTime,
    Text, Boolean, ForeignKey, JSON, UniqueConstraint, Index, inspect, text
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime
from pathlib import Path
from typing import Optional

from config.settings import settings
from utils.logging_config import logger

# Create declarative base
Base = declarative_base()

# Database path
DB_PATH = settings.root_dir / "eor_atlas.db"


class Field(Base):
    """Oil and gas field information."""
    
    __tablename__ = "fields"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), unique=True, nullable=False)
    location = Column(String(255), nullable=True)
    operator = Column(String(255), nullable=True)
    country = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    reservoirs = relationship("Reservoir", back_populates="field", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Field(name='{self.name}', location='{self.location}')>"


class Reservoir(Base):
    """Reservoir definition within a field."""
    
    __tablename__ = "reservoirs"
    
    id = Column(Integer, primary_key=True)
    field_id = Column(Integer, ForeignKey("fields.id"), nullable=False)
    name = Column(String(255), nullable=False)
    formation = Column(String(100), nullable=False)
    depth_ft = Column(Float, nullable=True)
    porosity_pct = Column(Float, nullable=True)
    permeability_md = Column(Float, nullable=True)
    api = Column(Float, nullable=True)
    viscosity_cp = Column(Float, nullable=True)
    oil_saturation_pct = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    field = relationship("Field", back_populates="reservoirs")
    screening_runs = relationship("ScreeningRun", back_populates="reservoir", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("ix_reservoir_field_id", "field_id"),
        Index("ix_reservoir_formation", "formation"),
    )
    
    def __repr__(self):
        return f"<Reservoir(name='{self.name}', formation='{self.formation}')>"


class ScreeningRun(Base):
    """Single EOR screening execution."""
    
    __tablename__ = "screening_runs"
    
    id = Column(Integer, primary_key=True)
    reservoir_id = Column(Integer, ForeignKey("reservoirs.id"), nullable=True)
    name = Column(String(255), nullable=True)  # For unnamed/ad-hoc screenings
    formation = Column(String(100), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    user = Column(String(100), nullable=True)
    status = Column(String(50), default="completed")  # completed, failed, pending
    
    # Input parameters
    depth_ft = Column(Float, nullable=False)
    porosity_pct = Column(Float, nullable=False)
    perm_md = Column(Float, nullable=False)
    api = Column(Float, nullable=False)
    visc_cp = Column(Float, nullable=False)
    so_pct = Column(Float, nullable=False)
    
    # Data quality
    data_quality_status = Column(String(50), nullable=True)
    data_readiness_pct = Column(Float, nullable=True)
    
    # Results
    recommended_technique = Column(String(255), nullable=True)
    recommendation_status = Column(String(50), nullable=True)
    recommendation_score = Column(Float, nullable=True)
    recommendation_mode = Column(String(50), nullable=True)  # ENGINEERING, FUZZY, ML, SYNTHESIS

    # Evidence and trace metadata
    input_payload = Column(JSON, nullable=True)
    rule_trace = Column(JSON, nullable=True)
    assumptions = Column(JSON, nullable=True)
    workbook_version = Column(String(100), nullable=True)
    rule_version = Column(String(50), nullable=True)
    fuzzy_model_version = Column(String(50), nullable=True)
    evidence_summary = Column(JSON, nullable=True)

    # Metadata
    model_version = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    reservoir = relationship("Reservoir", back_populates="screening_runs")
    eligibility_results = relationship("EligibilityResult", back_populates="screening_run", cascade="all, delete-orphan")
    fuzzy_results = relationship("FuzzyResult", back_populates="screening_run", cascade="all, delete-orphan")
    ml_results = relationship("MLResult", back_populates="screening_run", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("ix_screening_timestamp", "timestamp"),
        Index("ix_screening_reservoir_id", "reservoir_id"),
    )
    
    def __repr__(self):
        return f"<ScreeningRun(id={self.id}, technique='{self.recommended_technique}', timestamp='{self.timestamp}')>"


class EligibilityResult(Base):
    """Engineering eligibility result for a technique in a screening."""
    
    __tablename__ = "eligibility_results"
    
    id = Column(Integer, primary_key=True)
    screening_id = Column(Integer, ForeignKey("screening_runs.id"), nullable=False)
    technique = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False)  # PASS, CONDITIONAL, FAIL
    criteria_passed = Column(Integer, nullable=True)
    criteria_total = Column(Integer, nullable=True)
    details = Column(JSON, nullable=True)  # Store detailed criterion results
    
    # Relationships
    screening_run = relationship("ScreeningRun", back_populates="eligibility_results")
    
    __table_args__ = (
        Index("ix_eligibility_screening_id", "screening_id"),
        Index("ix_eligibility_technique", "technique"),
    )


class FuzzyResult(Base):
    """Fuzzy suitability results for a technique."""
    
    __tablename__ = "fuzzy_results"
    
    id = Column(Integer, primary_key=True)
    screening_id = Column(Integer, ForeignKey("screening_runs.id"), nullable=False)
    technique = Column(String(255), nullable=False)
    suitability_score = Column(Float, nullable=False)
    membership_scores = Column(JSON, nullable=True)  # Store per-parameter membership
    has_envelope = Column(Boolean, default=True)
    
    # Relationships
    screening_run = relationship("ScreeningRun", back_populates="fuzzy_results")
    
    __table_args__ = (
        Index("ix_fuzzy_screening_id", "screening_id"),
    )


class MLResult(Base):
    """Neural network inference results."""
    
    __tablename__ = "ml_results"
    
    id = Column(Integer, primary_key=True)
    screening_id = Column(Integer, ForeignKey("screening_runs.id"), nullable=False)
    technique = Column(String(255), nullable=False)
    probability = Column(Float, nullable=False)
    is_top_prediction = Column(Boolean, default=False)
    confidence = Column(Float, nullable=True)
    
    # Relationships
    screening_run = relationship("ScreeningRun", back_populates="ml_results")
    
    __table_args__ = (
        Index("ix_ml_screening_id", "screening_id"),
    )


class Scenario(Base):
    """Scenario: comparison of different input combinations."""
    
    __tablename__ = "scenarios"
    
    id = Column(Integer, primary_key=True)
    base_screening_id = Column(Integer, ForeignKey("screening_runs.id"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Modifications to base case
    modifications = Column(JSON, nullable=True)  # Store parameter changes
    
    created_by = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<Scenario(name='{self.name}')>"


class ModelVersion(Base):
    """Track ML model versions used for screening."""
    
    __tablename__ = "model_versions"
    
    id = Column(Integer, primary_key=True)
    version = Column(String(50), unique=True, nullable=False)
    algorithm = Column(String(100), nullable=False)
    framework = Column(String(100), nullable=False)
    training_date = Column(DateTime, nullable=True)
    training_samples = Column(Integer, nullable=True)
    
    # Performance metrics
    test_accuracy = Column(Float, nullable=True)
    test_weighted_f1 = Column(Float, nullable=True)
    
    # Metadata
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    def __repr__(self):
        return f"<ModelVersion(version='{self.version}', accuracy={self.test_accuracy})>"


class RuleVersion(Base):
    """Track engineering rule versions."""
    
    __tablename__ = "rule_versions"
    
    id = Column(Integer, primary_key=True)
    version = Column(String(50), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    effective_date = Column(DateTime, default=datetime.utcnow)
    rules_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)


class AuditEvent(Base):
    """Audit trail for all significant actions."""
    
    __tablename__ = "audit_events"
    
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    user = Column(String(100), nullable=True)
    action = Column(String(100), nullable=False)  # CREATE, UPDATE, DELETE, SCREENING, etc.
    object_type = Column(String(100), nullable=False)
    object_id = Column(Integer, nullable=True)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    details = Column(JSON, nullable=True)
    
    __table_args__ = (
        Index("ix_audit_timestamp", "timestamp"),
        Index("ix_audit_action", "action"),
    )


# Database initialization and session management
class DatabaseManager:
    """Manages database connections and sessions."""
    
    _engine = None
    _Session = None
    
    @classmethod
    def init_db(cls, db_path: Path = DB_PATH) -> None:
        """
        Initialize database.
        
        Args:
            db_path: Path to SQLite database file
        """
        logger.info(f"Initializing database at {db_path}")
        
        db_url = f"sqlite:///{db_path}"
        cls._engine = create_engine(db_url, echo=False)
        cls._Session = sessionmaker(bind=cls._engine)
        
        # Create tables
        Base.metadata.create_all(cls._engine)
        cls._ensure_screening_run_columns()
        logger.info("Database tables created successfully")

    @classmethod
    def _ensure_screening_run_columns(cls):
        """Add missing screening_run columns for older SQLite databases."""
        if cls._engine is None:
            return

        try:
            inspector = inspect(cls._engine)
            tables = inspector.get_table_names()
            if "screening_runs" not in tables:
                return

            existing_columns = {column["name"] for column in inspector.get_columns("screening_runs")}
            required_columns = [
                "data_quality_status",
                "data_readiness_pct",
                "recommendation_mode",
                "input_payload",
                "rule_trace",
                "assumptions",
                "workbook_version",
                "rule_version",
                "fuzzy_model_version",
                "evidence_summary",
                "model_version",
            ]

            with cls._engine.begin() as connection:
                for column_name in required_columns:
                    if column_name not in existing_columns:
                        col_type = "TEXT" if column_name in {"data_quality_status", "recommendation_mode", "workbook_version", "rule_version", "fuzzy_model_version", "model_version"} else "TEXT"
                        connection.execute(text(f"ALTER TABLE screening_runs ADD COLUMN {column_name} {col_type}"))
                        logger.info(f"Added missing database column: screening_runs.{column_name}")
        except Exception as exc:
            logger.warning(f"Schema compatibility check failed: {exc}")
    
    @classmethod
    def get_session(cls):
        """Get database session."""
        if cls._Session is None:
            cls.init_db()
        
        return cls._Session()
    
    @classmethod
    def close(cls) -> None:
        """Close database connection."""
        if cls._engine:
            cls._engine.dispose()
            logger.info("Database connection closed")


def init_database() -> None:
    """Initialize database on application startup."""
    DatabaseManager.init_db(DB_PATH)
    logger.info("Database ready for use")
