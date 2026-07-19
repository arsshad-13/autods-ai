from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DatasetResponse(BaseModel):
    """Full dataset metadata returned to the API client."""

    id: int
    uuid: UUID
    original_filename: str
    file_size: int
    mime_type: str
    extension: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DatasetListResponse(BaseModel):
    """Paginated list of datasets."""

    total: int
    page: int
    page_size: int
    items: list[DatasetResponse]
