import logging
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inference_log import InferenceLog
from app.models.dataset import Dataset
from app.models.trained_model import TrainedModel
from app.schemas.inference_history import (
    InferenceHistoryDetail,
    InferenceHistoryItem,
    InferenceHistoryPaginated,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers — build response schemas from ORM rows
# ---------------------------------------------------------------------------

def _build_item(log: InferenceLog) -> InferenceHistoryItem:
    """Map an InferenceLog ORM object to an InferenceHistoryItem schema."""
    return InferenceHistoryItem(
        id=log.id,
        uuid=log.uuid,
        user_id=log.user_id,
        dataset_uuid=log.dataset.uuid,
        model_uuid=log.model.uuid,
        model_name=log.model.name,
        inference_type=log.inference_type,
        row_count=log.row_count,
        created_at=log.created_at,
    )


def _build_detail(log: InferenceLog) -> InferenceHistoryDetail:
    """Map an InferenceLog ORM object to an InferenceHistoryDetail schema."""
    return InferenceHistoryDetail(
        id=log.id,
        uuid=log.uuid,
        user_id=log.user_id,
        dataset_uuid=log.dataset.uuid,
        model_uuid=log.model.uuid,
        model_name=log.model.name,
        inference_type=log.inference_type,
        row_count=log.row_count,
        created_at=log.created_at,
        input_data=log.input_data,
        prediction_data=log.prediction_data,
    )


# ---------------------------------------------------------------------------
# log_inference
# ---------------------------------------------------------------------------

async def log_inference(
    *,
    db: AsyncSession,
    user_id: int,
    dataset_id: int,
    model_id: int,
    inference_type: str,
    input_data: object,
    prediction_data: object,
    row_count: int,
) -> Optional[InferenceLog]:
    """
    Persist a successful inference record.

    Returns the created InferenceLog on success or None on failure.
    Logging errors are non-fatal: a failed audit write must never cause
    an otherwise successful prediction to appear as an error.
    """
    try:
        log = InferenceLog(
            user_id=user_id,
            dataset_id=dataset_id,
            model_id=model_id,
            inference_type=inference_type,
            input_data=input_data,
            prediction_data=prediction_data,
            row_count=row_count,
        )
        db.add(log)
        await db.commit()
        await db.refresh(log)
        return log
    except Exception as exc:
        logger.error(f"Failed to persist inference log: {exc}")
        await db.rollback()
        return None


# ---------------------------------------------------------------------------
# get_inference_history
# ---------------------------------------------------------------------------

async def get_inference_history(
    *,
    db: AsyncSession,
    user_id: int,
    page: int = 1,
    page_size: int = 20,
) -> InferenceHistoryPaginated:
    """
    Return a paginated list of inference log summaries owned by the user.
    Records are ordered newest-first.
    """
    offset = (page - 1) * page_size

    # Total count
    count_stmt = (
        select(func.count())
        .select_from(InferenceLog)
        .where(InferenceLog.user_id == user_id)
    )
    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()

    # Paginated records — eager-load related dataset/model for UUID/name
    records_stmt = (
        select(InferenceLog)
        .where(InferenceLog.user_id == user_id)
        .order_by(InferenceLog.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(records_stmt)
    logs = result.scalars().all()

    # Eagerly load relationships that are lazily declared
    items = []
    for log in logs:
        # Access dataset/model via already-loaded relationship or explicit fetch
        await db.refresh(log, ["dataset", "model"])
        items.append(_build_item(log))

    return InferenceHistoryPaginated(
        records=items,
        page=page,
        page_size=page_size,
        total=total,
    )


# ---------------------------------------------------------------------------
# get_inference_detail
# ---------------------------------------------------------------------------

async def get_inference_detail(
    *,
    db: AsyncSession,
    inference_uuid: UUID,
    user_id: int,
) -> InferenceHistoryDetail:
    """
    Return the full detail of a single inference log.
    Enforces ownership: returns 404 if the record does not exist or belongs
    to a different user (no information leakage).
    """
    stmt = (
        select(InferenceLog)
        .where(
            InferenceLog.uuid == inference_uuid,
            InferenceLog.user_id == user_id,
        )
    )
    result = await db.execute(stmt)
    log = result.scalar_one_or_none()

    if log is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inference record not found.",
        )

    await db.refresh(log, ["dataset", "model"])
    return _build_detail(log)
