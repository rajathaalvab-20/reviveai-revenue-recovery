import os
import json
import joblib
import numpy as np
import pandas as pd

from scipy.special import expit
from scipy.optimize import minimize
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import (
    roc_auc_score,
    average_precision_score,
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    brier_score_loss,
    log_loss
)

from feature_engineering import create_features, FEATURES


# ============================================================
# REVIVEAI - PROBABILITY CALIBRATION V4
# ============================================================
# TRAIN       -> base model
# VALIDATION  -> calibration + method selection
# TEST        -> final untouched evaluation
#
# Calibration:
#   1. Base model
#   2. Platt / Sigmoid
#   3. Isotonic
#
# Test data is NEVER used for calibration fitting or selection.
# ============================================================

ROOT_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)

TRAIN_FILE = os.path.join(ROOT_DIR, "data", "splits", "train.csv")
VAL_FILE = os.path.join(ROOT_DIR, "data", "splits", "validation.csv")
TEST_FILE = os.path.join(ROOT_DIR, "data", "splits", "test.csv")

OUTPUT_DIR = os.path.join(
    ROOT_DIR, "src", "risk_model", "saved_models"
)

EVALUATION_DIR = os.path.join(
    ROOT_DIR, "src", "risk_model", "evaluation"
)

MODEL_PATH = os.path.join(
    OUTPUT_DIR, "recovery_risk_model.joblib"
)

CALIBRATED_MODEL_PATH = os.path.join(
    OUTPUT_DIR, "calibrated_recovery_risk_model.joblib"
)

METRICS_PATH = os.path.join(
    OUTPUT_DIR, "calibration_metrics.json"
)

PROBABILITY_PATH = os.path.join(
    EVALUATION_DIR, "calibration_predictions.csv"
)

TARGET = "actual_recovery"
THRESHOLD = 0.50
SEED = 42

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(EVALUATION_DIR, exist_ok=True)

print("=" * 80)
print("REVIVEAI - PROBABILITY CALIBRATION V4")
print("=" * 80)


# ============================================================
# 1. DATA VALIDATION
# ============================================================

def load_dataset(path, name):
    if not os.path.exists(path):
        raise FileNotFoundError(f"{name} dataset not found: {path}")

    df = pd.read_csv(path)

    if df.empty:
        raise ValueError(f"{name} dataset is empty.")

    if TARGET not in df.columns:
        raise ValueError(
            f"Target '{TARGET}' missing from {name} dataset."
        )

    if df[TARGET].isna().any():
        raise ValueError(
            f"Target '{TARGET}' contains NaN values in {name} dataset."
        )

    values = set(df[TARGET].unique())

    if not values.issubset({0, 1}):
        raise ValueError(
            f"{name} target must contain only 0/1 values. Found: {values}"
        )

    return df


print("\nLoading datasets...")

train_df = load_dataset(TRAIN_FILE, "Training")
val_df = load_dataset(VAL_FILE, "Validation")
test_df = load_dataset(TEST_FILE, "Test")

print(f"Training transactions   : {len(train_df):,}")
print(f"Validation transactions : {len(val_df):,}")
print(f"Test transactions       : {len(test_df):,}")


# ============================================================
# 2. FEATURE ENGINEERING
# ============================================================

print("\nApplying shared feature engineering...")

train_features = create_features(train_df)
val_features = create_features(val_df)
test_features = create_features(test_df)

missing = [
    feature for feature in FEATURES
    if feature not in train_features.columns
    or feature not in val_features.columns
    or feature not in test_features.columns
]

if missing:
    raise RuntimeError(
        "Required engineered features are missing: "
        + ", ".join(missing)
    )

X_train = train_features[FEATURES]
X_val = val_features[FEATURES]
X_test = test_features[FEATURES]

y_train = train_df[TARGET].astype(int).to_numpy()
y_val = val_df[TARGET].astype(int).to_numpy()
y_test = test_df[TARGET].astype(int).to_numpy()

print(f"✓ Features generated: {len(FEATURES)}")


# ============================================================
# 3. LOAD BASE MODEL
# ============================================================

print("\nLoading trained risk model...")

if not os.path.exists(MODEL_PATH):
    raise FileNotFoundError(
        f"Base model not found: {MODEL_PATH}"
    )

base_model = joblib.load(MODEL_PATH)

if not hasattr(base_model, "predict_proba"):
    raise TypeError(
        "Loaded base model does not support predict_proba()."
    )

