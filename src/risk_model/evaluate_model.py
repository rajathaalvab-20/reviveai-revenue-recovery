import os
import json
import joblib
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from sklearn.metrics import (
    roc_auc_score,
    average_precision_score,
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    brier_score_loss,
    confusion_matrix,
    roc_curve,
    precision_recall_curve
)

from sklearn.calibration import calibration_curve


# ============================================================
# REVIVEAI - FINAL RISK MODEL EVALUATION
# ============================================================

TEST_FILE = "data/splits/test.csv"

MODEL_FILE = (
    "src/risk_model/saved_models/"
    "recovery_risk_model.joblib"
)

METRICS_FILE = (
    "src/risk_model/saved_models/"
    "test_metrics.json"
)

RESULTS_DIR = "src/risk_model/evaluation"

os.makedirs(RESULTS_DIR, exist_ok=True)


FEATURES = [
    "amount",
    "payment_method",
    "customer_type",
    "customer_age_days",
    "previous_transactions",
    "previous_success_rate",
    "failure_code",
    "failure_type",
    "attempt_count",
    "time_since_failure_min",
    "hour_of_day",
    "is_weekend"
]

TARGET = "actual_recovery"


# ============================================================
# 1. LOAD TEST DATA
# ============================================================

print("=" * 75)
print("REVIVEAI - FINAL TEST SET EVALUATION")
print("=" * 75)

test_df = pd.read_csv(TEST_FILE)

model = joblib.load(MODEL_FILE)

print("\nTest dataset:")
print(f"Transactions: {len(test_df):,}")


X_test = test_df[FEATURES]
y_test = test_df[TARGET]


# ============================================================
# 2. PREDICTIONS
# ============================================================

probabilities = model.predict_proba(X_test)[:, 1]

predictions = (
    probabilities >= 0.50
).astype(int)


# ============================================================
# 3. METRICS
# ============================================================

roc_auc = roc_auc_score(
    y_test,
    probabilities
)

pr_auc = average_precision_score(
    y_test,
    probabilities
)

accuracy = accuracy_score(
    y_test,
    predictions
)

precision = precision_score(
    y_test,
    predictions,
    zero_division=0
)

recall = recall_score(
    y_test,
    predictions,
    zero_division=0
)

f1 = f1_score(
    y_test,
    predictions,
    zero_division=0
)

brier = brier_score_loss(
    y_test,
    probabilities
)


# ============================================================
# 4. PRINT METRICS
# ============================================================

print("\n" + "-" * 75)
print("TEST SET METRICS")
print("-" * 75)

print(f"ROC-AUC       : {roc_auc:.4f}")
print(f"PR-AUC        : {pr_auc:.4f}")
print(f"Accuracy      : {accuracy:.4f}")
print(f"Precision     : {precision:.4f}")
print(f"Recall        : {recall:.4f}")
print(f"F1            : {f1:.4f}")
print(f"Brier Score   : {brier:.4f}")


# ============================================================
# 5. CONFUSION MATRIX
# ============================================================

cm = confusion_matrix(
    y_test,
    predictions
)

print("\n" + "-" * 75)
print("CONFUSION MATRIX")
print("-" * 75)

print(cm)

print(f"\nTrue Negative  : {cm[0, 0]}")
print(f"False Positive : {cm[0, 1]}")
print(f"False Negative : {cm[1, 0]}")
print(f"True Positive  : {cm[1, 1]}")


# ============================================================
# 6. ROC CURVE
# ============================================================

fpr, tpr, _ = roc_curve(
    y_test,
    probabilities
)

plt.figure(figsize=(8, 6))

plt.plot(
    fpr,
    tpr,
    label=f"ROC-AUC = {roc_auc:.4f}"
)

plt.plot(
    [0, 1],
    [0, 1],
    linestyle="--"
)

plt.xlabel("False Positive Rate")
plt.ylabel("True Positive Rate")
plt.title("ReviveAI - ROC Curve")
plt.legend()

plt.tight_layout()

roc_file = os.path.join(
    RESULTS_DIR,
    "roc_curve.png"
)

plt.savefig(
    roc_file,
    dpi=200
)

plt.close()


# ============================================================
# 7. PRECISION-RECALL CURVE
# ============================================================

precision_curve, recall_curve, _ = (
    precision_recall_curve(
        y_test,
        probabilities
    )
)

plt.figure(figsize=(8, 6))

plt.plot(
    recall_curve,
    precision_curve,
    label=f"PR-AUC = {pr_auc:.4f}"
)

plt.xlabel("Recall")
plt.ylabel("Precision")
plt.title("ReviveAI - Precision Recall Curve")
plt.legend()

plt.tight_layout()

