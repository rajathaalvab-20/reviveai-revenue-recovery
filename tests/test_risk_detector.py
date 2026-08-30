import json
import os

import joblib
import numpy as np
import pytest

import risk_detector
from risk_detector import (
    detect_risk,
    detect_risk_json,
    validate_input,
    load_model,
    apply_calibration,
    classify_risk,
)


VALID_PAYMENT = {
    "transaction_id": "TEST_RISK_001",
    "amount": 5000.0,
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
    "is_weekend": 0,
}


# ============================================================
# VALIDATION TESTS
# ============================================================

def test_validate_input_valid():
    validate_input(VALID_PAYMENT)


def test_validate_input_not_dictionary():
    with pytest.raises(TypeError, match="Payment input must be a dictionary"):
        validate_input([])


def test_validate_input_missing_multiple_fields():
    payment = VALID_PAYMENT.copy()
    del payment["amount"]
    del payment["payment_method"]

    with pytest.raises(ValueError, match="Missing required fields"):
        validate_input(payment)


@pytest.mark.parametrize(
    "field,value",
    [
        ("amount", "5000"),
        ("customer_age_days", "240"),
        ("previous_transactions", "25"),
        ("previous_success_rate", "0.92"),
        ("attempt_count", "1"),
        ("time_since_failure_min", "10"),
        ("hour_of_day", "14"),
        ("is_weekend", "0"),
    ],
)
def test_validate_input_non_numeric(field, value):
    payment = VALID_PAYMENT.copy()
    payment[field] = value

    with pytest.raises(TypeError, match=f"{field} must be numeric"):
        validate_input(payment)


@pytest.mark.parametrize(
    "field",
    [
        "amount",
        "customer_age_days",
        "previous_transactions",
        "previous_success_rate",
        "attempt_count",
        "time_since_failure_min",
        "hour_of_day",
        "is_weekend",
    ],
)
def test_validate_input_non_finite(field):
    payment = VALID_PAYMENT.copy()
    payment[field] = np.nan

    with pytest.raises(ValueError, match=f"{field} must be finite"):
        validate_input(payment)


def test_validate_input_infinite_value():
    payment = VALID_PAYMENT.copy()
    payment["amount"] = np.inf

    with pytest.raises(ValueError, match="amount must be finite"):
        validate_input(payment)


@pytest.mark.parametrize(
    "field,value,error",
    [
        ("amount", -1, "amount cannot be negative"),
        (
            "customer_age_days",
            -1,
            "customer_age_days cannot be negative",
        ),
        (
            "previous_transactions",
            -1,
            "previous_transactions cannot be negative",
        ),
        (
            "attempt_count",
            -1,
            "attempt_count cannot be negative",
        ),
        (
            "time_since_failure_min",
            -1,
            "time_since_failure_min cannot be negative",
        ),
    ],
)
def test_validate_input_negative_values(field, value, error):
    payment = VALID_PAYMENT.copy()
    payment[field] = value

    with pytest.raises(ValueError, match=error):
        validate_input(payment)


@pytest.mark.parametrize(
    "value",
    [-0.01, 1.01],
)
def test_validate_input_success_rate_out_of_range(value):
    payment = VALID_PAYMENT.copy()
    payment["previous_success_rate"] = value

    with pytest.raises(ValueError, match="previous_success_rate"):
        validate_input(payment)


@pytest.mark.parametrize(
    "value",
    [-1, 24],
)
def test_validate_input_hour_out_of_range(value):
    payment = VALID_PAYMENT.copy()
    payment["hour_of_day"] = value

    with pytest.raises(ValueError, match="hour_of_day"):
        validate_input(payment)


@pytest.mark.parametrize(
    "value",
    [-1, 2],
)
def test_validate_input_invalid_weekend_flag(value):
    payment = VALID_PAYMENT.copy()
    payment["is_weekend"] = value

    with pytest.raises(ValueError, match="is_weekend"):
        validate_input(payment)


def test_validate_input_numpy_numeric_types():
    payment = VALID_PAYMENT.copy()

    payment["amount"] = np.float64(5000)
    payment["customer_age_days"] = np.int64(240)
    payment["previous_transactions"] = np.int64(25)
    payment["previous_success_rate"] = np.float64(0.92)

    validate_input(payment)


# ============================================================
# LOAD MODEL TESTS
# ============================================================

def test_load_model_missing_file(monkeypatch, tmp_path):
    missing_model = tmp_path / "missing.joblib"

    monkeypatch.setattr(
        risk_detector,
        "MODEL_PATH",
        str(missing_model),
    )

    with pytest.raises(
        FileNotFoundError,
        match="Calibrated model not found",
    ):
        load_model()


