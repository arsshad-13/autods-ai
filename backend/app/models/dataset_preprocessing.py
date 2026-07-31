import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.database import Base


class DatasetPreprocessing(Base):
    """
    Stores preprocessing recommendations and execution metadata for a dataset.
    """

    __tablename__ = "dataset_preprocessing"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(
        UUID(as_uuid=True),
        default=uuid.uuid4,
        unique=True,
        index=True,
        nullable=False,
    )

    dataset_id = Column(
        Integer,
        ForeignKey("datasets.id", ondelete="CASCADE"),
        unique=True,  # One-to-one relationship
        nullable=False,
        index=True,
    )

    # Generated preprocessing recommendations (JSON)
    recommendations = Column(JSONB, nullable=True)

    # Actions actually selected and applied by the user
    actions_applied = Column(JSONB, nullable=True)
    
    # Summary of what was processed (e.g. "Removed 12 duplicate rows")
    processing_summary = Column(JSONB, nullable=True)

    # Path to the separately stored, versioned cleaned dataset
    clean_dataset_path = Column(String, nullable=True)

    # Quality metrics
    quality_before = Column(JSONB, nullable=True)
    quality_after = Column(JSONB, nullable=True)

    processing_time = Column(Float, nullable=True)

    # NOT_GENERATED, PLAN_GENERATED, APPLYING, COMPLETED, FAILED
    status = Column(String, nullable=False, default="NOT_GENERATED")
    error_message = Column(String, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationship back to Dataset
    dataset = relationship("Dataset", back_populates="preprocessing")
