import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.database import Base


class InferenceLog(Base):
    """
    Represents an audit log record for a successful model inference.
    Stores metadata about the request, the dataset, the model, and the predictions.
    """

    __tablename__ = "inference_logs"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(
        UUID(as_uuid=True),
        default=uuid.uuid4,
        unique=True,
        index=True,
        nullable=False,
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    dataset_id = Column(
        Integer,
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    model_id = Column(
        Integer,
        ForeignKey("trained_models.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    inference_type = Column(String, nullable=False)  # "single" or "batch"
    
    input_data = Column(JSONB, nullable=False)
    prediction_data = Column(JSONB, nullable=False)
    row_count = Column(Integer, nullable=False)

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    user = relationship("User", backref="inference_logs")
    dataset = relationship("Dataset", backref="inference_logs")
    model = relationship("TrainedModel", backref="inference_logs")
