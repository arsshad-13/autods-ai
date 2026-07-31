from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RecommendationSchema(BaseModel):
    id: str
    action: str
    recommendation: str
    reason: str
    affected_columns: list[str]
    estimated_impact: str


class ApplyPreprocessingRequest(BaseModel):
    selected_actions: list[str] = Field(..., description="List of recommendation IDs to apply")


class DatasetPreprocessingResponse(BaseModel):
    uuid: UUID
    dataset_id: int
    recommendations: list[RecommendationSchema] | None = None
    actions_applied: list[RecommendationSchema] | None = None
    processing_summary: dict[str, Any] | None = None
    clean_dataset_path: str | None = None
    quality_before: float | dict[str, Any] | None = None
    quality_after: float | dict[str, Any] | None = None
    processing_time: float | None = None
    status: str
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