print("✓ Base model loaded")


# ============================================================
# 4. PROBABILITY HELPERS
# ============================================================

def validate_probabilities(name, probabilities):
    probabilities = np.asarray(probabilities)

    if len(probabilities) == 0:
        raise ValueError(f"{name} probabilities are empty.")

    if not np.isfinite(probabilities).all():
        raise ValueError(
            f"{name} probabilities contain NaN or infinite values."
        )

    if np.any(probabilities < 0) or np.any(probabilities > 1):
        raise ValueError(
            f"{name} probabilities outside [0, 1]."
        )


def get_probabilities(model, X, name):
    probabilities = model.predict_proba(X)

    if probabilities.ndim != 2 or probabilities.shape[1] != 2:
        raise ValueError(
            f"{name} must return binary probability predictions."
        )

    probabilities = np.asarray(
        probabilities[:, 1],
        dtype=float
    )

    probabilities = np.clip(
        probabilities,
        1e-7,
        1 - 1e-7
    )

    validate_probabilities(name, probabilities)
    return probabilities


# ============================================================
# 5. BASE MODEL PROBABILITIES
# ============================================================

print("\nGenerating validation probabilities...")

val_base_probability = get_probabilities(
    base_model,
    X_val,
    "Validation base"
)

print("✓ Validation probabilities generated")

print("\nGenerating test base probabilities...")

test_base_probability = get_probabilities(
    base_model,
    X_test,
    "Test base"
)

print("✓ Test base probabilities generated")


# ============================================================
# 6. PLATT / SIGMOID CALIBRATION
# ============================================================

def logit(probabilities):
    probabilities = np.clip(
        probabilities,
        1e-7,
        1 - 1e-7
    )
    return np.log(
        probabilities / (1 - probabilities)
    )


def fit_platt_scaler(probabilities, targets):
    logits = logit(probabilities)

    def objective(params):
        a, b = params
        calibrated = expit(a * logits + b)
        return log_loss(targets, calibrated)

    result = minimize(
        objective,
        x0=np.array([1.0, 0.0]),
        method="L-BFGS-B",
        bounds=[(-20.0, 20.0), (-20.0, 20.0)]
    )

    if not result.success:
        raise RuntimeError(
            "Platt calibration failed: "
            + str(result.message)
        )

    return float(result.x[0]), float(result.x[1])


def apply_platt(probabilities, a, b):
    return expit(
        a * logit(probabilities) + b
    )


print("\nFitting Platt / sigmoid calibration...")

platt_a, platt_b = fit_platt_scaler(
    val_base_probability,
    y_val
)

val_sigmoid_probability = apply_platt(
    val_base_probability,
    platt_a,
    platt_b
)

test_sigmoid_probability = apply_platt(
    test_base_probability,
    platt_a,
    platt_b
)

validate_probabilities(
    "Validation sigmoid",
    val_sigmoid_probability
)

validate_probabilities(
    "Test sigmoid",
    test_sigmoid_probability
)

print(
    f"✓ Platt parameters: "
    f"a={platt_a:.6f}, b={platt_b:.6f}"
)


# ============================================================
# 7. ISOTONIC CALIBRATION
# ============================================================

print("\nFitting isotonic calibration...")

isotonic_model = IsotonicRegression(
    y_min=0.0,
    y_max=1.0,
    out_of_bounds="clip"
)

isotonic_model.fit(
    val_base_probability,
    y_val
)

val_isotonic_probability = isotonic_model.predict(
    val_base_probability
)

test_isotonic_probability = isotonic_model.predict(
    test_base_probability
)

validate_probabilities(
    "Validation isotonic",
    val_isotonic_probability
)

validate_probabilities(
    "Test isotonic",
    test_isotonic_probability
)

print("✓ Isotonic calibration fitted")


# ============================================================
# 8. EVALUATION
# ============================================================

