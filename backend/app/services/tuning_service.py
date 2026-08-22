"""
tuning_service.py
=================
Phase 7 - Optuna Hyperparameter Optimization for AutoDS AI.

Architecture
------------
Baseline Training (model_training_service.py)
    -> all candidate models trained with default params
Optuna Tuning (this service)
    -> triggered by POST /datasets/{uuid}/models/{model_uuid}/tune
    -> Loads cleaned dataset
    -> Recreates the identical leakage-safe train/test split
    -> Defines algorithm-specific search space
    -> Runs N trials, each trial:
         - Builds Pipeline(Imputer -> Scaler -> Estimator)
         - Evaluates using CV on X_train ONLY
         - Never touches X_test / holdout
    -> Selects best hyperparameters from trial results
    -> Trains final Pipeline on full X_train with best params
    -> Evaluates final model on holdout X_test
    -> Overwrites the model record if improvement is detected

Leakage prevention
------------------
- pipeline.fit() called ONLY on X_train inside every trial.
- cross_val_score() receives only X_train, y_train.
- X_test is used exactly once - for final holdout evaluation only.
- Imputer/Scaler statistics are re-learned per fold inside CV.

Storage
-------
No schema migration required. Optuna metadata is stored in
TrainedModel.metadata_info (JSONB):
  - tuning_status       : QUEUED | RUNNING | COMPLETED | FAILED
  - tuning_n_trials     : int
  - tuning_best_trial   : int
  - tuning_best_score   : float
  - tuning_best_params  : dict
  - tuning_metric       : str
  - tuning_duration     : float (seconds)
  - tuning_all_trials   : List[dict] (per-trial results)
  - tuning_improved     : bool

TrainedModel.hyperparameters is overwritten with the best
Optuna parameters if the tuned model outperforms the baseline.
"""

import asyncio
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

import joblib
import numpy as np
import optuna
import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.model_selection import (
    KFold,
    StratifiedKFold,
    cross_val_score,
    train_test_split,
)
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor

from app.config import get_settings
from app.models.dataset_preprocessing import DatasetPreprocessing
from app.models.trained_model import TrainedModel
from app.services.model_training_service import (
    _build_model_pipeline,
    _calculate_comprehensive_evaluation,
    _get_models_dir,
    get_model,
)

logger = logging.getLogger(__name__)
settings = get_settings()

# Default Optuna trial budget per model.
DEFAULT_N_TRIALS = 30

# Suppress Optuna's per-trial INFO/WARNING spam.
optuna.logging.set_verbosity(optuna.logging.WARNING)


# ---------------------------------------------------------------------------
# Search-space definitions - one function per algorithm family
# ---------------------------------------------------------------------------

def _suggest_logistic_regression(trial: optuna.Trial) -> LogisticRegression:
    """
    Search space for Logistic Regression.
    Solver/penalty pairs constrained to valid sklearn combinations.
    """
    solver = trial.suggest_categorical("solver", ["lbfgs", "saga", "liblinear"])

    if solver == "lbfgs":
        penalty = trial.suggest_categorical("penalty_lbfgs", ["l2", None])
    elif solver == "saga":
        penalty = trial.suggest_categorical("penalty_saga", ["l1", "l2", None])
    else:  # liblinear
        penalty = trial.suggest_categorical("penalty_liblinear", ["l1", "l2"])

    C = trial.suggest_float("C", 1e-3, 100.0, log=True)
    max_iter = trial.suggest_int("max_iter", 200, 2000, step=200)

    params: Dict[str, Any] = {
        "solver": solver,
        "penalty": penalty,
        "C": C,
        "max_iter": max_iter,
        "random_state": 42,
    }

    if solver == "saga" and penalty == "elasticnet":
        params["l1_ratio"] = trial.suggest_float("l1_ratio", 0.0, 1.0)

    return LogisticRegression(**params)


def _suggest_decision_tree_classifier(trial: optuna.Trial) -> DecisionTreeClassifier:
    """Search space for Decision Tree Classifier."""
    return DecisionTreeClassifier(
        max_depth=trial.suggest_int("max_depth", 2, 20),
        min_samples_split=trial.suggest_int("min_samples_split", 2, 20),
        min_samples_leaf=trial.suggest_int("min_samples_leaf", 1, 10),
        criterion=trial.suggest_categorical("dt_criterion", ["gini", "entropy"]),
        random_state=42,
    )


