from typing import Any, Dict, Optional, List
from uuid import UUID
from pydantic import BaseModel, Field

class PredictionRequest(BaseModel):
    features: Dict[str, Any] = Field(..., description="Dictionary of feature names and values matching the model's schema.")

class PredictionResponse(BaseModel):
    dataset_uuid: str
    model_uuid: str
    model_name: str
    prediction: Any
    predicted_label: Optional[str] = None
    probabilities: Optional[Dict[str, float]] = None

class BatchPredictionRequest(BaseModel):
    rows: List[Dict[str, Any]] = Field(..., description="List of dictionaries of feature names and values matching the model's schema.")

class BatchPredictionRowResponse(BaseModel):
    row_index: int
    prediction: Any
    predicted_label: Optional[str] = None
    probabilities: Optional[Dict[str, float]] = None

class BatchPredictionResponse(BaseModel):
    dataset_uuid: str
    model_uuid: str
    model_name: str
    predictions: List[BatchPredictionRowResponse]
    total_rows: int
