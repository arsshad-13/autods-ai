"""
model_training_service.py
=========================
Handles all model training logic for AutoDS AI.

Training lifecycle:
  POST /models/train
    └── train_models()         — validate, clear old records, create PENDING placeholders
    └── [endpoint enqueues]    — run_model_training() as FastAPI async BackgroundTask

  BackgroundTask (Uvicorn event loop)
    └── run_model_training()   — async entry point; awaits _execute_training_pipeline()
    └── _execute_training_pipeline() — async orchestrator with its own DB session

  GET /models/status
    └── get_training_status()  — aggregate status across all records for a dataset

Step 2 changes (leakage-free pipeline):
  - StandardScaler and SimpleImputer now live inside sklearn Pipelines fitted ONLY on X_train.
  - Time Series (task_type "Forecasting" or "Time Series"):
      * Datetime column detected and validated.
      * Dataset sorted chronologically before any feature engineering.
      * Lag features: lag_1, lag_7, lag_14 generated from target history.
      * Rolling features: rolling_mean_7, rolling_std_7 using shift(1) to avoid leakage.
      * Chronological 80/20 train/test split (no shuffle).
      * Datetime column dropped from X before fitting (kept in metadata).
      * MAPE added to regression metrics.
  - All model artifacts are persisted as complete fitted Pipelines (not bare estimators).
  - metadata_info stores task_type, target, datetime_col, feature_columns, lag/rolling
    feature names, and split information.
"""

import asyncio
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

import joblib
import numpy as np
import pandas as pd
from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    r2_score,
    recall_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor

from app.config import get_settings
from app.models.dataset_preprocessing import DatasetPreprocessing
from app.models.dataset_profile import DatasetProfile
from app.models.trained_model import TrainedModel
from app.schemas.trained_model import ModelTrainingStatusResponse, TrainedModelResponse
from app.services.dataset_service import get_dataset

logger = logging.getLogger(__name__)
settings = get_settings()


# ---------------------------------------------------------------------------
# Internal helpers — utilities
# ---------------------------------------------------------------------------

def _get_models_dir() -> Path:
    """Return (and create) the directory where trained .joblib files are stored."""
    models_dir = Path(settings.UPLOAD_DIR) / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    return models_dir


def _get_candidate_names(task_type: str) -> List[str]:
    """Return the ordered list of algorithm names for a given task type."""
    if task_type == "Classification":
        return ["Logistic Regression", "Random Forest", "Decision Tree"]
    elif task_type in ["Time Series", "Forecasting"]:
        return ["Random Forest Regressor", "Decision Tree Regressor"]
    else:  # Regression
        return ["Linear Regression", "Random Forest Regressor", "Decision Tree Regressor"]


def _mark_all_failed(records: List[TrainedModel], message: str) -> None:
    """Utility: mark every record in the list as FAILED with a user-safe message."""
    for r in records:
        r.status = "FAILED"
        r.error_message = message


# ---------------------------------------------------------------------------
# Internal helpers — time series feature engineering
# ---------------------------------------------------------------------------

def _detect_datetime_column(df: pd.DataFrame) -> Optional[str]:
    """
    Identify the most suitable datetime column in the dataframe.

    Detection strategy (in order of priority):
      1. Columns already parsed as datetime64 by pandas.
      2. Object/string columns whose name contains date/time/timestamp keywords
         AND where >50% of values parse successfully as dates.

    Returns the column name or None if no datetime column is found.
    """
    # Priority 1: Already datetime dtype
    dt_cols = [c for c in df.columns if pd.api.types.is_datetime64_any_dtype(df[c])]
    if dt_cols:
        return dt_cols[0]

    # Priority 2: String column with date-like name and parseable content
    date_keywords = ["date", "time", "timestamp", "_at", "created", "updated", "period"]
    for col in df.columns:
        col_lower = col.lower()
        if any(k in col_lower for k in date_keywords):
            try:
                parsed = pd.to_datetime(df[col], errors="coerce")
                if parsed.notna().sum() > 0.5 * len(df):
                    return col
            except Exception:
                continue

    # Priority 3: Try every object column for date parseability (last resort)
    for col in df.columns:
        if df[col].dtype == object:
            try:
                parsed = pd.to_datetime(df[col], errors="coerce")
                if parsed.notna().mean() > 0.8:
                    return col
            except Exception:
                continue

    return None


