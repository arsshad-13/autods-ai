import os
import joblib
import pandas as pd
import numpy as np
import logging
from uuid import UUID
from typing import Any, Dict
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.model_training_service import get_model
from app.schemas.model_inference import (
    PredictionRequest,
    PredictionResponse,
    BatchPredictionRequest,
    BatchPredictionRowResponse,
    BatchPredictionResponse,
)
from app.services import inference_history_service

logger = logging.getLogger(__name__)

def _load_model(model_path: str) -> Any:
    if not model_path or not os.path.exists(model_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model artifact missing on disk."
        )
    try:
        pipeline = joblib.load(model_path)
        return pipeline
    except Exception as e:
        logger.error(f"Failed to load model from {model_path}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load model artifact."
        )

async def predict(
    dataset_uuid: UUID,
    model_uuid: UUID,
    user_id: int,
    request: PredictionRequest,
    db: AsyncSession
) -> PredictionResponse:
    # 1. Fetch and validate model ownership and status
    model = await get_model(dataset_uuid, model_uuid, user_id, db)
    
    if model.status != "COMPLETED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Model training has not completed successfully."
        )
        
    if model.task_type in ["Forecasting", "Time Series"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Time series forecasting is not supported by the predict endpoint."
        )
    
    # 2. Load model
    pipeline = _load_model(model.model_path)
    
    # 3. Validate features
    metadata_info = model.metadata_info or {}
    expected_features = metadata_info.get("feature_columns", [])
    
    if not expected_features:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Model metadata is missing feature columns."
        )
        
    input_features = request.features
    
    # Check for missing required features
    missing_features = [f for f in expected_features if f not in input_features]
    if missing_features:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Missing required features: {missing_features}"
        )
        
    # Construct DataFrame in the exact expected order
    try:
        # Create a single-row DataFrame
        df_input = pd.DataFrame([{f: input_features[f] for f in expected_features}])
        
        # Ensure correct datatypes (force numeric since categorical features were dropped during training)
        df_input = df_input.apply(pd.to_numeric, errors='raise')
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid feature types. Expected numeric values. Error: {str(e)}"
        )
        
    # 4. Predict
    try:
        prediction = pipeline.predict(df_input)[0]
    except Exception as e:
        logger.error(f"Prediction failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Model prediction failed."
        )
        
    # Cast numpy types to python native types for JSON serialization
    if isinstance(prediction, (np.integer, int)):
        prediction_value = int(prediction)
    elif isinstance(prediction, (np.floating, float)):
        prediction_value = float(prediction)
    else:
        prediction_value = prediction
        
    # 5. Extract probabilities if classification
    probabilities = None
    predicted_label = None
    
    if model.task_type == "Classification":
        target_mapping = metadata_info.get("target_label_mapping")
        
        # Determine predicted label
        if target_mapping:
            predicted_label = target_mapping.get(str(prediction_value))
            
        # Get probabilities
        if hasattr(pipeline, "predict_proba"):
            try:
                probas = pipeline.predict_proba(df_input)[0]
                if target_mapping and hasattr(pipeline, "classes_") and len(probas) == len(target_mapping):
                    # We have mapping for all classes
                    classes = pipeline.classes_
                    probabilities = {}
                    for cls_idx, prob in zip(classes, probas):
                        label = target_mapping.get(str(cls_idx), str(cls_idx))
                        probabilities[label] = float(prob)
                elif hasattr(pipeline, "classes_"):
                    # No mapping, just return class indices
                    probabilities = {str(cls_idx): float(prob) for cls_idx, prob in zip(pipeline.classes_, probas)}
            except Exception as e:
                logger.warning(f"Failed to extract probabilities: {e}")
                pass

    response = PredictionResponse(
        dataset_uuid=str(dataset_uuid),
        model_uuid=str(model_uuid),
        model_name=model.name,
        prediction=prediction_value,
        predicted_label=predicted_label,
        probabilities=probabilities,
    )

    # --- Audit logging (non-fatal) ---
    await inference_history_service.log_inference(
        db=db,
        user_id=user_id,
        dataset_id=model.dataset_id,
        model_id=model.id,
        inference_type="single",
        input_data=request.features,
        prediction_data=response.model_dump(),
        row_count=1,
    )

    return response

