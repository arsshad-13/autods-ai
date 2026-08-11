import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Boolean
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.database import Base


class TrainedModel(Base):
    """
    Represents a machine learning model trained on a preprocessed dataset.
    Stores metadata, metrics, and the file path to the persisted joblib model.
    """

    __tablename__ = "trained_models"

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
        nullable=False,
        index=True,
    )

    name = Column(String, nullable=False)
    algorithm = Column(String, nullable=False)
    task_type = Column(String, nullable=False)  # Classification, Regression, Forecasting
    target_column = Column(String, nullable=False)

    # PENDING, RUNNING, COMPLETED, FAILED
    status = Column(String, nullable=False, default="PENDING")
    
    # Store dynamic data like metrics (RMSE, MAE, R2, Accuracy, etc.) and hyperparameters
    metrics = Column(JSONB, nullable=True)
    hyperparameters = Column(JSONB, nullable=True)
    
    # Add additional metadata like feature columns, test/train rows, random state
    metadata_info = Column(JSONB, nullable=True)
    
    training_duration = Column(Float, nullable=True)  # in seconds
    model_path = Column(String, nullable=True)  # Path relative to UPLOAD_DIR/models

    is_best = Column(Boolean, nullable=False, default=False)
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
    dataset = relationship("Dataset", backref="trained_models")
