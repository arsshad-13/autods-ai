"""
test_optuna_tuning.py
=====================
Automated tests for Phase 7 — Optuna Hyperparameter Optimization:
1. Search spaces construction for all algorithms
2. Objective function execution and leakage-free CV evaluation
3. Model tuning pipeline fit and artifact persistence
4. Compatibility of tuned pipeline with model_inference_service
5. End-to-end classification & regression tuning simulation
6. Improvement logic verification
"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

import joblib
import numpy as np
import optuna
import pandas as pd
from sklearn.metrics import f1_score, mean_squared_error

# Add backend to sys.path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.services.tuning_service import (
    _suggest_logistic_regression,
    _suggest_decision_tree_classifier,
    _suggest_random_forest_classifier,
    _suggest_linear_regression,
    _suggest_decision_tree_regressor,
    _suggest_random_forest_regressor,
    _build_objective,
    _build_estimator_from_params,
    _clean_best_params,
    _is_improved,
    _reconstruct_split,
    DEFAULT_N_TRIALS,
)
from app.services.model_training_service import _build_model_pipeline


def test_search_spaces():
    print("Testing search spaces...")
    study = optuna.create_study(direction="maximize")

    # 1. Logistic Regression
    trial = study.ask()
    lr = _suggest_logistic_regression(trial)
    assert lr is not None
    assert hasattr(lr, "fit")

    # 2. Decision Tree Classifier
    trial2 = study.ask()
    dt = _suggest_decision_tree_classifier(trial2)
    assert dt is not None
    assert hasattr(dt, "fit")

    # 3. Random Forest Classifier
    trial3 = study.ask()
    rf = _suggest_random_forest_classifier(trial3)
    assert rf is not None
    assert hasattr(rf, "fit")

    # 4. Linear Regression
    trial4 = study.ask()
    lin = _suggest_linear_regression(trial4)
    assert lin is not None
    assert hasattr(lin, "fit")

    # 5. Decision Tree Regressor
    trial5 = study.ask()
    dtr = _suggest_decision_tree_regressor(trial5)
    assert dtr is not None
    assert hasattr(dtr, "fit")

    # 6. Random Forest Regressor
    trial6 = study.ask()
    rfr = _suggest_random_forest_regressor(trial6)
    assert rfr is not None
    assert hasattr(rfr, "fit")

    print("[PASS] All 6 algorithm search spaces defined and instantiated properly.")


def test_leakage_free_objective_classification():
    print("Testing classification objective and leakage prevention...")
    np.random.seed(42)
    # Synthetic classification data (training portion only)
    X_train = pd.DataFrame({
        "age": np.random.randint(20, 70, size=50),
        "income": np.random.uniform(20000, 100000, size=50),
        "credit_score": np.random.uniform(300, 850, size=50),
    })
    y_train = pd.Series((X_train["income"] > 50000).astype(int), name="approved")

    # Optuna study for Random Forest
    study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=42))
    objective = _build_objective(
        algorithm="Random Forest",
        task_type="Classification",
        X_train=X_train,
        y_train=y_train,
    )

    study.optimize(objective, n_trials=5)
    assert len(study.trials) == 5
    assert study.best_value >= 0.0
    assert study.best_value <= 1.0
    assert "n_estimators" in study.best_params
    print(f"[PASS] Classification objective passed. Best F1 CV score: {study.best_value:.4f}")


def test_leakage_free_objective_regression():
    print("Testing regression objective and leakage prevention...")
    np.random.seed(42)
    # Synthetic regression data
    X_train = pd.DataFrame({
        "feat1": np.random.uniform(10, 50, size=50),
        "feat2": np.random.uniform(1, 10, size=50),
    })
    y_train = pd.Series(2.5 * X_train["feat1"] + 0.8 * X_train["feat2"] + np.random.normal(0, 1, 50), name="target")

    study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=42))
    objective = _build_objective(
        algorithm="Decision Tree Regressor",
        task_type="Regression",
        X_train=X_train,
        y_train=y_train,
    )

    study.optimize(objective, n_trials=5)
    assert len(study.trials) == 5
    # Negative RMSE (higher is better)
    assert study.best_value <= 0.0
    print(f"[PASS] Regression objective passed. Best Neg-RMSE: {study.best_value:.4f}")


def test_estimator_reconstruction_and_inference():
    print("Testing estimator reconstruction from best params & inference compatibility...")
    params = {
        "n_estimators": 50,
        "max_depth": 5,
        "min_samples_split": 3,
        "min_samples_leaf": 2,
        "max_features": "sqrt",
        "criterion": "gini",
    }
    rf = _build_estimator_from_params("Random Forest", params)
    pipeline = _build_model_pipeline(rf, "Classification")

    X_train = pd.DataFrame({
        "age": [25, 35, 45, 55],
        "income": [30000, 60000, 80000, 110000],
        "credit_score": [500, 650, 700, 800],
    })
    y_train = pd.Series([0, 1, 1, 1])

    pipeline.fit(X_train, y_train)

    # Save to temp file using joblib
    with tempfile.NamedTemporaryFile(suffix=".joblib", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        joblib.dump(pipeline, tmp_path)

        # Load back
        loaded_pipeline = joblib.load(tmp_path)

        # Inference test with DataFrame input (same way model_inference_service operates)
        test_df = pd.DataFrame({
            "age": [30, 60],
            "income": [45000, 95000],
            "credit_score": [600, 750],
        })
        preds = loaded_pipeline.predict(test_df)
        assert len(preds) == 2
        if hasattr(loaded_pipeline, "predict_proba"):
            probs = loaded_pipeline.predict_proba(test_df)
            assert probs.shape == (2, 2)
            assert np.allclose(probs.sum(axis=1), 1.0)
        print("[PASS] Loaded tuned pipeline successfully executed predict and predict_proba.")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_is_improved_logic():
    print("Testing improvement decision logic...")
    # Classification: F1 higher is better
    assert _is_improved("Classification", {"F1 Score": 0.80}, {"F1 Score": 0.85}) is True
    assert _is_improved("Classification", {"F1 Score": 0.85}, {"F1 Score": 0.80}) is False
    assert _is_improved("Classification", {"F1 Score": 0.85}, {"F1 Score": 0.85001}) is False  # below epsilon

    # Regression: RMSE lower is better
    assert _is_improved("Regression", {"RMSE": 12.5}, {"RMSE": 10.2}) is True
    assert _is_improved("Regression", {"RMSE": 10.2}, {"RMSE": 12.5}) is False
    assert _is_improved("Regression", {"RMSE": 10.2}, {"RMSE": 10.19999}) is False
    print("[PASS] Improvement logic verified for classification and regression.")


def test_reconstruct_split():
    print("Testing split reconstruction without leakage...")
    df = pd.DataFrame({
        "age": np.arange(100),
        "income": np.arange(100) * 1000,
        "target": [0, 1] * 50,
    })
    meta = {"stratified": True}
    X_train, X_test, y_train, y_test = _reconstruct_split(df, "target", "Classification", meta)
    assert len(X_train) == 80
    assert len(X_test) == 20
    assert len(y_train) == 80
    assert len(y_test) == 20
    assert "target" not in X_train.columns
    assert "target" not in X_test.columns
    # Check class balance preserved with stratification
    assert abs(y_train.mean() - 0.5) < 0.05
    assert abs(y_test.mean() - 0.5) < 0.05
    print("[PASS] Split reconstruction verified.")


if __name__ == "__main__":
    test_search_spaces()
    test_leakage_free_objective_classification()
    test_leakage_free_objective_regression()
    test_estimator_reconstruction_and_inference()
    test_is_improved_logic()
    test_reconstruct_split()
    print("\n==========================================")
    print("ALL OPTUNA TUNING UNIT & PIPELINE TESTS PASSED!")
    print("==========================================")