def _suggest_random_forest_classifier(trial: optuna.Trial) -> RandomForestClassifier:
    """Search space for Random Forest Classifier."""
    return RandomForestClassifier(
        n_estimators=trial.suggest_int("n_estimators", 50, 300, step=50),
        max_depth=trial.suggest_int("max_depth", 3, 25),
        min_samples_split=trial.suggest_int("min_samples_split", 2, 20),
        min_samples_leaf=trial.suggest_int("min_samples_leaf", 1, 10),
        max_features=trial.suggest_categorical("max_features", ["sqrt", "log2", None]),
        criterion=trial.suggest_categorical("rf_criterion", ["gini", "entropy"]),
        random_state=42,
        n_jobs=1,
    )


def _suggest_decision_tree_regressor(trial: optuna.Trial) -> DecisionTreeRegressor:
    """Search space for Decision Tree Regressor."""
    return DecisionTreeRegressor(
        max_depth=trial.suggest_int("max_depth", 2, 20),
        min_samples_split=trial.suggest_int("min_samples_split", 2, 20),
        min_samples_leaf=trial.suggest_int("min_samples_leaf", 1, 10),
        criterion=trial.suggest_categorical("dtr_criterion", ["squared_error", "friedman_mse"]),
        random_state=42,
    )


def _suggest_random_forest_regressor(trial: optuna.Trial) -> RandomForestRegressor:
    """Search space for Random Forest Regressor."""
    return RandomForestRegressor(
        n_estimators=trial.suggest_int("n_estimators", 50, 300, step=50),
        max_depth=trial.suggest_int("max_depth", 3, 25),
        min_samples_split=trial.suggest_int("min_samples_split", 2, 20),
        min_samples_leaf=trial.suggest_int("min_samples_leaf", 1, 10),
        max_features=trial.suggest_categorical("max_features", ["sqrt", "log2", None]),
        criterion=trial.suggest_categorical("rfr_criterion", ["squared_error", "friedman_mse"]),
        random_state=42,
        n_jobs=1,
    )


def _suggest_linear_regression(_trial: optuna.Trial) -> LinearRegression:
    """
    LinearRegression has no meaningful hyperparameters to tune.
    Returns a fixed instance; study will run 1 trial.
    """
    return LinearRegression()


# Map algorithm name -> suggester function
_SUGGESTER_MAP: Dict[str, Any] = {
    "Logistic Regression": _suggest_logistic_regression,
    "Decision Tree": _suggest_decision_tree_classifier,
    "Random Forest": _suggest_random_forest_classifier,
    "Linear Regression": _suggest_linear_regression,
    "Decision Tree Regressor": _suggest_decision_tree_regressor,
    "Random Forest Regressor": _suggest_random_forest_regressor,
}


# ---------------------------------------------------------------------------
# Objective factory
# ---------------------------------------------------------------------------