def _validate_time_series_requirements(
    df: pd.DataFrame,
    datetime_col: str,
    target_col: str,
    dataset_uuid: str,
) -> None:
    """
    Validate that the dataframe meets the minimum requirements for time-series training.

    Raises ValueError with a descriptive message if any requirement is not satisfied.
    """
    MIN_ROWS = 30  # Need enough rows for lag_14 + rolling_7 + meaningful train/test

    if len(df) < MIN_ROWS:
        raise ValueError(
            f"Time series dataset too small ({len(df)} rows). "
            f"Minimum {MIN_ROWS} rows required for lag/rolling feature generation."
        )

    if target_col not in df.columns:
        raise ValueError(f"Target column '{target_col}' not found in dataset.")

    target_series = pd.to_numeric(df[target_col], errors="coerce")
    if target_series.isna().all():
        raise ValueError(
            f"Target column '{target_col}' contains no valid numeric values. "
            "Time series forecasting requires a numeric target."
        )

    if datetime_col not in df.columns:
        raise ValueError(
            f"Datetime column '{datetime_col}' not found in dataset after preprocessing."
        )

    dt_parsed = pd.to_datetime(df[datetime_col], errors="coerce")
    valid_dt_count = dt_parsed.notna().sum()
    if valid_dt_count < MIN_ROWS * 0.8:
        raise ValueError(
            f"Datetime column '{datetime_col}' has too many unparseable values "
            f"({valid_dt_count} valid out of {len(df)} rows)."
        )

    logger.info(
        "Time series validation passed for dataset %s: %d rows, datetime='%s', target='%s'.",
        dataset_uuid, len(df), datetime_col, target_col,
    )


def _create_lag_features(
    df: pd.DataFrame,
    target_col: str,
    lags: List[int],
) -> Tuple[pd.DataFrame, List[str]]:
    """
    Create lag features for the target column using only historical values.

    Lag features use pandas .shift(n) which shifts target values forward by n positions,
    ensuring that row i's lag_n value is the target from row (i-n) — purely historical.

    Parameters
    ----------
    df : DataFrame sorted chronologically.
    target_col : Name of the target column.
    lags : List of lag periods (e.g. [1, 7, 14]).

    Returns
    -------
    df : DataFrame with new lag columns appended.
    lag_feature_names : Names of the generated lag columns.
    """
    lag_feature_names: List[str] = []
    for lag in lags:
        col_name = f"{target_col}_lag_{lag}"
        df[col_name] = df[target_col].shift(lag)
        lag_feature_names.append(col_name)
        logger.debug("Created lag feature '%s'.", col_name)
    return df, lag_feature_names


def _create_rolling_features(
    df: pd.DataFrame,
    target_col: str,
    windows: List[int],
) -> Tuple[pd.DataFrame, List[str]]:
    """
    Create rolling-window statistics for the target column using ONLY historical observations.

    LEAKAGE PREVENTION:
    The target series is shifted by 1 before computing the rolling window.
    This ensures that for row i, the rolling statistic uses values from
    rows [i-window, i-1], and never includes the current observation (row i).

    Parameters
    ----------
    df : DataFrame sorted chronologically.
    target_col : Name of the target column.
    windows : List of window sizes (e.g. [7]).

    Returns
    -------
    df : DataFrame with new rolling columns appended.
    rolling_feature_names : Names of the generated rolling columns.
    """
    rolling_feature_names: List[str] = []
    shifted = df[target_col].shift(1)  # shift once; all windows use this shifted series
    for window in windows:
        mean_col = f"{target_col}_rolling_mean_{window}"
        std_col = f"{target_col}_rolling_std_{window}"
        df[mean_col] = shifted.rolling(window=window, min_periods=1).mean()
        df[std_col] = shifted.rolling(window=window, min_periods=1).std()
        rolling_feature_names.extend([mean_col, std_col])
        logger.debug("Created rolling features '%s' and '%s'.", mean_col, std_col)
    return df, rolling_feature_names


def _prepare_time_series_features(
    df: pd.DataFrame,
    datetime_col: str,
    target_col: str,
    dataset_uuid: str,
) -> Tuple[pd.DataFrame, List[str], List[str]]:
    """
    Orchestrate all time-series feature engineering.

    Steps:
      1. Sort chronologically by datetime column.
      2. Convert target to numeric; drop rows with NaN target.
      3. Generate lag features (1, 7, 14).
      4. Generate rolling features (window=7: mean and std).
      5. Log a warning for leading NaN rows from lagging.

    The original datetime column is retained in the returned df for reference
    but will be excluded from X before model fitting.

    Returns
    -------
    df : Enriched, chronologically sorted DataFrame.
    lag_feature_names : List of lag column names.
    rolling_feature_names : List of rolling column names.
    """
    # Step 1: Sort chronologically
    df[datetime_col] = pd.to_datetime(df[datetime_col], errors="coerce")
    df = df.sort_values(by=datetime_col).reset_index(drop=True)
    logger.info(
        "Dataset %s sorted chronologically by '%s'. Date range: %s → %s.",
        dataset_uuid,
        datetime_col,
        df[datetime_col].iloc[0],
        df[datetime_col].iloc[-1],
    )

    # Step 2: Ensure numeric target; drop rows where target is NaN
    df[target_col] = pd.to_numeric(df[target_col], errors="coerce")
    rows_before = len(df)
    df = df.dropna(subset=[target_col]).reset_index(drop=True)
    dropped = rows_before - len(df)
    if dropped > 0:
        logger.warning(
            "Dataset %s: dropped %d rows with NaN target '%s'.", dataset_uuid, dropped, target_col
        )

    # Step 3: Lag features
    df, lag_feature_names = _create_lag_features(df, target_col, lags=[1, 7, 14])

    # Step 4: Rolling features
    df, rolling_feature_names = _create_rolling_features(df, target_col, windows=[7])

    # Step 5: Log NaN situation — leading rows will have NaN lags; Pipeline's SimpleImputer handles these
    nan_rows = df[lag_feature_names + rolling_feature_names].isna().any(axis=1).sum()
    logger.info(
        "Dataset %s: %d rows have NaN lag/rolling values (insufficient history). "
        "These will be handled by the training Pipeline's SimpleImputer.",
        dataset_uuid,
        nan_rows,
    )

    return df, lag_feature_names, rolling_feature_names


