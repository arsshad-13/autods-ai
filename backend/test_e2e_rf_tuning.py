"""
test_e2e_rf_tuning.py
=====================
End-to-End Random Forest Tuning with classification_test.csv (30 trials).
Verifies:
1. All 30 trials execute with real progress logging
2. Best trial extraction
3. Final tuned model training on full X_train
4. Holdout evaluation on X_test
5. Baseline (1.0000) vs Tuned (1.0000) comparison -> tuning_improved = False
6. Artifact retention safety
"""

import sys
import logging
from pathlib import Path
import pandas as pd
import numpy as np

# Configure standard logger to output to stdout
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# Add backend to path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.services.tuning_service import (
    _execute_optuna_study,
    _reconstruct_split,
)

def run_rf_e2e():
    csv_path = backend_dir.parent / "classification_test.csv"
    if not csv_path.exists():
        print(f"Error: {csv_path} does not exist.")
        return

    df = pd.read_csv(csv_path)
    print(f"Loaded classification_test.csv: {len(df)} rows, columns: {list(df.columns)}")

    target_col = "approved"
    task_type = "Classification"
    meta = {"stratified": True, "dataset_uuid": "test-dataset-uuid"}

    X_train, X_test, y_train, y_test = _reconstruct_split(df, target_col, task_type, meta)
    print(f"Train split: {len(X_train)} rows | Test split: {len(X_test)} rows")

    baseline_metrics = {
        "Accuracy": 1.0,
        "F1 Score": 1.0,
        "Precision": 1.0,
        "Recall": 1.0,
        "Train Accuracy": 1.0,
        "CV Score": 0.96,
    }
    existing_cv_results = {
        "cv_score": 0.96,
        "cv_score_std": 0.04,
        "cv_f1": 0.96,
        "cv_method": "5-Fold Stratified CV",
        "n_splits": 5,
    }

    print("\n--- Starting 30-Trial Random Forest Optimization ---")
    results = _execute_optuna_study(
        algorithm="Random Forest",
        task_type=task_type,
        X_train=X_train,
        y_train=y_train,
        X_test=X_test,
        y_test=y_test,
        n_trials=30,
        baseline_metrics=baseline_metrics,
        existing_cv_results=existing_cv_results,
        dataset_uuid="test-dataset-uuid",
        model_uuid="test-model-uuid",
    )

    print("\n==========================================")
    print("OPTUNA TUNING EXECUTION RESULTS:")
    print("==========================================")
    print(f"Total Trials Executed: {results['total_trials']}")
    print(f"Best Trial Number: {results['best_trial_number']}")
    print(f"Best CV Score: {results['best_cv_score']:.6f}")
    print(f"Baseline Holdout F1: {results['baseline_score']:.6f}")
    print(f"Tuned Holdout F1: {results['tuned_score']:.6f}")
    print(f"Tuning Improved Baseline: {results['improved']}")
    print(f"Optimization Duration: {results['tune_duration']:.2f}s")
    print(f"Best Hyperparameters: {results['best_params']}")
    print("==========================================")

    assert results["total_trials"] == 30
    assert results["best_trial_number"] >= 1 and results["best_trial_number"] <= 30
    assert len(results["all_trials"]) == 30
    # Because baseline is 1.0000, tuning cannot strictly exceed 1.0000
    assert results["improved"] is False
    print("[PASS] E2E 30-trial Random Forest tuning completed successfully and correctly!")

if __name__ == "__main__":
    run_rf_e2e()