def _build_objective(
    algorithm: str,
    task_type: str,
    X_train: pd.DataFrame,
    y_train: pd.Series,
) -> Any:
    """
    Returns a callable objective(trial) for the given algorithm.

    CRITICAL: X_test is never passed here. The objective evaluates ONLY on
    X_train / y_train via cross-validation to prevent leakage.
    """
    suggester = _SUGGESTER_MAP.get(algorithm)
    if suggester is None:
        raise ValueError(f"No Optuna search space defined for algorithm: '{algorithm}'")

    n_train = len(X_train)

    def objective(trial: optuna.Trial) -> float:
        estimator = suggester(trial)
        pipeline = _build_model_pipeline(estimator, task_type)

        if task_type == "Classification":
            min_class_count = int(y_train.value_counts().min())
            if min_class_count < 2:
                pipeline.fit(X_train, y_train)
                from sklearn.metrics import f1_score as _f1
                preds = pipeline.predict(X_train)
                return float(_f1(y_train, preds, average="weighted", zero_division=0))

            n_splits = min(5, max(2, min_class_count))
            cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)
            scores = cross_val_score(
                pipeline, X_train, y_train,
                cv=cv, scoring="f1_weighted", error_score=0.0,
            )
            return float(np.mean(scores))

        else:  # Regression
            n_splits = min(5, max(2, n_train // 6))
            if n_splits < 2:
                pipeline.fit(X_train, y_train)
                from sklearn.metrics import mean_squared_error as _mse
                preds = pipeline.predict(X_train)
                return -float(np.sqrt(_mse(y_train, preds)))

            cv = KFold(n_splits=n_splits, shuffle=True, random_state=42)
            scores = cross_val_score(
                pipeline, X_train, y_train,
                cv=cv, scoring="neg_root_mean_squared_error", error_score=0.0,
            )
            return float(np.mean(scores))  # negative; study direction = maximize

    return objective


# ---------------------------------------------------------------------------
# Split reconstruction helper
# ---------------------------------------------------------------------------

def _reconstruct_split(
    df: pd.DataFrame,
    target_column: str,
    task_type: str,
    metadata_info: Dict[str, Any],
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    """
    Recreate the exact same train/test split as baseline training.
    Uses random_state=42 and the same stratify decision stored in metadata_info.
    Guarantees Optuna never sees holdout data.
    """
    df = df.copy()

    if target_column not in df.columns:
        raise ValueError(f"Target column '{target_column}' not found in cleaned dataset.")

    # Encode target
    if task_type == "Classification":
        y_raw = df[target_column]
        if y_raw.dtype == object or str(y_raw.dtype) == "category":
            y = y_raw.astype("category").cat.codes
        else:
            y = pd.to_numeric(y_raw, errors="coerce")
    else:
        y = pd.to_numeric(df[target_column], errors="coerce")

    valid_mask = y.notna()
    df = df.loc[valid_mask].copy()
    y = y.loc[valid_mask]

    X = df.drop(columns=[target_column])
    X = X.select_dtypes(include=[np.number])

    if X.empty:
        raise ValueError("No numeric features available after column filtering.")

    was_stratified = metadata_info.get("stratified", False)

    if task_type == "Classification" and was_stratified:
        min_class = int(y.value_counts().min())
        if min_class >= 2:
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42, stratify=y
            )
        else:
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42
            )
    else:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

    return X_train, X_test, y_train, y_test


# ---------------------------------------------------------------------------
# Build estimator from best params dict
# ---------------------------------------------------------------------------

def _build_estimator_from_params(algorithm: str, params: Dict[str, Any]) -> Any:
    """Instantiate a concrete sklearn estimator from the best hyperparameter dict."""
    if algorithm == "Logistic Regression":
        clean: Dict[str, Any] = {
            "solver": params.get("solver", "lbfgs"),
            "penalty": params.get("penalty"),
            "C": params.get("C", 1.0),
            "max_iter": params.get("max_iter", 1000),
            "random_state": 42,
        }
        if clean.get("penalty") == "elasticnet":
            clean["l1_ratio"] = params.get("l1_ratio", 0.5)
        return LogisticRegression(**clean)

    elif algorithm == "Decision Tree":
        return DecisionTreeClassifier(
            max_depth=params.get("max_depth", 5),
            min_samples_split=params.get("min_samples_split", 2),
            min_samples_leaf=params.get("min_samples_leaf", 1),
            criterion=params.get("criterion", "gini"),
            random_state=42,
        )

    elif algorithm == "Random Forest":
        return RandomForestClassifier(
            n_estimators=params.get("n_estimators", 100),
            max_depth=params.get("max_depth"),
            min_samples_split=params.get("min_samples_split", 2),
            min_samples_leaf=params.get("min_samples_leaf", 1),
            max_features=params.get("max_features", "sqrt"),
            criterion=params.get("criterion", "gini"),
            random_state=42,
            n_jobs=1,
        )

    elif algorithm == "Linear Regression":
        return LinearRegression()

    elif algorithm == "Decision Tree Regressor":
        return DecisionTreeRegressor(
            max_depth=params.get("max_depth", 5),
            min_samples_split=params.get("min_samples_split", 2),
            min_samples_leaf=params.get("min_samples_leaf", 1),
            criterion=params.get("criterion", "squared_error"),
            random_state=42,
        )

    elif algorithm == "Random Forest Regressor":
        return RandomForestRegressor(
            n_estimators=params.get("n_estimators", 100),
            max_depth=params.get("max_depth"),
            min_samples_split=params.get("min_samples_split", 2),
            min_samples_leaf=params.get("min_samples_leaf", 1),
            max_features=params.get("max_features", "sqrt"),
            criterion=params.get("criterion", "squared_error"),
            random_state=42,
            n_jobs=1,
        )

    else:
        raise ValueError(f"Unknown algorithm for estimator construction: '{algorithm}'")


# ---------------------------------------------------------------------------
# Clean Optuna trial params (normalise solver/penalty keys for LR)
# ---------------------------------------------------------------------------

def _clean_best_params(raw_params: Dict[str, Any], algorithm: str) -> Dict[str, Any]:
    """
    Normalise Optuna parameters into standard scikit-learn parameter names:
      - LR: extracts penalty from solver-specific key
      - Tree/Forest: extracts criterion from algorithm-specific key
    """
    cleaned: Dict[str, Any] = {}
    penalty = None
    criterion = None

    for k, v in raw_params.items():
        if k.startswith("penalty_"):
            penalty = v
        elif k.endswith("_criterion"):
            criterion = v
        else:
            cleaned[k] = v

    if algorithm == "Logistic Regression" and penalty is not None:
        cleaned["penalty"] = penalty
    if criterion is not None:
        cleaned["criterion"] = criterion

    return cleaned


# ---------------------------------------------------------------------------
# Improvement check
# ---------------------------------------------------------------------------

def _is_improved(
    task_type: str,
    baseline_metrics: Dict[str, Any],
    tuned_metrics: Dict[str, Any],
) -> bool:
    """
    True if the tuned model is strictly better than the baseline on the
    primary selection metric. A small epsilon prevents meaningless updates.
    """
    epsilon = 1e-4

    if task_type == "Classification":
        baseline_f1 = float(baseline_metrics.get("F1 Score", 0.0))
        tuned_f1 = float(tuned_metrics.get("F1 Score", 0.0))
        return (tuned_f1 - baseline_f1) > epsilon
    else:
        baseline_rmse = float(baseline_metrics.get("RMSE", float("inf")))
        tuned_rmse = float(tuned_metrics.get("RMSE", float("inf")))
        return (baseline_rmse - tuned_rmse) > epsilon


# ---------------------------------------------------------------------------
# Public: validate_model_for_tuning
# ---------------------------------------------------------------------------

async def validate_model_for_tuning(
    dataset_uuid: UUID,
    model_uuid: UUID,
    user_id: int,
    db: AsyncSession,
) -> TrainedModel:
    """
    Validate that a model can be tuned:
      - Owned by the requesting user.
      - Belongs to the specified dataset.
      - Has COMPLETED status.
      - Is not a Time Series / Forecasting model.
      - Has a defined search space.
      - Is not already being tuned.

    Returns the TrainedModel record. Raises HTTPException on failure.
    """
    from fastapi import HTTPException, status as http_status

    model = await get_model(dataset_uuid, model_uuid, user_id, db)

    if model.status != "COMPLETED":
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Model must have COMPLETED status before tuning. "
                f"Current status: {model.status}."
            ),
        )

    if model.task_type in ["Forecasting", "Time Series"]:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Hyperparameter tuning is not supported for Time Series / Forecasting models.",
        )

    if model.algorithm not in _SUGGESTER_MAP:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"No Optuna search space defined for algorithm '{model.algorithm}'.",
        )

    current_tuning = (model.metadata_info or {}).get("tuning_status")
    if current_tuning in ("QUEUED", "RUNNING"):
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail="Tuning is already in progress for this model. Wait for it to complete.",
        )

    return model


