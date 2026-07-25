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
