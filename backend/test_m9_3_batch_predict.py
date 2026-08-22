import asyncio
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))

from uuid import UUID

from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.dataset import Dataset
from app.models.user import User

from app.services.model_inference_service import predict, predict_batch
from app.schemas.model_inference import PredictionRequest, BatchPredictionRequest
from fastapi import HTTPException

async def run_tests():
    dataset_uuid_str = "25489deb-33b8-4aca-990f-c6b7562d5ae3"
    model_uuid_str = "39a6a38f-2a04-4f07-8e77-a2e68c671110"
    
    async with AsyncSessionLocal() as db:
        # Find dataset owner
        stmt = select(Dataset).where(Dataset.uuid == UUID(dataset_uuid_str))
        result = await db.execute(stmt)
        dataset = result.scalar_one_or_none()
        if not dataset:
            print("Dataset not found in DB!")
            return
            
        user_id = dataset.user_id
        
        # ---------------------------------------------------------
        # I. Existing M9.2 single prediction
        # ---------------------------------------------------------
        payload_single = PredictionRequest(features={
            "age": 35,
            "income": 65000,
            "credit_score": 720
        })
        
        print("I. Testing M9.2 single predict...")
        resp = await predict(UUID(dataset_uuid_str), UUID(model_uuid_str), user_id, payload_single, db)
        print("Single response:", resp)
        assert resp.predicted_label in ["Yes", "No"], "Single predict failed to return proper label"
        
        # ---------------------------------------------------------
        # A. Valid classification batch
        # ---------------------------------------------------------
        print("\nA. Testing valid classification batch...")
        batch_payload = BatchPredictionRequest(rows=[
            {
                "age": 35,
                "income": 65000,
                "credit_score": 720
            },
            {
                "age": 29,
                "income": 41000,
                "credit_score": 600
            },
            {
                "age": 45,
                "income": 85000,
                "credit_score": 760
            }
        ])
        
        resp_batch = await predict_batch(UUID(dataset_uuid_str), UUID(model_uuid_str), user_id, batch_payload, db)
        print("Batch response rows count:", resp_batch.total_rows)
        for p in resp_batch.predictions:
            print(f"Row {p.row_index}: Label={p.predicted_label}, Probabilities={p.probabilities}")
        
        assert resp_batch.total_rows == 3, "Failed to return 3 predictions"
        
        # ---------------------------------------------------------
        # B. Missing feature
        # ---------------------------------------------------------
        print("\nB. Testing missing feature in batch...")
        bad_batch = BatchPredictionRequest(rows=[{"age": 35}])
        try:
            await predict_batch(UUID(dataset_uuid_str), UUID(model_uuid_str), user_id, bad_batch, db)
            print("FAILED: Missing feature did not raise exception")
        except HTTPException as e:
            print("Status:", e.status_code, "Detail:", e.detail)
            assert e.status_code == 400
            
        # ---------------------------------------------------------
        # C. Empty rows
        # ---------------------------------------------------------
        print("\nC. Testing empty rows in batch...")
        empty_batch = BatchPredictionRequest(rows=[])
        try:
            await predict_batch(UUID(dataset_uuid_str), UUID(model_uuid_str), user_id, empty_batch, db)
            print("FAILED: Empty batch did not raise exception")
        except HTTPException as e:
            print("Status:", e.status_code, "Detail:", e.detail)
            assert e.status_code == 400
            
        # ---------------------------------------------------------
        # D. Invalid dataset UUID
        # ---------------------------------------------------------
        print("\nD. Testing invalid dataset UUID...")
        try:
            await predict_batch(UUID("00000000-0000-0000-0000-000000000000"), UUID(model_uuid_str), user_id, batch_payload, db)
            print("FAILED: Invalid dataset UUID did not raise exception")
        except HTTPException as e:
            print("Status:", e.status_code, "Detail:", e.detail)
            assert e.status_code == 404
            
        # ---------------------------------------------------------
        # E. Invalid model UUID
        # ---------------------------------------------------------
        print("\nE. Testing invalid model UUID...")
        try:
            await predict_batch(UUID(dataset_uuid_str), UUID("00000000-0000-0000-0000-000000000000"), user_id, batch_payload, db)
            print("FAILED: Invalid model UUID did not raise exception")
        except HTTPException as e:
            print("Status:", e.status_code, "Detail:", e.detail)
            assert e.status_code == 404

        # ---------------------------------------------------------
        # F. Unauthorized/foreign dataset/model
        # ---------------------------------------------------------
        print("\nF. Testing unauthorized user...")
        try:
            # use a non-existent user id or random user id to simulate unauthorized access
            await predict_batch(UUID(dataset_uuid_str), UUID(model_uuid_str), 99999, batch_payload, db)
            print("FAILED: Unauthorized user did not raise exception")
        except HTTPException as e:
            print("Status:", e.status_code, "Detail:", e.detail)
            assert e.status_code in [403, 404]
            
        print("\nAll Batch Inference Tests Passed!")

if __name__ == "__main__":
    asyncio.run(run_tests())