pr_file = os.path.join(
    RESULTS_DIR,
    "precision_recall_curve.png"
)

plt.savefig(
    pr_file,
    dpi=200
)

plt.close()


# ============================================================
# 8. CALIBRATION CURVE
# ============================================================

fraction_positive, mean_predicted = (
    calibration_curve(
        y_test,
        probabilities,
        n_bins=10,
        strategy="uniform"
    )
)

plt.figure(figsize=(8, 6))

plt.plot(
    mean_predicted,
    fraction_positive,
    marker="o",
    label="ReviveAI"
)

plt.plot(
    [0, 1],
    [0, 1],
    linestyle="--",
    label="Perfect calibration"
)

plt.xlabel("Mean predicted probability")
plt.ylabel("Actual recovery rate")
plt.title("ReviveAI - Calibration Curve")
plt.legend()

plt.tight_layout()

calibration_file = os.path.join(
    RESULTS_DIR,
    "calibration_curve.png"
)

plt.savefig(
    calibration_file,
    dpi=200
)

plt.close()


# ============================================================
# 9. PROBABILITY BUCKET ANALYSIS
# ============================================================

print("\n" + "-" * 75)
print("PROBABILITY CALIBRATION")
print("-" * 75)

evaluation_df = pd.DataFrame({
    "probability": probabilities,
    "actual_recovery": y_test.values,
    "amount": test_df["amount"].values
})

evaluation_df["bucket"] = pd.cut(
    evaluation_df["probability"],
    bins=[
        0,
        0.2,
        0.4,
        0.6,
        0.8,
        1.0
    ],
    labels=[
        "0-20%",
        "20-40%",
        "40-60%",
        "60-80%",
        "80-100%"
    ],
    include_lowest=True
)

calibration_table = (
    evaluation_df
    .groupby(
        "bucket",
        observed=False
    )
    .agg(
        transactions=("actual_recovery", "count"),
        predicted_probability=("probability", "mean"),
        actual_recovery_rate=("actual_recovery", "mean"),
        revenue_at_risk=("amount", "sum")
    )
)

calibration_table["actual_recovery_rate"] *= 100
calibration_table["predicted_probability"] *= 100

print(
    calibration_table.round(2).to_string()
)


# ============================================================
# 10. REVENUE ANALYSIS
# ============================================================

print("\n" + "-" * 75)
print("REVENUE ANALYSIS")
print("-" * 75)

total_revenue_at_risk = test_df["amount"].sum()

actual_recovered_revenue = (
    test_df.loc[
        test_df[TARGET] == 1,
        "amount"
    ].sum()
)

expected_recovery = (
    test_df["amount"] * probabilities
).sum()

print(
    f"Revenue at risk       : ₹{total_revenue_at_risk:,.2f}"
)

print(
    f"Actual recovered      : ₹{actual_recovered_revenue:,.2f}"
)

print(
    f"Model expected        : ₹{expected_recovery:,.2f}"
)


# ============================================================
# 11. TOP RECOVERY OPPORTUNITIES
# ============================================================

evaluation_df["expected_recovery"] = (
    evaluation_df["amount"]
    * evaluation_df["probability"]
)

top_cases = (
    evaluation_df
    .sort_values(
        "expected_recovery",
        ascending=False
    )
    .head(10)
)

print("\n" + "-" * 75)
print("TOP 10 EXPECTED RECOVERY OPPORTUNITIES")
print("-" * 75)

print(
    top_cases[
        [
            "amount",
            "probability",
            "expected_recovery",
            "actual_recovery"
        ]
    ]
    .round(2)
    .to_string(index=False)
)


# ============================================================
# 12. SAVE METRICS
# ============================================================

metrics = {
    "roc_auc": float(roc_auc),
    "pr_auc": float(pr_auc),
    "accuracy": float(accuracy),
    "precision": float(precision),
    "recall": float(recall),
    "f1": float(f1),
    "brier_score": float(brier),

    "test_transactions": int(len(test_df)),

    "total_revenue_at_risk": float(
        total_revenue_at_risk
    ),

    "actual_recovered_revenue": float(
        actual_recovered_revenue
    ),

    "model_expected_recovery": float(
        expected_recovery
    )
}

with open(METRICS_FILE, "w") as f:
    json.dump(
        metrics,
        f,
        indent=4
    )


# ============================================================
# FINAL
# ============================================================

print("\n" + "=" * 75)
print("FINAL TEST EVALUATION COMPLETE")
print("=" * 75)

print("\nSaved:")
print(f"  {METRICS_FILE}")
print(f"  {roc_file}")
print(f"  {pr_file}")
print(f"  {calibration_file}")

print("\nIMPORTANT:")
print("The test set was NOT used during model training.")

print("\n" + "=" * 75)