@pytest.mark.parametrize(
    "artifact,missing_key",
    [
        (
            {
                "model_version": "1.0",
                "calibration_method": "base",
                "features": risk_detector.FEATURES,
            },
            "target",
        ),
        (
            {
                "calibration_method": "base",
                "features": risk_detector.FEATURES,
                "target": "recovery",
            },
            "model_version",
        ),
    ],
)
def test_load_model_missing_artifact_keys(
    monkeypatch,
    tmp_path,
    artifact,
    missing_key,
):
    model_path = tmp_path / "model.joblib"

    joblib.dump(artifact, model_path)

    monkeypatch.setattr(
        risk_detector,
        "MODEL_PATH",
        str(model_path),
    )

    with pytest.raises(RuntimeError, match="Invalid calibration artifact"):
        load_model()


def test_load_model_feature_schema_mismatch(monkeypatch, tmp_path):
    artifact = {
        "model_version": "1.0",
        "calibration_method": "base",
        "features": ["wrong_feature"],
        "target": "recovery",
    }

    model_path = tmp_path / "model.joblib"
    joblib.dump(artifact, model_path)

    monkeypatch.setattr(
        risk_detector,
        "MODEL_PATH",
        str(model_path),
    )

    with pytest.raises(
        RuntimeError,
        match="feature schema does not match",
    ):
        load_model()


def test_load_model_unsupported_calibration(monkeypatch, tmp_path):
    artifact = {
        "model_version": "1.0",
        "calibration_method": "unsupported",
        "features": risk_detector.FEATURES,
        "target": "recovery",
    }

    model_path = tmp_path / "model.joblib"
    joblib.dump(artifact, model_path)

    monkeypatch.setattr(
        risk_detector,
        "MODEL_PATH",
        str(model_path),
    )

    with pytest.raises(
        RuntimeError,
        match="Unsupported calibration method",
    ):
        load_model()


def test_load_model_valid_artifact(monkeypatch, tmp_path):
    artifact = {
        "model_version": "1.0",
        "calibration_method": "base",
        "features": risk_detector.FEATURES,
        "target": "recovery",
    }

    model_path = tmp_path / "model.joblib"
    joblib.dump(artifact, model_path)

    monkeypatch.setattr(
        risk_detector,
        "MODEL_PATH",
        str(model_path),
    )

    result = load_model()

    assert result["model_version"] == "1.0"
    assert result["calibration_method"] == "base"


# ============================================================
# CALIBRATION TESTS
# ============================================================

def test_apply_calibration_base():
    artifact = {
        "calibration_method": "base",
    }

    result = apply_calibration(artifact, 0.72)

    assert result == pytest.approx(0.72)


def test_apply_calibration_base_clips_probability():
    artifact = {
        "calibration_method": "base",
    }

    assert apply_calibration(artifact, -1) == 0.0
    assert apply_calibration(artifact, 2) == 1.0


def test_apply_calibration_sigmoid():
    artifact = {
        "calibration_method": "sigmoid",
        "platt_parameters": {
            "a": 1.0,
            "b": 0.0,
        },
    }

    result = apply_calibration(artifact, 0.5)

    assert 0.0 <= result <= 1.0
    assert result == pytest.approx(0.5)


def test_apply_calibration_sigmoid_low_probability():
    artifact = {
        "calibration_method": "sigmoid",
        "platt_parameters": {
            "a": 1.0,
            "b": 0.0,
        },
    }

    result = apply_calibration(artifact, 0.2)

    assert 0.0 < result < 1.0


class DummyIsotonicModel:

    def predict(self, values):
        assert len(values) == 1
        return np.array([0.73])


def test_apply_calibration_isotonic():
    artifact = {
        "calibration_method": "isotonic",
        "isotonic_model": DummyIsotonicModel(),
    }

    result = apply_calibration(artifact, 0.5)

    assert result == pytest.approx(0.73)


# ============================================================
# RISK CLASSIFICATION TESTS
# ============================================================

def test_classify_risk_high():
    assert classify_risk(0.80) == "HIGH"
    assert classify_risk(0.95) == "HIGH"


def test_classify_risk_medium():
    assert classify_risk(0.50) == "MEDIUM"
    assert classify_risk(0.79) == "MEDIUM"


def test_classify_risk_low():
    assert classify_risk(0.0) == "LOW"
    assert classify_risk(0.49) == "LOW"


# ============================================================
# END-TO-END DETECTION TESTS
# ============================================================

def test_risk_detector_valid_payment():
    result = detect_risk(VALID_PAYMENT)

    assert result["status"] == "success"
    assert result["transaction_id"] == "TEST_RISK_001"

    assert 0.0 <= result["recovery_probability"] <= 1.0
    assert 0.0 <= result["base_probability"] <= 1.0

    assert result["risk_level"] in {
        "LOW",
        "MEDIUM",
        "HIGH",
    }

    assert result["calibration_method"] in {
        "base",
        "sigmoid",
        "isotonic",
    }

    assert 0.0 <= result["threshold"] <= 1.0
    assert isinstance(result["recovery_likely"], bool)


def test_risk_detector_missing_field():
    payment = VALID_PAYMENT.copy()
    del payment["amount"]

    with pytest.raises(ValueError):
        detect_risk(payment)


