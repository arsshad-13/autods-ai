"""
M9.4 Test Suite — Inference History & Audit Logging

Tests:
  A. Single inference creates an audit log
  B. Batch inference creates an audit log
  C. Pagination on GET /inference/history
  D. GET /inference/history/{uuid} detail
  E. Ownership protection — cannot see another user's logs
  F. Invalid UUID returns 404
  G. Failed/invalid prediction does NOT create a log
  H. Empty batch does NOT create a log
  I. M9.1 / M9.2 / M9.3 regressions
"""

import asyncio
import os
import sys
from uuid import UUID

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))

from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.dataset import Dataset
from app.models.inference_log import InferenceLog
from app.schemas.model_inference import PredictionRequest, BatchPredictionRequest
from app.services.model_inference_service import predict, predict_batch
from app.services.inference_history_service import (
    get_inference_history,
    get_inference_detail,
)
from fastapi import HTTPException

DATASET_UUID = UUID("25489deb-33b8-4aca-990f-c6b7562d5ae3")
MODEL_UUID = UUID("39a6a38f-2a04-4f07-8e77-a2e68c671110")

VALID_SINGLE_FEATURES = {"age": 35, "income": 65000, "credit_score": 720}

BATCH_ROWS = [
    {"age": 35, "income": 65000, "credit_score": 720},
    {"age": 29, "income": 41000, "credit_score": 600},
    {"age": 45, "income": 85000, "credit_score": 760},
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_dataset_owner(db) -> int:
    stmt = select(Dataset).where(Dataset.uuid == DATASET_UUID)
    result = await db.execute(stmt)
    dataset = result.scalar_one_or_none()
    assert dataset is not None, "Dataset not found in DB"
    return dataset.user_id


async def _count_logs(db, user_id: int, inference_type: str | None = None) -> int:
    stmt = select(InferenceLog).where(InferenceLog.user_id == user_id)
    if inference_type:
        stmt = stmt.where(InferenceLog.inference_type == inference_type)
    result = await db.execute(stmt)
    return len(result.scalars().all())


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------

async def run_tests():
    print("=" * 60)
    print("  M9.4 — Inference History & Audit Logging Tests")
    print("=" * 60)

    async with AsyncSessionLocal() as db:
        user_id = await _get_dataset_owner(db)

        # ---------------------------------------------------------------
        # A. Single inference creates audit log
        # ---------------------------------------------------------------
        print("\nA. Single inference audit log...")
        single_before = await _count_logs(db, user_id, "single")
        payload = PredictionRequest(features=VALID_SINGLE_FEATURES)
        resp = await predict(DATASET_UUID, MODEL_UUID, user_id, payload, db)
        assert resp.prediction is not None, "predict() returned no prediction"
        assert resp.predicted_label in ["Yes", "No"], "predicted_label not mapped"
        single_after = await _count_logs(db, user_id, "single")
        assert single_after == single_before + 1, (
            f"Expected {single_before + 1} single logs, got {single_after}"
        )

        # Verify detail of the freshest log
        stmt = (
            select(InferenceLog)
            .where(InferenceLog.user_id == user_id, InferenceLog.inference_type == "single")
            .order_by(InferenceLog.created_at.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        log = result.scalar_one()
        await db.refresh(log, ["dataset", "model"])
        assert log.row_count == 1, f"row_count should be 1, got {log.row_count}"
        assert str(log.dataset.uuid) == str(DATASET_UUID)
        assert str(log.model.uuid) == str(MODEL_UUID)
        assert log.input_data == VALID_SINGLE_FEATURES, "input_data mismatch"
        assert "prediction" in log.prediction_data, "prediction_data missing 'prediction'"
        print(f"  [PASS] Single log created — row_count={log.row_count}, "
              f"label={log.prediction_data.get('predicted_label')}")

        # ---------------------------------------------------------------
        # B. Batch inference creates audit log
        # ---------------------------------------------------------------
        print("\nB. Batch inference audit log...")
        batch_before = await _count_logs(db, user_id, "batch")
        batch_payload = BatchPredictionRequest(rows=BATCH_ROWS)
        batch_resp = await predict_batch(DATASET_UUID, MODEL_UUID, user_id, batch_payload, db)
        assert batch_resp.total_rows == 3
        batch_after = await _count_logs(db, user_id, "batch")
        assert batch_after == batch_before + 1, (
            f"Expected {batch_before + 1} batch logs, got {batch_after}"
        )

        stmt = (
            select(InferenceLog)
            .where(InferenceLog.user_id == user_id, InferenceLog.inference_type == "batch")
            .order_by(InferenceLog.created_at.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        blog = result.scalar_one()
        await db.refresh(blog, ["dataset", "model"])
        assert blog.row_count == 3, f"row_count should be 3, got {blog.row_count}"
        assert isinstance(blog.input_data, list), "batch input_data should be a list"
        assert len(blog.input_data) == 3
        assert "predictions" in blog.prediction_data, "prediction_data missing 'predictions'"
        print(f"  [PASS] Batch log created — row_count={blog.row_count}, "
              f"total_rows={blog.prediction_data.get('total_rows')}")

        # ---------------------------------------------------------------
        # C. Pagination
        # ---------------------------------------------------------------
        print("\nC. Pagination...")
        page_result = await get_inference_history(db=db, user_id=user_id, page=1, page_size=10)
        assert page_result.page == 1
        assert page_result.page_size == 10
        assert page_result.total >= 2, "Expected at least 2 total records"
        assert len(page_result.records) >= 1
        # Newest first — created_at of first record >= second record
        if len(page_result.records) >= 2:
            assert page_result.records[0].created_at >= page_result.records[1].created_at, (
                "Records not ordered newest-first"
            )
        # Page 2 with page_size=1
        page2 = await get_inference_history(db=db, user_id=user_id, page=2, page_size=1)
        assert page2.page == 2
        assert page2.page_size == 1
        assert page2.total >= 2
        print(f"  [PASS] Pagination — total={page_result.total}, "
              f"page1 records={len(page_result.records)}, page2 records={len(page2.records)}")

        # ---------------------------------------------------------------
        # D. Detail endpoint
        # ---------------------------------------------------------------
        print("\nD. Detail endpoint...")
        # Reuse the single log UUID from test A
        await db.refresh(log, ["dataset", "model"])
        detail = await get_inference_detail(db=db, inference_uuid=log.uuid, user_id=user_id)
        assert detail.inference_type == "single"
        assert detail.row_count == 1
        assert detail.input_data == VALID_SINGLE_FEATURES
        assert "prediction" in detail.prediction_data
        assert str(detail.dataset_uuid) == str(DATASET_UUID)
        assert str(detail.model_uuid) == str(MODEL_UUID)
        print(f"  [PASS] Detail returned for UUID={log.uuid}")

        # ---------------------------------------------------------------
        # E. Ownership protection
        # ---------------------------------------------------------------
        print("\nE. Ownership protection...")
        try:
            await get_inference_detail(
                db=db, inference_uuid=log.uuid, user_id=99999
            )
            print("  [FAIL] Expected 404 for unauthorized user")
            assert False, "Should have raised HTTPException"
        except HTTPException as e:
            assert e.status_code == 404, f"Expected 404, got {e.status_code}"
            print(f"  [PASS] Foreign user gets 404 (status={e.status_code})")

        # ---------------------------------------------------------------
        # F. Invalid (non-existent) UUID returns 404
        # ---------------------------------------------------------------
        print("\nF. Invalid UUID returns 404...")
        fake_uuid = UUID("00000000-0000-0000-0000-000000000000")
        try:
            await get_inference_detail(db=db, inference_uuid=fake_uuid, user_id=user_id)
            print("  [FAIL] Expected 404 for non-existent UUID")
            assert False
        except HTTPException as e:
            assert e.status_code == 404
            print(f"  [PASS] Non-existent UUID returns 404")

        # ---------------------------------------------------------------
        # G. Failed/invalid prediction does NOT create a log
        # ---------------------------------------------------------------
        print("\nG. Failed prediction does not create a log...")
        bad_before = await _count_logs(db, user_id, "single")
        bad_payload = PredictionRequest(features={"age": 35})  # missing income, credit_score
        try:
            await predict(DATASET_UUID, MODEL_UUID, user_id, bad_payload, db)
            print("  [FAIL] Should have raised HTTPException")
        except HTTPException as e:
            assert e.status_code == 400
        bad_after = await _count_logs(db, user_id, "single")
        assert bad_after == bad_before, (
            f"A failed prediction should not create a log! before={bad_before}, after={bad_after}"
        )
        print(f"  [PASS] Failed prediction created no log (count unchanged at {bad_after})")

        # ---------------------------------------------------------------
        # H. Empty batch does NOT create a log
        # ---------------------------------------------------------------
        print("\nH. Empty batch does not create a log...")
        empty_before = await _count_logs(db, user_id, "batch")
        try:
            await predict_batch(DATASET_UUID, MODEL_UUID, user_id, BatchPredictionRequest(rows=[]), db)
            print("  [FAIL] Should have raised HTTPException")
        except HTTPException as e:
            assert e.status_code == 400
        empty_after = await _count_logs(db, user_id, "batch")
        assert empty_after == empty_before, (
            f"Empty batch should not create a log! before={empty_before}, after={empty_after}"
        )
        print(f"  [PASS] Empty batch created no log (count unchanged at {empty_after})")

    print("\n" + "=" * 60)
    print("  All M9.4 Tests Passed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_tests())
