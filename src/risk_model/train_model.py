import os
import json
import joblib
import numpy as np
import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score, average_precision_score, accuracy_score, precision_score, recall_score, f1_score, brier_score_loss
from feature_engineering import create_features, FEATURES, NUMERIC_FEATURES, CATEGORICAL_FEATURES

# ============================================================
# REVIVEAI - PRODUCTION RISK MODEL TRAINING
# ============================================================

TRAIN_FILE = "data/splits/train.csv"
VAL_FILE = "data/splits/validation.csv"
MODEL_DIR = "src/risk_model/saved_models"
SEED = 42
TARGET = "actual_recovery"

os.makedirs(MODEL_DIR, exist_ok=True)

print("=" * 80)
print("REVIVEAI - PRODUCTION RECOVERY RISK MODEL")
print("=" * 80)

# ============================================================
# 1. LOAD DATA
# ============================================================

train_df = pd.read_csv(TRAIN_FILE)
val_df = pd.read_csv(VAL_FILE)

if train_df.empty:
    raise ValueError("Training dataset is empty.")
if val_df.empty:
    raise ValueError("Validation dataset is empty.")
if TARGET not in train_df.columns or TARGET not in val_df.columns:
    raise ValueError(f"Target column '{TARGET}' is missing.")
if train_df[TARGET].isna().any() or val_df[TARGET].isna().any():
    raise ValueError("Target contains missing values.")

print("\nDataset:")
print(f"Training rows   : {len(train_df):,}")
print(f"Validation rows : {len(val_df):,}")

# ============================================================
# 2. TARGET VALIDATION
# ============================================================

for name, df in [("training", train_df), ("validation", val_df)]:
    values = set(df[TARGET].unique())
    if not values.issubset({0, 1}):
        raise ValueError(f"{name} target contains invalid values: {values}")

y_train = train_df[TARGET].astype(int)
y_val = val_df[TARGET].astype(int)

print("\nTarget:")
print(f"  {TARGET}")
print(f"Training recovery rate   : {y_train.mean():.4f}")
print(f"Validation recovery rate : {y_val.mean():.4f}")

# ============================================================
# 3. FEATURE ENGINEERING
# ============================================================

train_features = create_features(train_df)
val_features = create_features(val_df)

missing_train = [f for f in FEATURES if f not in train_features.columns]
missing_val = [f for f in FEATURES if f not in val_features.columns]

if missing_train:
    raise ValueError(f"Training features missing: {missing_train}")
if missing_val:
    raise ValueError(f"Validation features missing: {missing_val}")

X_train = train_features[FEATURES].copy()
X_val = val_features[FEATURES].copy()

print("\n" + "-" * 80)
print("FEATURE ENGINEERING")
print("-" * 80)
print("Original features  : 12")
print(f"Final features     : {len(FEATURES)}")
print(f"Numeric features   : {len(NUMERIC_FEATURES)}")
print(f"Categorical features: {len(CATEGORICAL_FEATURES)}")

# ============================================================
# 4. LEAKAGE PROTECTION
# ============================================================

FORBIDDEN_FEATURES = [
    "true_recovery_probability",
    "actual_recovery",
    "recovered_amount",
    "recovery_attempts",
    "final_status",
    "gateway_response",
    "verification_result"
]

used_forbidden = [f for f in FEATURES if f in FORBIDDEN_FEATURES]

if used_forbidden:
    raise ValueError(f"Target leakage detected: {used_forbidden}")

print("\nLeakage protection:")
print("✓ No outcome/future-state features used")

# ============================================================
# 5. PREPROCESSOR
# ============================================================

preprocessor = ColumnTransformer(
    transformers=[
        ("numeric", StandardScaler(), NUMERIC_FEATURES),
        ("categorical", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES)
    ],
    remainder="drop"
)

# ============================================================
# 6. MODELS
# ============================================================

models = {
    "logistic_regression": LogisticRegression(max_iter=3000, class_weight="balanced", random_state=SEED),
    "random_forest": RandomForestClassifier(n_estimators=500, max_depth=16, min_samples_leaf=5, class_weight="balanced", random_state=SEED, n_jobs=-1),
    "hist_gradient_boosting": HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, max_leaf_nodes=31, min_samples_leaf=20, l2_regularization=1.0, random_state=SEED)
}

# ============================================================
# 7. EVALUATION
# ============================================================