def _chronological_split(
    X: pd.DataFrame,
    y: pd.Series,
    test_size: float = 0.2,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    """
    Perform a chronological (time-ordered) train/test split.

    The dataset MUST already be sorted by datetime before calling this function.
    No shuffling is performed. The last `test_size` fraction of rows become the test set.

    This is compatible with sklearn's TimeSeriesSplit for future Optuna integration.

    Parameters
    ----------
    X : Feature DataFrame (sorted chronologically).
    y : Target Series (aligned with X).
    test_size : Fraction of data to reserve for testing (default 0.2 → last 20%).

    Returns
    -------
    X_train, X_test, y_train, y_test
    """
    n = len(X)
    split_idx = int(n * (1 - test_size))
    X_train = X.iloc[:split_idx]
    X_test = X.iloc[split_idx:]
    y_train = y.iloc[:split_idx]
    y_test = y.iloc[split_idx:]
    logger.info(
        "Chronological split: %d train rows (%.0f%%), %d test rows (%.0f%%).",
        len(X_train), (1 - test_size) * 100,
        len(X_test), test_size * 100,
    )
    return X_train, X_test, y_train, y_test


def _build_model_pipeline(estimator: Any, task_type: str) -> Pipeline:
    """
    Wrap an sklearn estimator in a leakage-free Pipeline.

    Pipeline steps:
      1. SimpleImputer (median strategy) — handles NaN values from lag/rolling features
         and any residual missingness. Fitted ONLY on training data.
      2. StandardScaler — standardizes features. Fitted ONLY on training data.
         (For tree-based models, scaling has no effect but is kept for consistency.)
      3. estimator — the actual ML model.

    CRITICAL: pipeline.fit() is called ONLY on X_train, y_train.
    pipeline.predict() is called on X_test without refitting.

    Parameters
    ----------
    estimator : An unfitted sklearn estimator instance.
    task_type : Task type string (used for logging only).

    Returns
    -------
    pipeline : Unfitted sklearn Pipeline ready for .fit(X_train, y_train).
    """
    pipeline = Pipeline(steps=[
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
        ("model", estimator),
    ])
    logger.debug(
        "Built Pipeline for task '%s': SimpleImputer(median) → StandardScaler → %s.",
        task_type,
        type(estimator).__name__,
    )
    return pipeline


def _calculate_metrics(
    task_type: str,
    y_test: pd.Series,
    preds: np.ndarray,
) -> Dict[str, float]:
    """
    Calculate evaluation metrics appropriate for the given task type.

    Classification : Accuracy, Precision, Recall, F1 Score
    Regression     : MAE, RMSE, R²
    Time Series    : MAE, RMSE, R², MAPE
      MAPE is computed only on observations where y_test != 0 to avoid division by zero.

    Parameters
    ----------
    task_type : "Classification", "Regression", "Forecasting", or "Time Series".
    y_test : True target values.
    preds : Model predictions.

    Returns
    -------
    metrics : Dictionary of metric name → float value.
    """
    if task_type == "Classification":
        return {
            "Accuracy": float(accuracy_score(y_test, preds)),
            "Precision": float(
                precision_score(y_test, preds, average="weighted", zero_division=0)
            ),
            "Recall": float(
                recall_score(y_test, preds, average="weighted", zero_division=0)
            ),
            "F1 Score": float(
                f1_score(y_test, preds, average="weighted", zero_division=0)
            ),
        }

    # Shared regression/time-series metrics
    mae = float(mean_absolute_error(y_test, preds))
    rmse = float(np.sqrt(mean_squared_error(y_test, preds)))
    r2 = float(r2_score(y_test, preds))
    metrics: Dict[str, float] = {"MAE": mae, "RMSE": rmse, "R2": r2}

    # MAPE — only for time-series tasks; guard against zero targets
    if task_type in ["Forecasting", "Time Series"]:
        y_arr = np.array(y_test, dtype=float)
        p_arr = np.array(preds, dtype=float)
        nonzero_mask = y_arr != 0
        if nonzero_mask.sum() > 0:
            mape = float(
                np.mean(np.abs((y_arr[nonzero_mask] - p_arr[nonzero_mask]) / y_arr[nonzero_mask]))
                * 100.0
            )
        else:
            # All target values are zero — MAPE is undefined
            logger.warning("MAPE undefined: all y_test values are zero. Storing NaN.")
            mape = float("nan")
        metrics["MAPE"] = mape

    return metrics


# ---------------------------------------------------------------------------
# READ endpoints — unchanged
# ---------------------------------------------------------------------------

async def get_trained_models(
    dataset_uuid: UUID,
    user_id: int,
    db: AsyncSession,
) -> List[TrainedModel]:
    """Return all TrainedModel records for a dataset, newest first."""
    dataset = await get_dataset(dataset_uuid, user_id, db)
    stmt = (
        select(TrainedModel)
        .where(TrainedModel.dataset_id == dataset.id)
        .order_by(TrainedModel.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_best_model(
    dataset_uuid: UUID,
    user_id: int,
    db: AsyncSession,
) -> TrainedModel | None:
    """Return the model flagged as best for the dataset, or None."""
    dataset = await get_dataset(dataset_uuid, user_id, db)
    stmt = (
        select(TrainedModel)
        .where(
            TrainedModel.dataset_id == dataset.id,
            TrainedModel.is_best == True,  # noqa: E712
        )
        .order_by(TrainedModel.created_at.desc())
    )
    result = await db.execute(stmt)
    return result.scalars().first()


async def get_model(
    dataset_uuid: UUID,
    model_uuid: UUID,
    user_id: int,
    db: AsyncSession,
) -> TrainedModel:
    """Return a specific trained model by UUID, or raise 404."""
    dataset = await get_dataset(dataset_uuid, user_id, db)
    stmt = select(TrainedModel).where(
        TrainedModel.dataset_id == dataset.id,
        TrainedModel.uuid == model_uuid,
    )
    result = await db.execute(stmt)
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    return model


# ---------------------------------------------------------------------------
# Training status endpoint
# ---------------------------------------------------------------------------

async def get_training_status(
    dataset_uuid: UUID,
    user_id: int,
    db: AsyncSession,
) -> ModelTrainingStatusResponse:
    """
    Compute the aggregate training status for the dataset's current training run.
    Called by GET /{dataset_uuid}/models/status for frontend polling.
    """
    dataset = await get_dataset(dataset_uuid, user_id, db)

    stmt = (
        select(TrainedModel)
        .where(TrainedModel.dataset_id == dataset.id)
        .order_by(TrainedModel.created_at.desc())
    )
    result = await db.execute(stmt)
    models = list(result.scalars().all())

    if not models:
        return ModelTrainingStatusResponse(
            message="No training jobs found. Start training first.",
            status="NOT_STARTED",
            dataset_uuid=str(dataset_uuid),
            trained_models=[],
        )

    statuses = {m.status for m in models}
    error_message: str | None = None

    if "RUNNING" in statuses or "PENDING" in statuses:
        agg_status = "RUNNING"
        message = "Model training is in progress."
    elif all(m.status == "COMPLETED" for m in models):
        agg_status = "COMPLETED"
        message = "Model training completed successfully."
    elif "FAILED" in statuses:
        agg_status = "FAILED"
        failed_errors = [
            m.error_message for m in models if m.status == "FAILED" and m.error_message
        ]
        error_message = failed_errors[0] if failed_errors else "Model training failed."
        message = error_message
    else:
        # Defensive fallback — should not occur in normal operation
        agg_status = "RUNNING"
        message = "Model training is in progress."

    return ModelTrainingStatusResponse(
        message=message,
        status=agg_status,
        dataset_uuid=str(dataset_uuid),
        trained_models=[TrainedModelResponse.model_validate(m) for m in models],
        error_message=error_message,
    )


# ---------------------------------------------------------------------------
# train_models — validate, clear, create PENDING placeholders
# ---------------------------------------------------------------------------

async def train_models(
    dataset_uuid: UUID,
    user_id: int,
    db: AsyncSession,
) -> Tuple[List[TrainedModel], Dict[str, Any]]:
    """
    Validates the dataset state, prevents duplicate training, clears any previous
    TrainedModel records for this dataset, creates PENDING placeholder records for
    each candidate algorithm, and returns the placeholder list plus all parameters
    the background task needs.

    The caller (the API endpoint) is responsible for enqueuing run_model_training()
    as a FastAPI BackgroundTask after this function returns.

    Returns
    -------
    placeholder_records : List[TrainedModel]
        Freshly committed PENDING records, one per candidate model.
    bg_params : Dict[str, Any]
        Keyword arguments to pass directly to run_model_training().
    """

    # 1. Verify ownership and existence
    dataset = await get_dataset(dataset_uuid, user_id, db)

    # 2. Verify profile completeness
    profile_stmt = select(DatasetProfile).where(DatasetProfile.dataset_id == dataset.id)
    profile_res = await db.execute(profile_stmt)
    profile = profile_res.scalar_one_or_none()

    if not profile or not profile.recommended_task:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dataset profile not found or incomplete. Please profile the dataset first.",
        )

    task_type: str = profile.recommended_task
    target_column: str | None = profile.recommended_target

    if not target_column:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Target column not identified in dataset profile.",
        )

    # 3. Extract datetime column from profile for time series tasks
    datetime_column: Optional[str] = None
    if task_type in ["Forecasting", "Time Series"]:
        dt_cols = profile.profile_data.get("general", {}).get("column_types", {}).get("datetime", [])
        if dt_cols:
            datetime_column = dt_cols[0]
        logger.info(
            "Time series task for dataset %s — datetime column from profile: '%s'.",
            dataset_uuid, datetime_column,
        )

    # 4. Verify preprocessing is completed
    prep_stmt = select(DatasetPreprocessing).where(DatasetPreprocessing.dataset_id == dataset.id)
    prep_res = await db.execute(prep_stmt)
    preprocessing = prep_res.scalar_one_or_none()

    if not preprocessing or preprocessing.status != "COMPLETED" or not preprocessing.clean_dataset_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Preprocessing is required before model training. "
                "Please complete the preprocessing step first."
            ),
        )

    clean_path = Path(preprocessing.clean_dataset_path)
    if not clean_path.exists():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Cleaned dataset file not found on disk. Please re-run preprocessing.",
        )

    # 5. Prevent duplicate concurrent training
    running_stmt = select(TrainedModel).where(
        TrainedModel.dataset_id == dataset.id,
        TrainedModel.status.in_(["PENDING", "RUNNING"]),
    )
    running_res = await db.execute(running_stmt)
    if running_res.scalars().first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Model training is already in progress for this dataset. "
                "Please wait for the current run to complete."
            ),
        )

    # 6. Clear previous training records for this dataset
    #    (old .joblib files are intentionally NOT deleted at this step)
    await db.execute(delete(TrainedModel).where(TrainedModel.dataset_id == dataset.id))
    await db.commit()
    logger.info("Cleared previous TrainedModel records for dataset %s.", dataset_uuid)

    # 7. Create one PENDING placeholder record per candidate algorithm
    candidate_names = _get_candidate_names(task_type)
    placeholder_records: List[TrainedModel] = []

    for name in candidate_names:
        record = TrainedModel(
            dataset_id=dataset.id,
            name=f"{name} (Auto)",
            algorithm=name,
            task_type=task_type,
            target_column=target_column,
            status="PENDING",
            is_best=False,
        )
        db.add(record)
        placeholder_records.append(record)

    await db.commit()
    for r in placeholder_records:
        await db.refresh(r)

    logger.info(
        "Created %d PENDING placeholder(s) for dataset %s — task=%s, target=%s, algorithms=%s",
        len(placeholder_records),
        dataset_uuid,
        task_type,
        target_column,
        candidate_names,
    )

    # 8. Build the parameter dict for the background task
    bg_params: Dict[str, Any] = {
        "dataset_id": dataset.id,
        "dataset_uuid": str(dataset.uuid),
        "task_type": task_type,
        "target_column": target_column,
        "datetime_column": datetime_column,
        "clean_path": str(clean_path),
        "placeholder_ids": [r.id for r in placeholder_records],
    }

    return placeholder_records, bg_params


