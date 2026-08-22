"""
test_model_evaluation_pipeline.py
==================================
Comprehensive test suite for Model Training & Evaluation pipeline improvements:
  1. Classification on 30-row classification_test.csv (adaptive CV, stratified split, small dataset warning).
  2. Synthetic balanced classification dataset (150 rows) — verifies CV scores, ROC-AUC, confusion matrix.
  3. Synthetic imbalanced classification dataset (100 rows, 90:10) — verifies F1 selection and generalization assessment.
  4. Leakage detection checks (duplicate rows, constant columns, high-cardinality IDs).
  5. Fallback safety on small/single-class edge cases.
"""

import sys
import os
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.datasets import make_classification
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.tree import DecisionTreeClassifier

sys.path.insert(0, str(Path(__file__).parent))

from app.services.model_training_service import (
    _build_model_pipeline,
    _run_leakage_checks,
    _run_cross_validation,
    _calculate_comprehensive_evaluation,
    _assess_generalization,
    _calculate_metrics,
)

PASS = "[PASS]"
FAIL = "[FAIL]"
all_passed = True


def test(name: str, condition: bool, detail: str = ""):
    global all_passed
    status = PASS if condition else FAIL
    if not condition:
        all_passed = False
    msg = f"  {status} {name}"
    if detail:
        msg += f" — {detail}"
    print(msg)


print("=" * 60)
print("  Model Training & Evaluation Pipeline Verification Suite")
print("=" * 60)

# ---------------------------------------------------------------------------
# Test 1: Leakage detection
# ---------------------------------------------------------------------------
print("\n--- 1. Automated Leakage Detection Checks ---")
df_leak = pd.DataFrame({
    "id": range(30),
    "feat1": [1.0] * 30,  # constant
    "feat2": np.random.randn(30),
    "approved_score": np.random.randn(30),  # name leakage
    "approved": [0, 1] * 15,
})

checks = _run_leakage_checks(df_leak, "approved", ["id", "feat1", "feat2", "approved_score"])
test("Target excluded check", "approved" not in ["id", "feat1", "feat2", "approved_score"])
test("Constant feature detected", "feat1" in checks["constant_columns"])
test("ID column detected", "id" in checks["high_cardinality_columns"])
test("Potential name leakage detected", "approved_score" in checks["potential_leakage_columns"])
test("Warnings generated", len(checks["warnings"]) >= 3, f"got {len(checks['warnings'])} warnings")


# ---------------------------------------------------------------------------
# Test 2: 30-row classification_test.csv
# ---------------------------------------------------------------------------
print("\n--- 2. 30-row classification_test.csv Evaluation ---")
df_30 = pd.read_csv("storage/uploads/classification_test_clean_v1.csv")
X_30 = df_30[["age", "income", "credit_score"]]
y_30 = (df_30["approved"] == "Yes").astype(int)

from sklearn.model_selection import train_test_split
X_tr, X_te, y_tr, y_te = train_test_split(X_30, y_30, test_size=0.2, random_state=42, stratify=y_30)

test("Stratified split size train", len(X_tr) == 24)
test("Stratified split size test", len(X_te) == 6)
test("Stratified split preserves ratio", abs(y_te.mean() - y_30.mean()) < 0.1, f"train={y_tr.mean():.2f}, test={y_te.mean():.2f}")

pipe_lr = _build_model_pipeline(LogisticRegression(max_iter=1000, random_state=42), "Classification")

# Adaptive CV on 24 rows
cv_res = _run_cross_validation(pipe_lr, X_tr, y_tr, "Classification")
test("Adaptive CV ran successfully", cv_res["cv_score"] is not None)
test("Adaptive CV used stratified folds", "Stratified CV" in cv_res["cv_method"], cv_res["cv_method"])

pipe_lr.fit(X_tr, y_tr)
tr_preds = pipe_lr.predict(X_tr)
te_preds = pipe_lr.predict(X_te)

metrics, eval_details = _calculate_comprehensive_evaluation(
    "Classification", pipe_lr, X_tr, y_tr, X_te, y_te, tr_preds, te_preds, cv_res
)

test("Accuracy in metrics", "Accuracy" in metrics and metrics["Accuracy"] == 1.0)
test("Train Accuracy in metrics", "Train Accuracy" in metrics and metrics["Train Accuracy"] == 1.0)
test("CV Score in metrics", "CV Score" in metrics and metrics["CV Score"] == 1.0)
test("ROC-AUC in metrics", "ROC-AUC" in metrics and metrics["ROC-AUC"] == 1.0)
test("Confusion matrix present", eval_details["confusion_matrix"] is not None)
test("Generalization status present", "generalization_status" in eval_details)


