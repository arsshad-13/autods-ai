import uuid
from datetime import datetime, timezone

from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class Dataset(Base):
    """
    Represents a user-uploaded dataset file.

    Files are stored on disk under settings.UPLOAD_DIR using UUID-based filenames.
    The original filename is preserved separately for display purposes only.
    """

    __tablename__ = "datasets"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(
        UUID(as_uuid=True),
        default=uuid.uuid4,
        unique=True,
        index=True,
        nullable=False,
    )

    # Ownership — FK to users.id with cascade delete
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # File metadata
    original_filename = Column(String, nullable=False)   # sanitised original name shown in UI
    stored_filename = Column(String, nullable=False)     # UUID-based name on disk
    file_path = Column(String, nullable=False)           # full relative path inside UPLOAD_DIR
    file_size = Column(BigInteger, nullable=False)       # bytes
    mime_type = Column(String, nullable=False)
    extension = Column(String, nullable=False)           # .csv / .xlsx / .xls

    # Processing lifecycle — future milestones will advance this
    status = Column(String, nullable=False, default="uploaded")
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

    # Relationship back to User (for ORM navigation if needed)
    owner = relationship("User", back_populates="datasets")

    # 1-to-1 relationship with DatasetProfile
    profile = relationship(
        "DatasetProfile",
        back_populates="dataset",
        uselist=False,
        cascade="all, delete-orphan",
    )

