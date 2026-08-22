from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel


class InferenceHistoryItem(BaseModel):
    """Summary view of a single inference log record (no large payloads)."""

    id: int
    uuid: UUID
    user_id: int
    dataset_uuid: UUID
    model_uuid: UUID
    model_name: str
    inference_type: str  # "single" | "batch"
    row_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class InferenceHistoryDetail(InferenceHistoryItem):
    """Full detail view — includes input and prediction payloads."""

    input_data: Any
    prediction_data: Any


class InferenceHistoryPaginated(BaseModel):
    """Paginated response for GET /inference/history."""

    records: List[InferenceHistoryItem]
    page: int
    page_size: int
    total: int
