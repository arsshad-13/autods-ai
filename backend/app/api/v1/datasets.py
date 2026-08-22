from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, UploadFile, status, BackgroundTasks, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_active_user
from app.database import get_db
from app.models.user import User
from app.schemas.dataset import DatasetListResponse, DatasetResponse
from app.schemas.dataset_profile import DatasetProfileResponse
from app.services import dataset_service

router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.post(
    "/",
    response_model=DatasetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a dataset",
)
async def upload_dataset(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> DatasetResponse:
    """
    Upload a dataset file (.csv, .xlsx, .xls).

    Maximum file size is 100 MB.  The file is stored on disk using a
    UUID-generated filename; the original filename is preserved in the database.
    """
    dataset = await dataset_service.save_upload(
        file=file,
        user_id=current_user.id,
        db=db,
    )
    return DatasetResponse.model_validate(dataset)


@router.get(
    "/",
    response_model=DatasetListResponse,
    summary="List all datasets for the current user",
)
async def list_datasets(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> DatasetListResponse:
    """
    Return a paginated list of datasets owned by the authenticated user.
    """
    total, items = await dataset_service.list_datasets(
        user_id=current_user.id,
        db=db,
        page=page,
        page_size=page_size,
    )
    return DatasetListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[DatasetResponse.model_validate(d) for d in items],
    )


@router.get(
    "/{dataset_uuid}",
    response_model=DatasetResponse,
    summary="Get dataset metadata",
)
async def get_dataset(
    dataset_uuid: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> DatasetResponse:
    """
    Return metadata for a single dataset.  Users may only access their own datasets.
    """
    dataset = await dataset_service.get_dataset(
        dataset_uuid=dataset_uuid,
        user_id=current_user.id,
        db=db,
    )
    return DatasetResponse.model_validate(dataset)


@router.delete(
    "/{dataset_uuid}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a dataset",
)
async def delete_dataset(
    dataset_uuid: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Permanently delete a dataset: removes the database record and the file on disk.
    Users may only delete their own datasets.
    """
    await dataset_service.delete_dataset(
        dataset_uuid=dataset_uuid,
        user_id=current_user.id,
        db=db,
    )


@router.post(
    "/{dataset_uuid}/profile",
    response_model=DatasetResponse,
    summary="Trigger dataset profiling analysis",
)
async def trigger_profiling(
    dataset_uuid: UUID,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> DatasetResponse:
    """
    Trigger the profiling engine to analyze the dataset.
    This runs asynchronously in the background.
    """
    # 1. Fetch dataset and verify ownership
    dataset = await dataset_service.get_dataset(
        dataset_uuid=dataset_uuid,
        user_id=current_user.id,
        db=db,
    )

    # Reject duplicate concurrent requests
    if dataset.status in ("pending", "profiling"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A profiling job is already in progress for this dataset."
        )

    # 2. Set status to pending and reset error message
    dataset.status = "pending"
    dataset.error_message = None
    db.add(dataset)
    await db.commit()
    await db.refresh(dataset)


    # 3. Define background task wrapper
    async def run_profiling_task(d_id: int, f_path: str):
        from app.database import AsyncSessionLocal
        from app.services import profiling_service
        async with AsyncSessionLocal() as bg_db:
            try:
                await profiling_service.profile_dataset(d_id, f_path, bg_db)
            except Exception:
                # Logging is handled inside service
                pass

    # 4. Enqueue background task
    background_tasks.add_task(run_profiling_task, dataset.id, dataset.file_path)

    return DatasetResponse.model_validate(dataset)


@router.get(
    "/{dataset_uuid}/profile",
    response_model=DatasetProfileResponse,
    summary="Retrieve dataset profiling report",
)
async def get_dataset_profile(
    dataset_uuid: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> DatasetProfileResponse:
    """
    Get the completed profile of a dataset.
    Only the dataset owner may retrieve the profile.
    """
    # 1. Fetch dataset and verify ownership
    dataset = await dataset_service.get_dataset(
        dataset_uuid=dataset_uuid,
        user_id=current_user.id,
        db=db,
    )

    # 2. Query profile
    from sqlalchemy import select
    from app.models.dataset_profile import DatasetProfile

    stmt = select(DatasetProfile).where(DatasetProfile.dataset_id == dataset.id)
    result = await db.execute(stmt)
    profile = result.scalar_one_or_none()

    if not profile:
        raise HTTPException(
            status_code=404,
            detail="Profile not found. Please analyze the dataset first."
        )

    return DatasetProfileResponse.model_validate(profile)


from app.schemas.dataset_preprocessing import DatasetPreprocessingResponse, ApplyPreprocessingRequest
from app.services import preprocessing_service
from fastapi.responses import FileResponse
from pathlib import Path


@router.post(
    "/{dataset_uuid}/preprocess/plan",
    response_model=DatasetPreprocessingResponse,
    summary="Generate a preprocessing plan",
)
async def generate_preprocessing_plan(
    dataset_uuid: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> DatasetPreprocessingResponse:
    """
    Generate preprocessing recommendations based on dataset profile.
    """
    plan = await preprocessing_service.generate_preprocessing_plan(
        dataset_uuid=dataset_uuid,
        user_id=current_user.id,
        db=db,
    )
    return DatasetPreprocessingResponse.model_validate(plan)


@router.get(
    "/{dataset_uuid}/preprocess/plan",
    response_model=DatasetPreprocessingResponse,
    summary="Get preprocessing plan",
)
async def get_preprocessing_plan(
    dataset_uuid: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> DatasetPreprocessingResponse:
    """
    Get the existing preprocessing plan for a dataset.
    """
    plan = await preprocessing_service.get_preprocessing_plan(
        dataset_uuid=dataset_uuid,
        user_id=current_user.id,
        db=db,
    )
    if not plan:
        raise HTTPException(status_code=404, detail="Preprocessing plan not found.")
    return DatasetPreprocessingResponse.model_validate(plan)


@router.post(
    "/{dataset_uuid}/preprocess/apply",
    response_model=DatasetPreprocessingResponse,
    summary="Apply preprocessing actions",
)
async def apply_preprocessing_plan(
    dataset_uuid: UUID,
    request: ApplyPreprocessingRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> DatasetPreprocessingResponse:
    """
    Apply user-selected preprocessing actions and create a versioned clean dataset.
    """
    plan = await preprocessing_service.apply_preprocessing_plan(
        dataset_uuid=dataset_uuid,
        user_id=current_user.id,
        selected_actions=request.selected_actions,
        db=db,
    )
    return DatasetPreprocessingResponse.model_validate(plan)


@router.get(
    "/{dataset_uuid}/preprocess/download",
    summary="Download cleaned dataset",
)
async def download_cleaned_dataset(
    dataset_uuid: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Download the latest cleaned dataset.
    """
    plan = await preprocessing_service.get_preprocessing_plan(
        dataset_uuid=dataset_uuid,
        user_id=current_user.id,
        db=db,
    )
    if not plan or not plan.clean_dataset_path or not Path(plan.clean_dataset_path).exists():
        raise HTTPException(status_code=404, detail="Cleaned dataset not found.")
        
    return FileResponse(
        path=plan.clean_dataset_path,
        filename=Path(plan.clean_dataset_path).name,
        media_type="application/octet-stream"
    )

from app.schemas.trained_model import TrainedModelResponse, ModelTrainingStartResponse, ModelTrainingStatusResponse
from app.services import model_training_service
from typing import List


@router.post(
    "/{dataset_uuid}/models/train",
    response_model=ModelTrainingStatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start asynchronous ML model training on the preprocessed dataset",
)
async def train_models(
    dataset_uuid: UUID,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> ModelTrainingStatusResponse:
    """
    Starts model training in the background and returns immediately.
    The response status will be RUNNING with PENDING placeholder model records.
    Poll GET /{dataset_uuid}/models/status to check progress.
    """
    placeholder_records, bg_params = await model_training_service.train_models(
        dataset_uuid=dataset_uuid,
        user_id=current_user.id,
        db=db,
    )

    background_tasks.add_task(
        model_training_service.run_model_training,
        **bg_params,
    )

    return ModelTrainingStatusResponse(
        message="Model training started successfully.",
        status="RUNNING",
        dataset_uuid=str(dataset_uuid),
        trained_models=[TrainedModelResponse.model_validate(r) for r in placeholder_records],
    )


@router.get(
    "/{dataset_uuid}/models",
    response_model=List[TrainedModelResponse],
    summary="List all trained models for a dataset",
)
async def get_models(
    dataset_uuid: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> List[TrainedModelResponse]:
    """
    Get all trained models for the specified dataset.
    """
    models = await model_training_service.get_trained_models(
        dataset_uuid=dataset_uuid,
        user_id=current_user.id,
        db=db,
    )
    return [TrainedModelResponse.model_validate(m) for m in models]


@router.get(
    "/{dataset_uuid}/models/best",
    response_model=TrainedModelResponse,
    summary="Get the best trained model",
)
async def get_best_model(
    dataset_uuid: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> TrainedModelResponse:
    """
    Get the best performing model automatically selected after training.
    """
    model = await model_training_service.get_best_model(
        dataset_uuid=dataset_uuid,
        user_id=current_user.id,
        db=db,
    )
    if not model:
        raise HTTPException(status_code=404, detail="No models trained for this dataset.")
    return TrainedModelResponse.model_validate(model)


@router.get(
    "/{dataset_uuid}/models/status",
    response_model=ModelTrainingStatusResponse,
    summary="Get the current training status and available model results",
)
async def get_training_status(
    dataset_uuid: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> ModelTrainingStatusResponse:
    """
    Returns the aggregate training status (NOT_STARTED | RUNNING | COMPLETED | FAILED)
    and all available model records for the dataset.
    Intended for frontend polling after starting a training job.
    """
    return await model_training_service.get_training_status(
        dataset_uuid=dataset_uuid,
        user_id=current_user.id,
        db=db,
    )


@router.get(
    "/{dataset_uuid}/models/{model_uuid}",
    response_model=TrainedModelResponse,
    summary="Get details of a specific trained model",
)
async def get_model(
    dataset_uuid: UUID,
    model_uuid: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> TrainedModelResponse:
    """
    Get details of a specific trained model by UUID.
    """
    model = await model_training_service.get_model(
        dataset_uuid=dataset_uuid,
        model_uuid=model_uuid,
        user_id=current_user.id,
        db=db,
    )
    return TrainedModelResponse.model_validate(model)


from app.schemas.model_inference import PredictionRequest, PredictionResponse, BatchPredictionRequest, BatchPredictionResponse
from app.services import model_inference_service

@router.post(
    "/{dataset_uuid}/models/{model_uuid}/predict",
    response_model=PredictionResponse,
    summary="Predict using a specific trained classification or regression model",
)
async def predict_model(
    dataset_uuid: UUID,
    model_uuid: UUID,
    request: PredictionRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> PredictionResponse:
    """
    Perform inference using a trained model.
    Pass a JSON object with a 'features' dictionary matching the model's expected schema.
    """
    return await model_inference_service.predict(
        dataset_uuid=dataset_uuid,
        model_uuid=model_uuid,
        user_id=current_user.id,
        request=request,
        db=db,
    )

@router.post(
    "/{dataset_uuid}/models/{model_uuid}/predict/batch",
    response_model=BatchPredictionResponse,
    summary="Batch predict using a specific trained classification or regression model",
)
async def predict_model_batch(
    dataset_uuid: UUID,
    model_uuid: UUID,
    request: BatchPredictionRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> BatchPredictionResponse:
    """
    Perform batch inference using a trained model.
    Pass a JSON object with a 'rows' array matching the model's expected schema.
    """
    return await model_inference_service.predict_batch(
        dataset_uuid=dataset_uuid,
        model_uuid=model_uuid,
        user_id=current_user.id,
        request=request,
        db=db,
    )


# ---------------------------------------------------------------------------
# Phase 7 — Optuna Hyperparameter Tuning endpoints
# ---------------------------------------------------------------------------

from app.services import tuning_service as _tuning_service
from app.schemas.tuning import TuneRequest, TuneStatusResponse


@router.post(
    "/{dataset_uuid}/models/{model_uuid}/tune",
    response_model=TuneStatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start Optuna hyperparameter tuning for a trained model",
)
async def tune_model(
    dataset_uuid: UUID,
    model_uuid: UUID,
    background_tasks: BackgroundTasks,
    request: TuneRequest = TuneRequest(),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> TuneStatusResponse:
    """
    Trigger Optuna hyperparameter optimisation on a COMPLETED trained model.

    - Authenticates the current user.
    - Verifies dataset and model ownership.
    - Prevents concurrent tuning of the same model.
    - Returns 202 immediately; tuning runs as a FastAPI BackgroundTask.
    - Poll GET /{dataset_uuid}/models/{model_uuid} and inspect
      metadata_info.tuning_status for progress.

    tuning_status values: QUEUED | RUNNING | COMPLETED | FAILED
    """
    model = await _tuning_service.validate_model_for_tuning(
        dataset_uuid=dataset_uuid,
        model_uuid=model_uuid,
        user_id=current_user.id,
        db=db,
    )

    # Mark as QUEUED synchronously so subsequent poll calls see it immediately
    meta = dict(model.metadata_info or {})
    meta["tuning_status"] = "QUEUED"
    meta["tuning_n_trials"] = request.n_trials
    model.metadata_info = meta
    db.add(model)
    await db.commit()
    await db.refresh(model)

    background_tasks.add_task(
        _tuning_service.run_tuning,
        dataset_uuid=str(dataset_uuid),
        model_uuid=str(model_uuid),
        user_id=current_user.id,
        n_trials=request.n_trials,
    )

    return TuneStatusResponse(
        model_uuid=str(model_uuid),
        dataset_uuid=str(dataset_uuid),
        algorithm=model.algorithm,
        tuning_status="QUEUED",
        n_trials=request.n_trials,
        message=(
            f"Hyperparameter tuning queued for '{model.algorithm}' with "
            f"{request.n_trials} trials. "
            "Poll GET /datasets/{dataset_uuid}/models/{model_uuid} for status."
        ),
    )
