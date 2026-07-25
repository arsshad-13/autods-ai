import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Float, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class DatasetProfile(Base):
    """
    Represents the computed statistics, preview, quality score, and ML recommendation
    for a user's uploaded dataset. Stored as structured columns for quick queries
    and raw JSON for detailed profiling results.
    """

    __tablename__ = "dataset_profiles"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(
        UUID(as_uuid=True),
        default=uuid.uuid4,
        unique=True,
        index=True,
        nullable=False,
    )

    # 1-to-1 relationship with Dataset
    dataset_id = Column(
        Integer,
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Frequently queried profiling metrics stored as separate columns
    quality_score = Column(Float, nullable=False, default=100.0)
    quality_level = Column(String, nullable=False, default="Excellent")  # Excellent, Good, Fair, Poor
    recommended_task = Column(String, nullable=False)  # Classification, Regression, Clustering, Time Series
    recommended_target = Column(String, nullable=True)  # detected target column (nullable)
    row_count = Column(Integer, nullable=False, default=0)
    column_count = Column(Integer, nullable=False, default=0)

    # Full dictionary containing detailed profiling values (statistics, preview, distribution, etc.)
    profile_data = Column(JSON, nullable=False)

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
    dataset = relationship("Dataset", back_populates="profile")