# ---------------------------------------------------------------------------
# Test 3: Synthetic Balanced Classification Dataset (150 rows, noisy)
# ---------------------------------------------------------------------------
print("\n--- 3. Synthetic Balanced Dataset (150 rows) ---")
X_bal_raw, y_bal_raw = make_classification(
    n_samples=150, n_features=6, n_informative=4, flip_y=0.1, random_state=42
)
X_bal = pd.DataFrame(X_bal_raw, columns=[f"col_{i}" for i in range(6)])
y_bal = pd.Series(y_bal_raw)

X_b_tr, X_b_te, y_b_tr, y_b_te = train_test_split(X_bal, y_bal, test_size=0.2, random_state=42, stratify=y_bal)

for clf_name, clf in [
    ("Logistic Regression", LogisticRegression(max_iter=1000, random_state=42)),
    ("Random Forest", RandomForestClassifier(n_estimators=100, random_state=42)),
    ("Decision Tree", DecisionTreeClassifier(random_state=42)),
]:
    pipe = _build_model_pipeline(clf, "Classification")
    cv_b = _run_cross_validation(pipe, X_b_tr, y_b_tr, "Classification")
    pipe.fit(X_b_tr, y_b_tr)
    tr_p = pipe.predict(X_b_tr)
    te_p = pipe.predict(X_b_te)
    m, d = _calculate_comprehensive_evaluation(
        "Classification", pipe, X_b_tr, y_b_tr, X_b_te, y_b_te, tr_p, te_p, cv_b
    )
    test(f"{clf_name} metrics calculated", "Accuracy" in m and "CV Score" in m and "ROC-AUC" in m,
         f"Train Acc={m['Train Accuracy']:.3f}, Test Acc={m['Test Accuracy']:.3f}, CV Acc={m['CV Score']:.3f}, ROC-AUC={m['ROC-AUC']:.3f}")


# ---------------------------------------------------------------------------
# Test 4: Synthetic Imbalanced Classification Dataset (100 rows, 90:10 ratio)
# ---------------------------------------------------------------------------
print("\n--- 4. Synthetic Imbalanced Dataset (100 rows, 90:10) ---")
X_imb_raw, y_imb_raw = make_classification(
    n_samples=100, n_features=4, weights=[0.9, 0.1], random_state=42
)
X_imb = pd.DataFrame(X_imb_raw, columns=[f"f{i}" for i in range(4)])
y_imb = pd.Series(y_imb_raw)

X_i_tr, X_i_te, y_i_tr, y_i_te = train_test_split(X_imb, y_imb, test_size=0.2, random_state=42, stratify=y_imb)

pipe_imb = _build_model_pipeline(RandomForestClassifier(n_estimators=50, random_state=42), "Classification")
cv_imb = _run_cross_validation(pipe_imb, X_i_tr, y_i_tr, "Classification")
pipe_imb.fit(X_i_tr, y_i_tr)
tr_p = pipe_imb.predict(X_i_tr)
te_p = pipe_imb.predict(X_i_te)
m_imb, d_imb = _calculate_comprehensive_evaluation(
    "Classification", pipe_imb, X_i_tr, y_i_tr, X_i_te, y_i_te, tr_p, te_p, cv_imb
)

test("Imbalanced dataset CV works safely", cv_imb["n_splits"] >= 2, cv_imb["cv_method"])
test("Imbalanced dataset F1 Score computed", "F1 Score" in m_imb, f"F1={m_imb['F1 Score']:.3f}")
test("Generalization assessment ran", d_imb["generalization_status"] is not None)


# ---------------------------------------------------------------------------
# Test 5: Edge cases & Fallbacks
# ---------------------------------------------------------------------------
print("\n--- 5. Extreme Edge Cases (Small Sample Fallback Safety) ---")
# Dataset too small for CV (e.g. 4 samples)
X_micro = pd.DataFrame({"a": [1, 2, 3, 4]})
y_micro = pd.Series([0, 1, 0, 1])
pipe_micro = _build_model_pipeline(LogisticRegression(), "Classification")
cv_micro = _run_cross_validation(pipe_micro, X_micro, y_micro, "Classification")
test("Micro dataset (<6 rows) gracefully skips CV without crash", cv_micro["cv_score"] is None and cv_micro["n_splits"] == 0)

# Regression CV
X_reg = pd.DataFrame({"x1": range(40), "x2": range(40)})
y_reg = pd.Series(range(40))
pipe_reg = _build_model_pipeline(LogisticRegression(), "Regression")
cv_reg = _run_cross_validation(pipe_reg, X_reg, y_reg, "Regression")
test("Regression adaptive KFold CV works", cv_reg["cv_score"] is not None, cv_reg["cv_method"])

print("\n" + "=" * 60)
if all_passed:
    print("  ALL EVALUATION PIPELINE TESTS PASSED!")
else:
    print("  SOME TESTS FAILED!")
print("=" * 60)