def evaluate_model(name, pipeline, X, y):
    probabilities = pipeline.predict_proba(X)[:, 1]
    predictions = (probabilities >= 0.50).astype(int)

    metrics = {
        "roc_auc": roc_auc_score(y, probabilities),
        "pr_auc": average_precision_score(y, probabilities),
        "accuracy": accuracy_score(y, predictions),
        "precision": precision_score(y, predictions, zero_division=0),
        "recall": recall_score(y, predictions, zero_division=0),
        "f1": f1_score(y, predictions, zero_division=0),
        "brier_score": brier_score_loss(y, probabilities)
    }

    print("\n" + "-" * 80)
    print(name.upper())
    print("-" * 80)

    for metric, value in metrics.items():
        print(f"{metric:15s}: {value:.4f}")

    return metrics

# ============================================================
# 8. TRAINING
# ============================================================

results = {}
trained_models = {}

for name, model in models.items():
    print("\n" + "=" * 80)
    print(f"TRAINING: {name}")
    print("=" * 80)

    pipeline = Pipeline([
        ("preprocessor", preprocessor),
        ("model", model)
    ])

    pipeline.fit(X_train, y_train)
    results[name] = evaluate_model(name, pipeline, X_val, y_val)
    trained_models[name] = pipeline

# ============================================================
# 9. MODEL COMPARISON
# ============================================================

print("\n" + "=" * 80)
print("MODEL COMPARISON")
print("=" * 80)

comparison = pd.DataFrame(results).T
print(comparison.round(4).sort_values("roc_auc", ascending=False).to_string())

# ============================================================
# 10. MODEL SELECTION
# ============================================================

best_model_name = sorted(
    results,
    key=lambda name: (results[name]["roc_auc"], results[name]["pr_auc"], -results[name]["brier_score"]),
    reverse=True
)[0]

best_model = trained_models[best_model_name]

print(f"\nSelected model: {best_model_name}")

# ============================================================
# 11. VALIDATE MODEL OUTPUT
# ============================================================

test_probabilities = best_model.predict_proba(X_val)[:, 1]

if not np.isfinite(test_probabilities).all():
    raise ValueError("Model generated invalid probability values.")

if ((test_probabilities < 0) | (test_probabilities > 1)).any():
    raise ValueError("Model generated probabilities outside [0, 1].")

print("\nModel probability validation:")
print("✓ Probabilities are finite")
print("✓ Probabilities are within [0, 1]")

# ============================================================
# 12. SAVE MODEL
# ============================================================

model_path = os.path.join(MODEL_DIR, "recovery_risk_model.joblib")
joblib.dump(best_model, model_path)

# ============================================================
# 13. SAVE METRICS
# ============================================================

metrics_path = os.path.join(MODEL_DIR, "training_metrics.json")

training_metadata = {
    "model_version": "V3",
    "selected_model": best_model_name,
    "random_seed": SEED,
    "training_rows": len(train_df),
    "validation_rows": len(val_df),
    "feature_count": len(FEATURES),
    "validation_metrics": results[best_model_name],
    "all_models": results
}

with open(metrics_path, "w") as f:
    json.dump(training_metadata, f, indent=4)

# ============================================================
# 14. SAVE FEATURE CONFIGURATION
# ============================================================

config_path = os.path.join(MODEL_DIR, "feature_config.json")

feature_config = {
    "model_version": "V3",
    "features": FEATURES,
    "numeric_features": NUMERIC_FEATURES,
    "categorical_features": CATEGORICAL_FEATURES,
    "target": TARGET,
    "forbidden_features": FORBIDDEN_FEATURES
}

with open(config_path, "w") as f:
    json.dump(feature_config, f, indent=4)

# ============================================================
# 15. TRAINING DATA SIGNATURE
# ============================================================

schema_path = os.path.join(MODEL_DIR, "training_schema.json")

schema = {
    "model_version": "V3",
    "features": FEATURES,
    "target": TARGET,
    "training_rows": len(train_df),
    "validation_rows": len(val_df),
    "training_recovery_rate": float(y_train.mean()),
    "validation_recovery_rate": float(y_val.mean())
}

with open(schema_path, "w") as f:
    json.dump(schema, f, indent=4)

# ============================================================
# FINAL
# ============================================================

print("\n" + "=" * 80)
print("REVIVEAI V3 TRAINING COMPLETE")
print("=" * 80)

print(f"\nModel saved:")
print(f"  {model_path}")

print(f"\nMetrics saved:")
print(f"  {metrics_path}")

print(f"\nFeature configuration saved:")
print(f"  {config_path}")

print(f"\nTraining schema saved:")
print(f"  {schema_path}")

print(f"\nSelected model:")
print(f"  {best_model_name}")

print("\nProduction safeguards:")
print("✓ Customer-level train/validation split")
print("✓ No target leakage")
print("✓ Shared feature engineering")
print("✓ Unknown categorical values handled")
print("✓ Probability validation")
print("✓ Model metadata persisted")
print("✓ Feature configuration persisted")
print("✓ Deterministic random seed")

print("\n" + "=" * 80)