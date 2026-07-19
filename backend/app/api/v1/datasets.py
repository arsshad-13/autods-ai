from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_active_user
from app.database import get_db
from app.models.user import User
from app.schemas.dataset import DatasetListResponse, DatasetResponse
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