async def predict_batch(
    dataset_uuid: UUID,
    model_uuid: UUID,
    user_id: int,
    request: BatchPredictionRequest,
    db: AsyncSession
) -> BatchPredictionResponse:
    # 1. Fetch and validate model ownership and status
    model = await get_model(dataset_uuid, model_uuid, user_id, db)
    
    if model.status != "COMPLETED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Model training has not completed successfully."
        )
        
    if model.task_type in ["Forecasting", "Time Series"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Time series forecasting is not supported by the predict endpoint."
        )
        
    if not request.rows:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty rows list provided for batch prediction."
        )
    
    # 2. Load model
    pipeline = _load_model(model.model_path)
    
    # 3. Validate features
    metadata_info = model.metadata_info or {}
    expected_features = metadata_info.get("feature_columns", [])
    
    if not expected_features:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Model metadata is missing feature columns."
        )
        
    # Check for missing required features across all rows
    # We can do this efficiently by looking at the keys of the first row if we assume homogeneous rows,
    # or by converting to a DataFrame and checking columns.
    df_raw = pd.DataFrame(request.rows)
    missing_features = [f for f in expected_features if f not in df_raw.columns]
    
    if missing_features:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Missing required features: {missing_features}"
        )
        
    # Construct DataFrame in the exact expected order
    try:
        df_input = df_raw[expected_features].copy()
        # Ensure correct datatypes
        df_input = df_input.apply(pd.to_numeric, errors='raise')
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid feature types. Expected numeric values. Error: {str(e)}"
        )
        
    # 4. Predict
    try:
        predictions = pipeline.predict(df_input)
    except Exception as e:
        logger.error(f"Batch prediction failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Model batch prediction failed."
        )
        
    # 5. Extract probabilities if classification
    target_mapping = None
    all_probas = None
    
    if model.task_type == "Classification":
        target_mapping = metadata_info.get("target_label_mapping")
        
        if hasattr(pipeline, "predict_proba"):
            try:
                all_probas = pipeline.predict_proba(df_input)
            except Exception as e:
                logger.warning(f"Failed to extract batch probabilities: {e}")
                pass
                
    response_rows = []
    
    for i in range(len(predictions)):
        pred = predictions[i]
        
        # Cast numpy types to python native types for JSON serialization
        if isinstance(pred, (np.integer, int)):
            prediction_value = int(pred)
        elif isinstance(pred, (np.floating, float)):
            prediction_value = float(pred)
        else:
            prediction_value = pred
            
        predicted_label = None
        probabilities = None
        
        if model.task_type == "Classification":
            if target_mapping:
                predicted_label = target_mapping.get(str(prediction_value))
                
            if all_probas is not None:
                row_probas = all_probas[i]
                if target_mapping and hasattr(pipeline, "classes_") and len(row_probas) == len(target_mapping):
                    classes = pipeline.classes_
                    probabilities = {}
                    for cls_idx, prob in zip(classes, row_probas):
                        label = target_mapping.get(str(cls_idx), str(cls_idx))
                        probabilities[label] = float(prob)
                elif hasattr(pipeline, "classes_"):
                    probabilities = {str(cls_idx): float(prob) for cls_idx, prob in zip(pipeline.classes_, row_probas)}
                    
        response_rows.append(BatchPredictionRowResponse(
            row_index=i,
            prediction=prediction_value,
            predicted_label=predicted_label,
            probabilities=probabilities
        ))
        
    batch_response = BatchPredictionResponse(
        dataset_uuid=str(dataset_uuid),
        model_uuid=str(model_uuid),
        model_name=model.name,
        predictions=response_rows,
        total_rows=len(response_rows),
    )

    # --- Audit logging (non-fatal) ---
    await inference_history_service.log_inference(
        db=db,
        user_id=user_id,
        dataset_id=model.dataset_id,
        model_id=model.id,
        inference_type="batch",
        input_data=request.rows,
        prediction_data=batch_response.model_dump(),
        row_count=len(request.rows),
    )

    return batch_response