# ---------------------------------------------------------------------------
# Synchronous Optuna study execution (runs in worker thread)
# ---------------------------------------------------------------------------

def _execute_optuna_study(
    algorithm: str,
    task_type: str,
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    n_trials: int,
    baseline_metrics: Dict[str, Any],
    existing_cv_results: Dict[str, Any],
    dataset_uuid: str,
    model_uuid: str,
) -> Dict[str, Any]:
    """
    Synchronous worker function that runs the CPU-bound Optuna search and model evaluation.
    Must NOT perform async DB operations or use AsyncSession.
    Executed in a worker thread via asyncio.to_thread().
    """
    logger.info(
        "Tuning started for model %s (algorithm='%s', n_trials=%d)",
        model_uuid,
        algorithm,
        n_trials,
    )

    effective_n_trials = 1 if algorithm == "Linear Regression" else n_trials

    study = optuna.create_study(
        direction="maximize",
        sampler=optuna.samplers.TPESampler(seed=42),
        pruner=optuna.pruners.MedianPruner(n_startup_trials=5, n_warmup_steps=0),
    )
    logger.info("Study created for algorithm '%s'", algorithm)

    objective = _build_objective(
        algorithm=algorithm,
        task_type=task_type,
        X_train=X_train,
        y_train=y_train,
    )

    # Optuna trial callback for granular progress logging
    def _trial_callback(study: optuna.Study, trial: optuna.trial.FrozenTrial) -> None:
        trial_num = trial.number + 1
        score_str = f"{trial.value:.6f}" if trial.value is not None else "failed/pruned"
        best_str = f"{study.best_value:.6f}" if study.best_trial else "N/A"
        logger.info(
            "Trial %d/%d completed with score: %s | Best score so far: %s",
            trial_num,
            effective_n_trials,
            score_str,
            best_str,
        )

    tune_start = time.time()
    study.optimize(
        objective,
        n_trials=effective_n_trials,
        timeout=None,
        show_progress_bar=False,
        callbacks=[_trial_callback],
        catch=(Exception,),
    )
    tune_duration = time.time() - tune_start

    logger.info(
        "Study optimization completed in %.2fs (%d trials)",
        tune_duration,
        len(study.trials),
    )

    completed_trials = [t for t in study.trials if t.value is not None]
    if not completed_trials:
        raise ValueError("All Optuna trials failed. No best trial available.")

    best_trial = study.best_trial
    best_params = _clean_best_params(best_trial.params, algorithm)
    best_cv_score = float(best_trial.value)
    logger.info(
        "Best trial identified: Trial #%d with score %.6f (params=%s)",
        best_trial.number + 1,
        best_cv_score,
        best_params,
    )

    # Collect all trial results for persistence & frontend inspection
    all_trials: List[Dict[str, Any]] = []
    for t in study.trials:
        if t.value is not None:
            all_trials.append({
                "trial_number": t.number + 1,
                "score": round(float(t.value), 6),
                "params": _clean_best_params(t.params, algorithm),
                "state": t.state.name,
            })

    # Train final tuned model on full X_train using best parameters
    logger.info("Final tuned model fitting started for algorithm '%s'", algorithm)
    final_estimator = _build_estimator_from_params(algorithm, best_params)
    final_pipeline = _build_model_pipeline(final_estimator, task_type)

    final_fit_start = time.time()
    final_pipeline.fit(X_train, y_train)
    final_fit_duration = time.time() - final_fit_start
    logger.info("Final tuned model fitting completed in %.2fs", final_fit_duration)

    # Evaluate on the SAME untouched holdout test split (X_test, y_test)
    train_preds = final_pipeline.predict(X_train)
    test_preds = final_pipeline.predict(X_test)

    tuned_metrics, tuned_eval_details = _calculate_comprehensive_evaluation(
        task_type=task_type,
        pipeline=final_pipeline,
        X_train=X_train,
        y_train=y_train,
        X_test=X_test,
        y_test=y_test,
        train_preds=train_preds,
        test_preds=test_preds,
        cv_results=existing_cv_results,
    )

    improved = _is_improved(task_type, baseline_metrics, tuned_metrics)

    if task_type == "Classification":
        opt_metric = "F1 Score"
        baseline_score = float(baseline_metrics.get("F1 Score", 0.0))
        tuned_score = float(tuned_metrics.get("F1 Score", 0.0))
    else:
        opt_metric = "RMSE"
        baseline_score = float(baseline_metrics.get("RMSE", float("inf")))
        tuned_score = float(tuned_metrics.get("RMSE", float("inf")))

    logger.info(
        "Tuning evaluation result: improved=%s | baseline_%s=%.6f | tuned_%s=%.6f",
        improved,
        opt_metric,
        baseline_score,
        opt_metric,
        tuned_score,
    )

    # Persist artifact if and only if tuned model strictly improves baseline
    tuned_model_path_str: Optional[str] = None
    if improved:
        logger.info("Artifact persistence started: saving tuned model pipeline")
        models_dir = _get_models_dir()
        timestamp = int(time.time())
        filename = f"{dataset_uuid}_{algorithm.replace(' ', '_')}_tuned_{timestamp}.joblib"
        tuned_model_path = models_dir / filename
        joblib.dump(final_pipeline, tuned_model_path)
        tuned_model_path_str = str(tuned_model_path)
        logger.info("Artifact persistence completed: %s", tuned_model_path_str)
    else:
        logger.info(
            "Tuned model did not improve baseline — retaining existing baseline model artifact."
        )

    return {
        "improved": improved,
        "tuned_metrics": tuned_metrics,
        "best_params": best_params,
        "best_trial_number": best_trial.number + 1,
        "best_cv_score": best_cv_score,
        "opt_metric": opt_metric,
        "baseline_score": baseline_score,
        "tuned_score": tuned_score,
        "tune_duration": tune_duration,
        "final_fit_duration": final_fit_duration,
        "tuned_model_path": tuned_model_path_str,
        "all_trials": all_trials,
        "tuned_eval_details": tuned_eval_details,
        "total_trials": len(study.trials),
    }


