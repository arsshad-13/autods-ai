from datetime import datetime
from uuid import UUID
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict


class DatasetProfileResponse(BaseModel):
    """Schema representing the dataset profiling metadata and results."""

    id: int
    uuid: UUID
    dataset_id: int
    quality_score: float
    quality_level: str
    recommended_task: str
    recommended_target: Optional[str] = None
    row_count: int
    column_count: int
    profile_data: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