# ---------------------------------------------------------------------------
# run_model_training — async background task (runs on Uvicorn's event loop)
# ---------------------------------------------------------------------------

async def run_model_training(
    dataset_id: int,
    dataset_uuid: str,
    task_type: str,
    target_column: str,
    clean_path: str,
    placeholder_ids: List[int],
    datetime_column: Optional[str] = None,
) -> None:
    """
    Async background training entry point.

    FastAPI BackgroundTasks accepts async functions and schedules them directly
    on Uvicorn's running event loop — the same loop on which the SQLAlchemy
    AsyncEngine (asyncpg) connection pool was initialised.  Running on the
    same loop is the critical requirement; asyncpg Futures/connections must
    never be used from a different loop.

    Previously this was a sync wrapper that created a new event loop via
    asyncio.new_event_loop() / loop.run_until_complete().  That pattern is
    incompatible with asyncpg's connection pool because the pool is bound to
    the loop that existed when create_async_engine() was called (Uvicorn's
    loop), causing the "Future attached to a different loop" RuntimeError.

    The fix: simply await _execute_training_pipeline() directly so the call
    runs on the existing Uvicorn event loop.  No second loop is ever created.
    """
    await _execute_training_pipeline(
        dataset_id=dataset_id,
        dataset_uuid=dataset_uuid,
        task_type=task_type,
        target_column=target_column,
        clean_path=clean_path,
        placeholder_ids=placeholder_ids,
        datetime_column=datetime_column,
    )