# ---------------------------------------------------------------------------
# Public: run_tuning (background task entry point)
# ---------------------------------------------------------------------------

async def run_tuning(
    dataset_uuid: str,
    model_uuid: str,
    user_id: int,
    n_trials: int = DEFAULT_N_TRIALS,
) -> None:
    """
    Background task entry point for Optuna hyperparameter tuning.

    Architecture:
      1. Short-lived AsyncSession: read model & dataset, mark RUNNING, close session.
      2. Offload CPU-bound ML computation to worker thread via asyncio.to_thread().
      3. Open fresh short-lived AsyncSession: persist results, mark COMPLETED/FAILED, close session.
    """
    from app.database import AsyncSessionLocal

    # -----------------------------------------------------------------------
    # Step 1: Short-lived session to validate, load data, and mark RUNNING
    # -----------------------------------------------------------------------
    try:
        async with AsyncSessionLocal() as db:
            stmt = select(TrainedModel).where(TrainedModel.uuid == model_uuid)
            result = await db.execute(stmt)
            record: Optional[TrainedModel] = result.scalar_one_or_none()

            if record is None:
                logger.error("Tuning aborted: model %s not found.", model_uuid)
                return

            algorithm = record.algorithm
            task_type = record.task_type
            target_column = record.target_column
            dataset_id = record.dataset_id
            baseline_metrics = dict(record.metrics or {})
            existing_meta = dict(record.metadata_info or {})
            current_duration = record.training_duration or 0.0

            # Find preprocessing record to locate clean dataset
            prep_stmt = select(DatasetPreprocessing).where(
                DatasetPreprocessing.dataset_id == dataset_id
            )
            prep_res = await db.execute(prep_stmt)
            preprocessing = prep_res.scalar_one_or_none()

            if not preprocessing or not preprocessing.clean_dataset_path:
                raise ValueError("Preprocessing record not found for dataset.")

            clean_path = Path(preprocessing.clean_dataset_path)
            if not clean_path.exists():
                raise ValueError(f"Clean dataset file not found: {clean_path}")

            df = (
                pd.read_csv(clean_path)
                if clean_path.suffix == ".csv"
                else pd.read_excel(clean_path)
            )

            # Reconstruct identical train/test split without leakage
            X_train, X_test, y_train, y_test = _reconstruct_split(
                df=df,
                target_column=target_column,
                task_type=task_type,
                metadata_info=existing_meta,
            )

            # Mark RUNNING and commit
            existing_meta["tuning_status"] = "RUNNING"
            existing_meta["tuning_n_trials"] = n_trials
            existing_meta["tuning_completed_trials"] = 0
            existing_meta["tuning_total_trials"] = n_trials
            record.metadata_info = existing_meta
            await db.commit()

        # Database session is closed here before long-running computation!
    except Exception as e:
        logger.exception("Tuning initialization failed for model %s: %s", model_uuid, e)
        async with AsyncSessionLocal() as db:
            stmt = select(TrainedModel).where(TrainedModel.uuid == model_uuid)
            result = await db.execute(stmt)
            rec = result.scalar_one_or_none()
            if rec:
                meta = dict(rec.metadata_info or {})
                meta["tuning_status"] = "FAILED"
                meta["tuning_error"] = f"Initialization failed: {str(e)[:200]}"
                rec.metadata_info = meta
                await db.commit()
        return

    # -----------------------------------------------------------------------
    # Step 2: Offload CPU-bound Optuna computation to worker thread
    # -----------------------------------------------------------------------
    existing_cv_results = {
        "cv_score": existing_meta.get("cv_score"),
        "cv_score_std": existing_meta.get("cv_score_std"),
        "cv_f1": existing_meta.get("cv_f1"),
        "cv_method": existing_meta.get("cv_method", ""),
        "n_splits": existing_meta.get("cv_n_splits", 0),
    }

    try:
        results = await asyncio.to_thread(
            _execute_optuna_study,
            algorithm=algorithm,
            task_type=task_type,
            X_train=X_train,
            y_train=y_train,
            X_test=X_test,
            y_test=y_test,
            n_trials=n_trials,
            baseline_metrics=baseline_metrics,
            existing_cv_results=existing_cv_results,
            dataset_uuid=dataset_uuid,
            model_uuid=model_uuid,
        )
    except Exception as e:
        logger.exception("Tuning execution failed for model %s: %s", model_uuid, e)
        async with AsyncSessionLocal() as db:
            stmt = select(TrainedModel).where(TrainedModel.uuid == model_uuid)
            result = await db.execute(stmt)
            rec = result.scalar_one_or_none()
            if rec:
                meta = dict(rec.metadata_info or {})
                meta["tuning_status"] = "FAILED"
                meta["tuning_error"] = f"Optimization failed: {str(e)[:200]}"
                rec.metadata_info = meta
                await db.commit()
        return

    # -----------------------------------------------------------------------
    # Step 3: Open fresh short-lived session to persist final tuning results
    # -----------------------------------------------------------------------
    logger.info("Persisting tuning results for model %s", model_uuid)
    try:
        async with AsyncSessionLocal() as db:
            stmt = select(TrainedModel).where(TrainedModel.uuid == model_uuid)
            result = await db.execute(stmt)
            rec = result.scalar_one_or_none()

            if rec is None:
                logger.error("Tuning persistence error: model %s no longer in DB.", model_uuid)
                return

            meta = dict(rec.metadata_info or {})

            if results["improved"]:
                rec.metrics = results["tuned_metrics"]
                rec.hyperparameters = results["best_params"]
                if results["tuned_model_path"]:
                    rec.model_path = results["tuned_model_path"]
                rec.training_duration = (
                    current_duration + results["tune_duration"] + results["final_fit_duration"]
                )

                tuned_eval = results["tuned_eval_details"]
                meta["confusion_matrix"] = tuned_eval.get("confusion_matrix")
                meta["overfitting_detected"] = tuned_eval.get("overfitting_detected", False)
                meta["generalization_status"] = tuned_eval.get(
                    "generalization_status", "Good Generalization"
                )

            tuning_metadata: Dict[str, Any] = {
                "tuning_status": "COMPLETED",
                "tuning_n_trials": results["total_trials"],
                "tuning_completed_trials": results["total_trials"],
                "tuning_total_trials": n_trials,
                "tuning_best_trial": results["best_trial_number"],
                "tuning_best_score": round(results["best_cv_score"], 6),
                "tuning_best_params": results["best_params"],
                "tuning_metric": results["opt_metric"],
                "tuning_duration": round(results["tune_duration"], 2),
                "tuning_improved": results["improved"],
                "tuning_baseline_score": round(results["baseline_score"], 6),
                "tuning_tuned_score": round(results["tuned_score"], 6),
                "tuning_all_trials": results["all_trials"],
            }
            meta.update(tuning_metadata)
            rec.metadata_info = meta
            await db.commit()

        logger.info("Tuning completed successfully for model %s", model_uuid)

    except Exception as e:
        logger.exception("Failed to persist final tuning metadata for model %s: %s", model_uuid, e)

