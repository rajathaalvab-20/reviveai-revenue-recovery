import os
import json
import joblib
import numpy as np
import pandas as pd

from feature_engineering import create_features, FEATURES

MODEL_PATH = os.path.join(
    os.path.dirname(__file__),
    "saved_models",
    "calibrated_recovery_risk_model.joblib"
)

REQUIRED_INPUTS = [
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

DEFAULT_THRESHOLD = 0.50


def validate_input(data):
    if not isinstance(data, dict):
        raise TypeError("Payment input must be a dictionary.")

    missing = [column for column in REQUIRED_INPUTS if column not in data]
    if missing:
        raise ValueError("Missing required fields: " + ", ".join(missing))

    numeric_fields = [
        "amount",
        "customer_age_days",
        "previous_transactions",
        "previous_success_rate",
        "attempt_count",
        "time_since_failure_min",
        "hour_of_day",
        "is_weekend"
    ]

    for field in numeric_fields:
        value = data[field]
        if not isinstance(value, (int, float, np.integer, np.floating)):
            raise TypeError(f"{field} must be numeric.")
        if not np.isfinite(value):
            raise ValueError(f"{field} must be finite.")

    if data["amount"] < 0:
        raise ValueError("amount cannot be negative.")

    if data["customer_age_days"] < 0:
        raise ValueError("customer_age_days cannot be negative.")

    if data["previous_transactions"] < 0:
        raise ValueError("previous_transactions cannot be negative.")

    if not 0 <= data["previous_success_rate"] <= 1:
        raise ValueError("previous_success_rate must be between 0 and 1.")

    if data["attempt_count"] < 0:
        raise ValueError("attempt_count cannot be negative.")

    if data["time_since_failure_min"] < 0:
        raise ValueError("time_since_failure_min cannot be negative.")

    if not 0 <= data["hour_of_day"] <= 23:
        raise ValueError("hour_of_day must be between 0 and 23.")

    if data["is_weekend"] not in (0, 1):
        raise ValueError("is_weekend must be 0 or 1.")


def load_model():
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(
            "Calibrated model not found: " + MODEL_PATH
        )

    artifact = joblib.load(MODEL_PATH)

    required_artifact_keys = [
        "model_version",
        "calibration_method",
        "features",
        "target"
    ]

    missing = [
        key for key in required_artifact_keys
        if key not in artifact
    ]

    if missing:
        raise RuntimeError(
            "Invalid calibration artifact. Missing: "
            + ", ".join(missing)
        )

    if artifact["features"] != FEATURES:
        raise RuntimeError(
            "Model feature schema does not match feature_engineering.py."
        )

    if artifact["calibration_method"] not in {
        "base",
        "sigmoid",
        "isotonic"
    }:
        raise RuntimeError("Unsupported calibration method.")

    return artifact


def apply_calibration(artifact, base_probability):
    method = artifact["calibration_method"]

    if method == "base":
        probability = base_probability

    elif method == "sigmoid":
        parameters = artifact["platt_parameters"]
        a = parameters["a"]
        b = parameters["b"]
        probability = 1 / (
            1 + np.exp(
                -(a * np.log(
                    base_probability / (1 - base_probability)
                ) + b)
            )
        )

    else:
        probability = artifact["isotonic_model"].predict(
            [base_probability]
        )[0]

    return float(np.clip(probability, 0.0, 1.0))


def classify_risk(probability):
    if probability >= 0.80:
        return "HIGH"

    if probability >= 0.50:
        return "MEDIUM"

    return "LOW"


def detect_risk(payment):
    validate_input(payment)

    artifact = load_model()

    input_df = pd.DataFrame([payment])
    feature_df = create_features(input_df)
    model_input = feature_df[FEATURES]

    base_model = artifact.get("base_model")

    if base_model is None:
        base_model_path = artifact.get("base_model_path")

        if not base_model_path:
            raise RuntimeError(
                "Base model information missing from calibration artifact."
            )

        # Convert Windows paths to a Docker-compatible path.
        base_model_path = str(base_model_path).replace("\\", "/")

        # If the artifact contains an absolute Windows path,
        # use the model location inside the project instead.
        marker = "saved_models/"

        if marker in base_model_path:
            relative_model_path = base_model_path.split(marker, 1)[1]

            base_model_path = os.path.join(
                os.path.dirname(__file__),
                "saved_models",
                relative_model_path
            )

        elif not os.path.isabs(base_model_path):
            project_root = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "..")
            )

            base_model_path = os.path.join(
                project_root,
                base_model_path
            )

        if not os.path.exists(base_model_path):
            raise FileNotFoundError(
                "Base risk model not found: " + base_model_path
            )

        base_model = joblib.load(base_model_path)

    if not hasattr(base_model, "predict_proba"):
        raise TypeError(
            "Base risk model does not support predict_proba()."
        )

    base_probability = float(
        base_model.predict_proba(model_input)[0, 1]
    )

    if not np.isfinite(base_probability):
        raise ValueError("Base probability is invalid.")

    base_probability = float(
        np.clip(base_probability, 1e-7, 1 - 1e-7)
    )

    probability = apply_calibration(
        artifact,
        base_probability
    )

    if not np.isfinite(probability):
        raise ValueError("Calibrated probability is invalid.")

    threshold = float(
        artifact.get(
            "threshold",
            DEFAULT_THRESHOLD
        )
    )

    risk_level = classify_risk(probability)

    return {
        "status": "success",
        "transaction_id": payment.get("transaction_id"),
        "recovery_probability": round(probability, 6),
        "base_probability": round(base_probability, 6),
        "risk_level": risk_level,
        "recovery_likely": probability >= threshold,
        "threshold": threshold,
        "calibration_method": artifact["calibration_method"],
        "model_version": artifact["model_version"]
    }


def detect_risk_json(payment):
    return json.dumps(
        detect_risk(payment),
        indent=4
    )


if __name__ == "__main__":
    sample_payment = {
        "transaction_id": "TXN_DEMO_001",
        "amount": 5000,
        "payment_method": "CARD",
        "customer_type": "RETURNING",
        "customer_age_days": 240,
        "previous_transactions": 25,
        "previous_success_rate": 0.92,
        "failure_code": "BANK_TIMEOUT",
        "failure_type": "TRANSIENT",
        "attempt_count": 1,
        "time_since_failure_min": 10,
        "hour_of_day": 14,
        "is_weekend": 0
    }

    print(json.dumps(
        detect_risk(sample_payment),
        indent=4
    ))
