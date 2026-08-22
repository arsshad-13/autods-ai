"""
schemas/tuning.py
=================
Pydantic request/response schemas for Phase 7 Optuna hyperparameter tuning.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class TuneRequest(BaseModel):
    """
    Optional request body for POST /datasets/{uuid}/models/{uuid}/tune.

    n_trials: Number of Optuna trials to run.
      - Default: 30 (sensible for a local machine).
      - Increase for larger datasets / more complex search spaces.
      - Minimum: 1  (allows single-trial sanity checks).
      - Maximum: 200 (prevents unreasonably long runs via the API).
    """
    n_trials: int = Field(
        default=30,
        ge=1,
        le=200,
        description="Number of Optuna hyperparameter search trials.",
    )


class TuneStatusResponse(BaseModel):
    """
    Response returned immediately (HTTP 202) when tuning is queued.
    Frontend should poll GET /datasets/{uuid}/models/{model_uuid} and
    read metadata_info.tuning_status for live progress.
    """
    model_uuid: str
    dataset_uuid: str
    algorithm: str
    tuning_status: str  # QUEUED | RUNNING | COMPLETED | FAILED
    n_trials: int
    message: str


class TrialResult(BaseModel):
    """Summary of a single Optuna trial for frontend display."""
    trial_number: int
    score: float
    params: Dict[str, Any]
    state: str  # COMPLETE | PRUNED | FAIL


class TuningResult(BaseModel):
    """
    Rich tuning summary embedded in TrainedModelResponse.metadata_info.
    Exposed to the frontend via the existing GET /models/{uuid} endpoint.
    """
    tuning_status: str              # QUEUED | RUNNING | COMPLETED | FAILED
    tuning_n_trials: int
    tuning_best_trial: Optional[int] = None
    tuning_best_score: Optional[float] = None
    tuning_best_params: Optional[Dict[str, Any]] = None
    tuning_metric: Optional[str] = None
    tuning_duration: Optional[float] = None
    tuning_improved: Optional[bool] = None
    tuning_baseline_score: Optional[float] = None
    tuning_tuned_score: Optional[float] = None
    tuning_all_trials: Optional[List[TrialResult]] = None
    tuning_error: Optional[str] = None