def evaluate_probability_model(
    name,
    probabilities,
    y_true
):
    probabilities = np.asarray(probabilities, dtype=float)
    y_true = np.asarray(y_true, dtype=int)

    if len(probabilities) != len(y_true):
        raise ValueError(
            f"{name}: prediction count does not match target count."
        )

    predictions = (
        probabilities >= THRESHOLD
    ).astype(int)

    metrics = {
        "roc_auc": roc_auc_score(
            y_true, probabilities
        ),
        "pr_auc": average_precision_score(
            y_true, probabilities
        ),
        "accuracy": accuracy_score(
            y_true, predictions
        ),
        "precision": precision_score(
            y_true, predictions, zero_division=0
        ),
        "recall": recall_score(
            y_true, predictions, zero_division=0
        ),
        "f1": f1_score(
            y_true, predictions, zero_division=0
        ),
        "brier_score": brier_score_loss(
            y_true, probabilities
        ),
        "log_loss": log_loss(
            y_true, probabilities
        )
    }

    print("\n" + "-" * 80)
    print(name)
    print("-" * 80)

    for metric, value in metrics.items():
        print(f"{metric:15s}: {value:.6f}")

    return metrics


# ============================================================
# 9. VALIDATION EVALUATION
# ============================================================

print("\n" + "=" * 80)
print("VALIDATION CALIBRATION EVALUATION")
print("=" * 80)

val_base_metrics = evaluate_probability_model(
    "VALIDATION - BASE MODEL",
    val_base_probability,
    y_val
)

val_sigmoid_metrics = evaluate_probability_model(
    "VALIDATION - SIGMOID",
    val_sigmoid_probability,
    y_val
)

val_isotonic_metrics = evaluate_probability_model(
    "VALIDATION - ISOTONIC",
    val_isotonic_probability,
    y_val
)

validation_candidates = {
    "base": val_base_metrics,
    "sigmoid": val_sigmoid_metrics,
    "isotonic": val_isotonic_metrics
}


# ============================================================
# 10. SELECT CALIBRATION METHOD
# ============================================================

best_method = min(
    validation_candidates,
    key=lambda name: (
        validation_candidates[name]["brier_score"],
        validation_candidates[name]["log_loss"]
    )
)

print(
    f"\nSelected calibration method: {best_method}"
)


# ============================================================
# 11. FINAL TEST EVALUATION
# ============================================================

print("\n" + "=" * 80)
print("FINAL TEST SET CALIBRATION COMPARISON")
print("=" * 80)

base_metrics = evaluate_probability_model(
    "BASE MODEL",
    test_base_probability,
    y_test
)

sigmoid_metrics = evaluate_probability_model(
    "PLATT / SIGMOID CALIBRATION",
    test_sigmoid_probability,
    y_test
)

isotonic_metrics = evaluate_probability_model(
    "ISOTONIC CALIBRATION",
    test_isotonic_probability,
    y_test
)

test_candidates = {
    "base": base_metrics,
    "sigmoid": sigmoid_metrics,
    "isotonic": isotonic_metrics
}

comparison = pd.DataFrame(test_candidates).T

print("\n" + "=" * 80)
print("CALIBRATION MODEL COMPARISON")
print("=" * 80)

print(comparison.round(6).to_string())


# ============================================================
# 12. SELECT FINAL PROBABILITY ARRAY
# ============================================================

probability_map = {
    "base": test_base_probability,
    "sigmoid": test_sigmoid_probability,
    "isotonic": test_isotonic_probability
}

selected_test_probability = probability_map[best_method]


# ============================================================
# 13. SAVE CALIBRATION ARTIFACT
# ============================================================

calibration_artifact = {
    "model_version": "V4",
    "base_model_path": MODEL_PATH,
    "calibration_method": best_method,
    "platt_parameters": {
        "a": platt_a,
        "b": platt_b
    },
    "isotonic_model": isotonic_model,
    "features": FEATURES,
    "target": TARGET,
    "threshold": THRESHOLD,
    "seed": SEED,
    "data_policy": {
        "training": "base_model_training",
        "validation": "calibration_fitting_and_selection",
        "test": "final_evaluation_only"
    }
}

joblib.dump(
    calibration_artifact,
    CALIBRATED_MODEL_PATH
)

print(
    "\nCalibration artifact saved:"
    f"\n  {CALIBRATED_MODEL_PATH}"
)


# ============================================================
# 14. SAVE TEST PREDICTIONS
# ============================================================

output_columns = [
    column for column in [
        "transaction_id",
        "customer_id",
        "amount",
        "payment_method",
        "customer_type",
        "failure_code",
        "failure_type",
        TARGET
    ]
    if column in test_df.columns
]

probability_output = test_df[
    output_columns
].copy()

probability_output["base_probability"] = (
    test_base_probability
)

probability_output["sigmoid_probability"] = (
    test_sigmoid_probability
)

