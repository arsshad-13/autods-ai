from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_active_user
from app.database import get_db
from app.models.user import User
from app.schemas.inference_history import (
    InferenceHistoryDetail,
    InferenceHistoryPaginated,
)
from app.services import inference_history_service

router = APIRouter(prefix="/inference", tags=["inference"])

_MAX_PAGE_SIZE = 100


@router.get(
    "/history",
    response_model=InferenceHistoryPaginated,
    summary="List inference history for the current user",
)
async def list_inference_history(
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(
        default=20, ge=1, le=_MAX_PAGE_SIZE, description="Records per page"
    ),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> InferenceHistoryPaginated:
    """
    Return the authenticated user's inference history, newest first.
    Supports pagination via `page` and `page_size` query parameters.
    """
    return await inference_history_service.get_inference_history(
        db=db,
        user_id=current_user.id,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/history/{inference_uuid}",
    response_model=InferenceHistoryDetail,
    summary="Get detailed inference record",
)
async def get_inference_detail(
    inference_uuid: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> InferenceHistoryDetail:
    """
    Return the full detail of a single inference record.
    Input data and prediction data are included.
    Returns 404 if the record does not exist or belongs to another user.
    """
    return await inference_history_service.get_inference_detail(
        db=db,
        inference_uuid=inference_uuid,
        user_id=current_user.id,
    )
