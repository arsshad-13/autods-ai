import asyncio
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))

from uuid import UUID

from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.dataset import Dataset
from app.models.user import User
from app.core.security import create_access_token
from datetime import timedelta

from app.services.model_inference_service import predict
from app.schemas.model_inference import PredictionRequest
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
        
        # Positive case
        payload = PredictionRequest(features={
            "age": 35,
            "income": 65000,
            "credit_score": 720
        })
        
        print("Testing positive case...")
        resp = await predict(UUID(dataset_uuid_str), UUID(model_uuid_str), user_id, payload, db)
        print("Response:", resp)
        
        # Negative cases
        print("\nTesting missing feature...")
        bad_payload = PredictionRequest(features={"age": 35})
        try:
            await predict(UUID(dataset_uuid_str), UUID(model_uuid_str), user_id, bad_payload, db)
        except HTTPException as e:
            print("Status:", e.status_code, "Detail:", e.detail)
        
        print("\nTesting invalid dataset...")
        try:
            await predict(UUID("00000000-0000-0000-0000-000000000000"), UUID(model_uuid_str), user_id, payload, db)
        except HTTPException as e:
            print("Status:", e.status_code, "Detail:", e.detail)

    
if __name__ == "__main__":
    asyncio.run(run_tests())

