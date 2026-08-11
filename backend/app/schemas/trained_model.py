from datetime import datetime
from typing import Any, Dict, Optional, List
from uuid import UUID

from pydantic import BaseModel, Field


class TrainedModelBase(BaseModel):
    name: str
    algorithm: str
    task_type: str
    target_column: str


class TrainedModelCreate(TrainedModelBase):
    pass


class TrainedModelUpdate(BaseModel):
    status: Optional[str] = None
    metrics: Optional[Dict[str, Any]] = None
    hyperparameters: Optional[Dict[str, Any]] = None
    metadata_info: Optional[Dict[str, Any]] = None
    training_duration: Optional[float] = None
    model_path: Optional[str] = None
    is_best: Optional[bool] = None
    error_message: Optional[str] = None


class TrainedModelResponse(TrainedModelBase):
    id: int
    uuid: UUID
    dataset_id: int
    status: str
    metrics: Optional[Dict[str, Any]] = None
    hyperparameters: Optional[Dict[str, Any]] = None
    metadata_info: Optional[Dict[str, Any]] = None
    training_duration: Optional[float] = None
    model_path: Optional[str] = None
    is_best: bool
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ModelTrainingStartResponse(BaseModel):
    message: str
    trained_models: List[TrainedModelResponse]


class ModelTrainingStatusResponse(BaseModel):
    """
    Returned by both the start-training endpoint (POST /models/train)
    and the status-polling endpoint (GET /models/status).
    """

    message: str
    status: str  # NOT_STARTED | RUNNING | COMPLETED | FAILED
    dataset_uuid: str
    trained_models: List[TrainedModelResponse]
    error_message: Optional[str] = None