def test_risk_detector_negative_amount():
    payment = VALID_PAYMENT.copy()
    payment["amount"] = -100

    with pytest.raises(ValueError):
        detect_risk(payment)


def test_risk_detector_invalid_success_rate():
    payment = VALID_PAYMENT.copy()
    payment["previous_success_rate"] = 1.5

    with pytest.raises(ValueError):
        detect_risk(payment)


def test_risk_detector_invalid_hour():
    payment = VALID_PAYMENT.copy()
    payment["hour_of_day"] = 25

    with pytest.raises(ValueError):
        detect_risk(payment)


def test_risk_detector_invalid_weekend_flag():
    payment = VALID_PAYMENT.copy()
    payment["is_weekend"] = 2

    with pytest.raises(ValueError):
        detect_risk(payment)


def test_risk_detector_negative_attempt_count():
    payment = VALID_PAYMENT.copy()
    payment["attempt_count"] = -1

    with pytest.raises(ValueError):
        detect_risk(payment)


def test_risk_detector_probability_is_finite():
    result = detect_risk(VALID_PAYMENT)

    assert np.isfinite(result["recovery_probability"])
    assert np.isfinite(result["base_probability"])


def test_risk_detector_boundary_values():
    payment = VALID_PAYMENT.copy()

    payment["amount"] = 0
    payment["customer_age_days"] = 0
    payment["previous_transactions"] = 0
    payment["previous_success_rate"] = 0
    payment["attempt_count"] = 0
    payment["time_since_failure_min"] = 0
    payment["hour_of_day"] = 0
    payment["is_weekend"] = 0

    result = detect_risk(payment)

    assert result["status"] == "success"
    assert 0 <= result["recovery_probability"] <= 1


# ============================================================
# JSON OUTPUT
# ============================================================

def test_detect_risk_json():
    result = detect_risk_json(VALID_PAYMENT)

    assert isinstance(result, str)

    parsed = json.loads(result)

    assert parsed["status"] == "success"
    assert parsed["transaction_id"] == "TEST_RISK_001"


# ============================================================
# FAILURE BRANCHES IN detect_risk()
# ============================================================

def test_detect_risk_missing_base_model_information(monkeypatch):
    artifact = {
        "model_version": "test",
        "calibration_method": "base",
        "features": risk_detector.FEATURES,
        "target": "recovery",
    }

    monkeypatch.setattr(
        risk_detector,
        "load_model",
        lambda: artifact,
    )

    with pytest.raises(
        RuntimeError,
        match="Base model information missing",
    ):
        detect_risk(VALID_PAYMENT)


def test_detect_risk_missing_base_model_file(monkeypatch, tmp_path):
    artifact = {
        "model_version": "test",
        "calibration_method": "base",
        "features": risk_detector.FEATURES,
        "target": "recovery",
        "base_model_path": "missing_model.joblib",
    }

    monkeypatch.setattr(
        risk_detector,
        "load_model",
        lambda: artifact,
    )

    with pytest.raises(
        FileNotFoundError,
        match="Base risk model not found",
    ):
        detect_risk(VALID_PAYMENT)


class InvalidModel:

    def predict(self, X):
        return np.array([1])


def test_detect_risk_model_without_predict_proba(monkeypatch):
    artifact = {
        "model_version": "test",
        "calibration_method": "base",
        "features": risk_detector.FEATURES,
        "target": "recovery",
        "base_model": InvalidModel(),
    }

    monkeypatch.setattr(
        risk_detector,
        "load_model",
        lambda: artifact,
    )

    with pytest.raises(
        TypeError,
        match="does not support predict_proba",
    ):
        detect_risk(VALID_PAYMENT)


class InvalidProbabilityModel:

    def predict_proba(self, X):
        return np.array([[0.5, np.nan]])


def test_detect_risk_invalid_base_probability(monkeypatch):
    artifact = {
        "model_version": "test",
        "calibration_method": "base",
        "features": risk_detector.FEATURES,
        "target": "recovery",
        "base_model": InvalidProbabilityModel(),
    }

    monkeypatch.setattr(
        risk_detector,
        "load_model",
        lambda: artifact,
    )

    with pytest.raises(
        ValueError,
        match="Base probability is invalid",
    ):
        detect_risk(VALID_PAYMENT)


class InvalidCalibratedProbabilityModel:

    def predict_proba(self, X):
        return np.array([[0.0, 0.5]])


def test_detect_risk_invalid_calibrated_probability(monkeypatch):
    artifact = {
        "model_version": "test",
        "calibration_method": "isotonic",
        "features": risk_detector.FEATURES,
        "target": "recovery",
        "base_model": InvalidCalibratedProbabilityModel(),
        "isotonic_model": None,
    }

    monkeypatch.setattr(
        risk_detector,
        "load_model",
        lambda: artifact,
    )

    with pytest.raises(Exception):
        detect_risk(VALID_PAYMENT)