probability_output["isotonic_probability"] = (
    test_isotonic_probability
)

probability_output["selected_probability"] = (
    selected_test_probability
)

probability_output["selected_prediction"] = (
    selected_test_probability >= THRESHOLD
).astype(int)

probability_output.to_csv(
    PROBABILITY_PATH,
    index=False
)

print(
    "\nCalibration predictions saved:"
    f"\n  {PROBABILITY_PATH}"
)


# ============================================================
# 15. SAVE METRICS
# ============================================================

metrics_output = {
    "model_version": "V4",
    "selected_method": best_method,
    "selection_rule": {
        "primary": "validation_brier_score",
        "secondary": "validation_log_loss",
        "test_used_for_selection": False
    },
    "validation_metrics": validation_candidates,
    "test_metrics": test_candidates,
    "platt_parameters": {
        "a": platt_a,
        "b": platt_b
    },
    "data_split": {
        "training_rows": len(train_df),
        "validation_rows": len(val_df),
        "test_rows": len(test_df)
    },
    "features": FEATURES,
    "target": TARGET,
    "threshold": THRESHOLD,
    "seed": SEED
}

with open(METRICS_PATH, "w") as f:
    json.dump(
        metrics_output,
        f,
        indent=4
    )

print(
    "\nCalibration metrics saved:"
    f"\n  {METRICS_PATH}"
)


# ============================================================
# 16. FINAL INTEGRITY CHECKS
# ============================================================

print("\n" + "=" * 80)
print("CALIBRATION INTEGRITY CHECKS")
print("=" * 80)

assert len(test_base_probability) == len(y_test)
assert len(test_sigmoid_probability) == len(y_test)
assert len(test_isotonic_probability) == len(y_test)
assert len(selected_test_probability) == len(y_test)

assert np.isfinite(test_base_probability).all()
assert np.isfinite(test_sigmoid_probability).all()
assert np.isfinite(test_isotonic_probability).all()
assert np.isfinite(selected_test_probability).all()

assert (
    (test_base_probability >= 0).all()
    and (test_base_probability <= 1).all()
)

assert (
    (test_sigmoid_probability >= 0).all()
    and (test_sigmoid_probability <= 1).all()
)

assert (
    (test_isotonic_probability >= 0).all()
    and (test_isotonic_probability <= 1).all()
)

assert (
    (selected_test_probability >= 0).all()
    and (selected_test_probability <= 1).all()
)

assert not probability_output[
    "selected_probability"
].isna().any()

assert os.path.exists(CALIBRATED_MODEL_PATH)
assert os.path.exists(METRICS_PATH)
assert os.path.exists(PROBABILITY_PATH)

print("✓ Test prediction count matches test dataset")
print("✓ No NaN probabilities")
print("✓ No infinite probabilities")
print("✓ All probabilities within [0, 1]")
print("✓ Test set was not used for calibration fitting")
print("✓ Calibration method selected using validation data")
print("✓ Shared feature engineering used")
print("✓ Calibration artifact saved successfully")
print("✓ Metrics artifact saved successfully")
print("✓ Prediction artifact saved successfully")


# ============================================================
# 17. FINAL SUMMARY
# ============================================================

print("\n" + "=" * 80)
print("REVIVEAI PROBABILITY CALIBRATION COMPLETE")
print("=" * 80)

print(f"\nSelected method : {best_method}")

print(
    "\nValidation Brier:"
    f" {validation_candidates[best_method]['brier_score']:.6f}"
)

print(
    "Test Brier:"
    f" {test_candidates[best_method]['brier_score']:.6f}"
)

print(
    "\nTest ROC-AUC:"
    f" {test_candidates[best_method]['roc_auc']:.6f}"
)

print(
    "Test PR-AUC:"
    f" {test_candidates[best_method]['pr_auc']:.6f}"
)

print(
    "Test Accuracy:"
    f" {test_candidates[best_method]['accuracy']:.6f}"
)

print(
    "Test F1:"
    f" {test_candidates[best_method]['f1']:.6f}"
)

print("\nArtifacts:")
print(f"  Model      : {CALIBRATED_MODEL_PATH}")
print(f"  Metrics    : {METRICS_PATH}")
print(f"  Predictions: {PROBABILITY_PATH}")

print("\nData isolation:")
print("  TRAIN      -> base model")
print("  VALIDATION -> calibration + selection")
print("  TEST       -> final evaluation only")

print("\n" + "=" * 80)