# ---------------------------------------------------------------------------
# _execute_training_pipeline — async orchestrator (private)
# ---------------------------------------------------------------------------

async def _execute_training_pipeline(
    dataset_id: int,
    dataset_uuid: str,
    task_type: str,
    target_column: str,
    clean_path: str,
    placeholder_ids: List[int],
    datetime_column: Optional[str] = None,
) -> None:
    """
    Internal async training orchestrator.

    Awaited directly by run_model_training() on Uvicorn's event loop.
    Opens its own database session via AsyncSessionLocal — never reuses the
    request-scoped session from the endpoint.

    For Time Series / Forecasting tasks:
      1. Detect datetime column (from profile hint or auto-detection).
      2. Validate requirements.
      3. Sort chronologically.
      4. Generate lag (1, 7, 14) and rolling (mean_7, std_7) features.
      5. Chronological 80/20 split (no shuffle).
      6. Wrap each estimator in a leakage-free Pipeline.
      7. Fit Pipeline ONLY on X_train.
      8. Calculate MAE, RMSE, R², MAPE.

    For Classification / Regression:
      1. Standard random 80/20 split.
      2. Wrap each estimator in a leakage-free Pipeline.
      3. Fit Pipeline ONLY on X_train.
      4. Calculate task-appropriate metrics.

    All model artifacts are persisted as complete fitted Pipelines.
    """

    # Deferred import to avoid circular dependency at module load time
    from app.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:

        # --- Fetch placeholder records ---
        stmt = select(TrainedModel).where(TrainedModel.id.in_(placeholder_ids))
        result = await db.execute(stmt)
        records = list(result.scalars().all())

        if not records:
            logger.error(
                "Background training aborted: placeholder records not found for dataset %s "
                "(expected ids=%s).",
                dataset_uuid,
                placeholder_ids,
            )
            return

        # Stable lookup by algorithm name — independent of DB query row order
        records_by_algo: Dict[str, TrainedModel] = {r.algorithm: r for r in records}

        # --- Mark all records RUNNING ---
        for r in records:
            r.status = "RUNNING"
        try:
            await db.commit()
        except Exception:
            logger.exception(
                "Failed to mark records RUNNING for dataset %s. Training aborted.", dataset_uuid
            )
            return

        logger.info(
            "Background training RUNNING for dataset %s (task=%s, target=%s).",
            dataset_uuid,
            task_type,
            target_column,
        )

        # ----------------------------------------------------------------
        # Load cleaned dataset
        # ----------------------------------------------------------------
        try:
            p = Path(clean_path)
            df = pd.read_csv(p) if p.suffix == ".csv" else pd.read_excel(p)
        except Exception as e:
            logger.exception("Failed to load cleaned dataset for dataset %s.", dataset_uuid)
            _mark_all_failed(records, f"Failed to load dataset: {str(e)[:200]}")
            await db.commit()
            return

        # ----------------------------------------------------------------
        # Branch: Time Series / Forecasting
        # ----------------------------------------------------------------
        if task_type in ["Forecasting", "Time Series"]:

            # --- Step 1: Identify datetime column ---
            dt_col = datetime_column  # hint from profile, may be None
            if dt_col is None or dt_col not in df.columns:
                dt_col = _detect_datetime_column(df)

            if dt_col is None:
                msg = (
                    "No datetime column found in dataset. "
                    "Time series training requires exactly one datetime column. "
                    "Ensure the dataset has a date/timestamp column."
                )
                logger.error("Dataset %s: %s", dataset_uuid, msg)
                _mark_all_failed(records, msg)
                await db.commit()
                return

            logger.info("Dataset %s: using datetime column '%s'.", dataset_uuid, dt_col)

            # --- Step 2: Validate requirements ---
            try:
                _validate_time_series_requirements(df, dt_col, target_column, dataset_uuid)
            except ValueError as e:
                logger.error("Dataset %s time series validation failed: %s", dataset_uuid, e)
                _mark_all_failed(records, str(e))
                await db.commit()
                return

            # --- Step 3–4: Sort + generate lag and rolling features ---
            try:
                df, lag_feature_names, rolling_feature_names = _prepare_time_series_features(
                    df, dt_col, target_column, dataset_uuid
                )
            except Exception as e:
                logger.exception("Feature preparation failed for dataset %s.", dataset_uuid)
                _mark_all_failed(records, f"Feature preparation failed: {str(e)[:200]}")
                await db.commit()
                return

            # --- Step 5: Build X and y (exclude datetime from features) ---
            try:
                y = df[target_column].copy()

                # X: all columns except target and datetime
                # Datetime column must NOT be a model feature (non-numeric, used only for ordering)
                cols_to_exclude = [target_column, dt_col]
                X = df.drop(columns=[c for c in cols_to_exclude if c in df.columns])

                # Drop any remaining non-numeric columns (e.g. other string columns)
                X_numeric = X.select_dtypes(include=[np.number])
                if len(X_numeric.columns) < len(X.columns):
                    dropped_cols = set(X.columns) - set(X_numeric.columns)
                    logger.warning(
                        "Dataset %s: dropping non-numeric feature columns: %s",
                        dataset_uuid,
                        dropped_cols,
                    )
                X = X_numeric
                feature_cols = list(X.columns)

                if X.empty:
                    raise ValueError("No usable numeric features found after column filtering.")

            except Exception as e:
                logger.exception("Feature preparation failed for dataset %s.", dataset_uuid)
                _mark_all_failed(records, f"Feature preparation failed: {str(e)[:200]}")
                await db.commit()
                return

            # --- Step 6: Chronological split ---
            try:
                X_train, X_test, y_train, y_test = _chronological_split(X, y, test_size=0.2)
                split_meta: Dict[str, Any] = {
                    "chronological_split": True,
                    "split_index": len(X_train),
                    "train_rows": len(X_train),
                    "test_rows": len(X_test),
                }
            except Exception as e:
                logger.exception("Train/test split failed for dataset %s.", dataset_uuid)
                _mark_all_failed(records, f"Train/test split failed: {str(e)[:200]}")
                await db.commit()
                return

            # --- Build candidate estimators for Time Series ---
            candidates: Dict[str, Any] = {
                "Random Forest Regressor": RandomForestRegressor(n_estimators=100, random_state=42),
                "Decision Tree Regressor": DecisionTreeRegressor(random_state=42),
            }

        # ----------------------------------------------------------------
        # Branch: Classification
        # ----------------------------------------------------------------
        elif task_type == "Classification":

            try:
                df = df.dropna(subset=[target_column])
                if len(df) < 20:
                    raise ValueError(
                        f"Dataset too small after cleaning ({len(df)} rows). Minimum is 20."
                    )

                y = df[target_column]
                if y.dtype == object or str(y.dtype) == "category":
                    y = y.astype("category").cat.codes

                X = df.drop(columns=[target_column])
                X_numeric = X.select_dtypes(include=[np.number])
                if len(X_numeric.columns) < len(X.columns):
                    dropped_cols = set(X.columns) - set(X_numeric.columns)
                    logger.warning(
                        "Dataset %s: dropping non-numeric feature columns: %s",
                        dataset_uuid,
                        dropped_cols,
                    )
                X = X_numeric
                feature_cols = list(X.columns)

                if X.empty:
                    raise ValueError("No usable numeric features found after column filtering.")

            except Exception as e:
                logger.exception("Feature preparation failed for dataset %s.", dataset_uuid)
                _mark_all_failed(records, f"Feature preparation failed: {str(e)[:200]}")
                await db.commit()
                return

            try:
                X_train, X_test, y_train, y_test = train_test_split(
                    X, y, test_size=0.2, random_state=42
                )
                split_meta = {"random_state": 42}
                dt_col = None
                lag_feature_names = []
                rolling_feature_names = []
            except Exception as e:
                logger.exception("Train/test split failed for dataset %s.", dataset_uuid)
                _mark_all_failed(records, f"Train/test split failed: {str(e)[:200]}")
                await db.commit()
                return

            candidates = {
                "Logistic Regression": LogisticRegression(max_iter=1000, random_state=42),
                "Random Forest": RandomForestClassifier(n_estimators=100, random_state=42),
                "Decision Tree": DecisionTreeClassifier(random_state=42),
            }

        # ----------------------------------------------------------------
        # Branch: Regression
        # ----------------------------------------------------------------
        else:

            try:
                df = df.dropna(subset=[target_column])
                if len(df) < 20:
                    raise ValueError(
                        f"Dataset too small after cleaning ({len(df)} rows). Minimum is 20."
                    )

                y = pd.to_numeric(df[target_column], errors="coerce")
                valid_mask = y.notna()
                df = df.loc[valid_mask]
                y = y.loc[valid_mask]

                X = df.drop(columns=[target_column])
                X_numeric = X.select_dtypes(include=[np.number])
                if len(X_numeric.columns) < len(X.columns):
                    dropped_cols = set(X.columns) - set(X_numeric.columns)
                    logger.warning(
                        "Dataset %s: dropping non-numeric feature columns: %s",
                        dataset_uuid,
                        dropped_cols,
                    )
                X = X_numeric
                feature_cols = list(X.columns)

                if X.empty:
                    raise ValueError("No usable numeric features found after column filtering.")

            except Exception as e:
                logger.exception("Feature preparation failed for dataset %s.", dataset_uuid)
                _mark_all_failed(records, f"Feature preparation failed: {str(e)[:200]}")
                await db.commit()
                return

            try:
                X_train, X_test, y_train, y_test = train_test_split(
                    X, y, test_size=0.2, random_state=42
                )
                split_meta = {"random_state": 42}
                dt_col = None
                lag_feature_names = []
                rolling_feature_names = []
            except Exception as e:
                logger.exception("Train/test split failed for dataset %s.", dataset_uuid)
                _mark_all_failed(records, f"Train/test split failed: {str(e)[:200]}")
                await db.commit()
                return

            candidates = {
                "Linear Regression": LinearRegression(),
                "Random Forest Regressor": RandomForestRegressor(n_estimators=100, random_state=42),
                "Decision Tree Regressor": DecisionTreeRegressor(random_state=42),
            }

        # Common train/test row counts for metadata
        train_rows = len(X_train)
        test_rows = len(X_test)
        models_dir = _get_models_dir()

        # ----------------------------------------------------------------
        # Train each candidate individually — per-model error isolation
        # ----------------------------------------------------------------
        for name, estimator in candidates.items():
            rec = records_by_algo.get(name)
            if rec is None:
                logger.warning(
                    "No placeholder record for algorithm '%s' in dataset %s — skipping.",
                    name,
                    dataset_uuid,
                )
                continue

            try:
                start_t = time.time()

                # Wrap estimator in leakage-free Pipeline
                pipeline = _build_model_pipeline(estimator, task_type)

                # Fit ONLY on training data — this is where imputer and scaler learn statistics
                pipeline.fit(X_train, y_train)

                # Predict on test data — pipeline applies learned transforms without refitting
                preds = pipeline.predict(X_test)
                dur = time.time() - start_t

                # Calculate metrics
                metrics = _calculate_metrics(task_type, y_test, preds)

                # Persist the COMPLETE fitted Pipeline (includes imputer + scaler + estimator)
                timestamp = int(time.time())
                filename = f"{dataset_uuid}_{name.replace(' ', '_')}_{timestamp}.joblib"
                model_path = models_dir / filename
                joblib.dump(pipeline, model_path)

                # Build rich metadata for this model
                metadata_info: Dict[str, Any] = {
                    "task_type": task_type,
                    "target_column": target_column,
                    "feature_columns": feature_cols,
                    "train_rows": train_rows,
                    "test_rows": test_rows,
                    "pipeline_steps": ["imputer", "scaler", "model"],
                    **split_meta,
                }
                # Time-series specific metadata
                if task_type in ["Forecasting", "Time Series"]:
                    metadata_info["datetime_column"] = dt_col
                    metadata_info["lag_features"] = lag_feature_names
                    metadata_info["rolling_features"] = rolling_feature_names

                rec.status = "COMPLETED"
                rec.metrics = metrics
                rec.model_path = str(model_path)
                rec.training_duration = dur
                rec.hyperparameters = estimator.get_params()
                rec.metadata_info = metadata_info

                logger.info(
                    "Trained '%s' for dataset %s in %.2fs — metrics=%s",
                    name,
                    dataset_uuid,
                    dur,
                    metrics,
                )

            except Exception as e:
                logger.exception(
                    "Training failed for model '%s' in dataset %s.", name, dataset_uuid
                )
                rec.status = "FAILED"
                rec.error_message = f"{type(e).__name__}: {str(e)[:200]}"

        # ----------------------------------------------------------------
        # Select best model among COMPLETED records
        # ----------------------------------------------------------------
        completed = [r for r in records if r.status == "COMPLETED"]
        if completed:
            if task_type == "Classification":
                best = max(completed, key=lambda r: (r.metrics or {}).get("Accuracy", 0.0))
            else:
                # For Regression and Time Series, minimise RMSE
                best = min(
                    completed, key=lambda r: (r.metrics or {}).get("RMSE", float("inf"))
                )
            best.is_best = True
            logger.info(
                "Best model for dataset %s: '%s'", dataset_uuid, best.algorithm
            )

        # ----------------------------------------------------------------
        # Persist all results
        # ----------------------------------------------------------------
        try:
            await db.commit()
            logger.info("Background training finished for dataset %s.", dataset_uuid)
        except Exception:
            logger.exception(
                "Failed to persist training results for dataset %s.", dataset_uuid
            )
