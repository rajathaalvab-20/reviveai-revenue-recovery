import json
import os

import pytest

from orchestrator import run_pipeline


# ============================================================
# TEST PAYMENT
# ============================================================

def make_payment(
    transaction_id="TXN_TEST_PIPELINE_001",
    amount=5000.0,
    failure_code="BANK_TIMEOUT",
    failure_type="TRANSIENT",
    attempt_count=1
):
    return {
        "transaction_id": transaction_id,
        "amount": amount,
        "payment_method": "CARD",
        "customer_type": "RETURNING",
        "customer_age_days": 240,
        "previous_transactions": 25,
        "previous_success_rate": 0.92,
        "failure_code": failure_code,
        "failure_type": failure_type,
        "attempt_count": attempt_count,
        "time_since_failure_min": 10,
        "hour_of_day": 14,
        "is_weekend": 0
    }


# ============================================================
# BASIC END-TO-END PIPELINE
# ============================================================

def test_pipeline_runs_end_to_end():
    payment = make_payment()

    result = run_pipeline(payment)

    assert result["transaction_id"] == "TXN_TEST_PIPELINE_001"

    assert result["status"] in {
        "recovered",
        "not_recovered",
        "blocked"
    }

    assert "risk" in result
    assert "diagnosis" in result
    assert "policy" in result
    assert "action" in result
    assert "verification" in result


# ============================================================
# RISK STAGE
# ============================================================

def test_pipeline_contains_valid_risk_result():
    payment = make_payment(
        transaction_id="TXN_PIPELINE_RISK"
    )

    result = run_pipeline(payment)

    risk = result["risk"]

    assert risk["status"] == "success"
    assert 0.0 <= risk["recovery_probability"] <= 1.0
    assert 0.0 <= risk["base_probability"] <= 1.0
    assert risk["calibration_method"] in {
        "base",
        "sigmoid",
        "isotonic"
    }


# ============================================================
# DIAGNOSIS STAGE
# ============================================================

def test_pipeline_contains_diagnosis_result():
    payment = make_payment(
        transaction_id="TXN_PIPELINE_DIAGNOSIS"
    )

    result = run_pipeline(payment)

    diagnosis = result["diagnosis"]

    assert diagnosis["status"] == "success"
    assert diagnosis["failure_code"] == "BANK_TIMEOUT"
    assert diagnosis["diagnosis_category"] == "TRANSIENT"
    assert diagnosis["recovery_strategy"] == "RETRY_PAYMENT"


# ============================================================
# POLICY STAGE
# ============================================================

def test_pipeline_policy_is_present():
    payment = make_payment(
        transaction_id="TXN_PIPELINE_POLICY"
    )

    result = run_pipeline(payment)

    policy = result["policy"]

    assert policy["status"] == "success"
    assert policy["decision"] in {
        "APPROVED",
        "BLOCKED"
    }
    assert isinstance(policy["approved"], bool)
    assert "guardrails" in policy
    assert len(policy["guardrails"]) >= 1


# ============================================================
# ACTION STAGE
# ============================================================

def test_pipeline_action_contains_execution_status():
    payment = make_payment(
        transaction_id="TXN_PIPELINE_ACTION"
    )

    result = run_pipeline(payment)

    action = result["action"]

    assert "status" in action
    assert "executed" in action
    assert "transaction_id" in action
    assert "action" in action


# ============================================================
# VERIFICATION STAGE
# ============================================================

def test_pipeline_verification_is_present():
    payment = make_payment(
        transaction_id="TXN_PIPELINE_VERIFICATION"
    )

    result = run_pipeline(payment)

    verification = result["verification"]

    assert "status" in verification
    assert "recovered" in verification


# ============================================================
# VALID TRANSIENT PAYMENT SHOULD REACH ACTION
# ============================================================

def test_transient_payment_reaches_action_stage():
    payment = make_payment(
        transaction_id="TXN_PIPELINE_TRANSIENT"
    )

    result = run_pipeline(payment)

    assert result["diagnosis"]["diagnosis_category"] == "TRANSIENT"
    assert result["diagnosis"]["recovery_strategy"] == "RETRY_PAYMENT"

    assert result["policy"]["action"] == "RETRY_PAYMENT"

    assert "action" in result
    assert "verification" in result


# ============================================================
# HARD FAILURE SHOULD NOT BE RETRIED
# ============================================================

def test_hard_failure_is_not_automatically_retried():
    payment = make_payment(
        transaction_id="TXN_PIPELINE_HARD_FAILURE",
        failure_code="FRAUD_SUSPECTED",
        failure_type="HARD_FAILURE"
    )

    result = run_pipeline(payment)

    assert result["diagnosis"]["diagnosis_category"] == "HARD_FAILURE"
    assert result["diagnosis"]["recovery_strategy"] == "ESCALATE"
    assert result["diagnosis"]["retryable"] is False
    assert result["diagnosis"]["automatic_recovery"] is False

    assert result["policy"]["action"] == "ESCALATE"


# ============================================================
# CUSTOMER ACTION FAILURE
# ============================================================

def test_customer_action_failure_uses_customer_update():
    payment = make_payment(
        transaction_id="TXN_PIPELINE_CUSTOMER_ACTION",
        failure_code="EXPIRED_CARD",
        failure_type="CUSTOMER_ACTION_REQUIRED"
    )

    result = run_pipeline(payment)

    assert (
        result["diagnosis"]["diagnosis_category"]
        == "CUSTOMER_ACTION_REQUIRED"
    )

    assert (
        result["diagnosis"]["recovery_strategy"]
        == "CUSTOMER_ACTION"
    )

    assert result["diagnosis"]["automatic_recovery"] is False


# ============================================================
# UNKNOWN FAILURE MUST NOT BE AUTOMATICALLY RECOVERED
# ============================================================

def test_unknown_failure_is_not_automatically_recovered():
    payment = make_payment(
        transaction_id="TXN_PIPELINE_UNKNOWN",
        failure_code="UNKNOWN_FAILURE_CODE",
        failure_type="UNKNOWN"
    )

    result = run_pipeline(payment)

    assert (
        result["diagnosis"]["recovery_strategy"]
        == "HUMAN_REVIEW"
    )

    assert result["diagnosis"]["automatic_recovery"] is False

    assert result["policy"]["approved"] is False


# ============================================================
# LOW VALUE / ZERO AMOUNT
# ============================================================

def test_zero_amount_pipeline_does_not_crash():
    payment = make_payment(
        transaction_id="TXN_PIPELINE_ZERO_AMOUNT",
        amount=0.0
    )

    result = run_pipeline(payment)

    assert result["transaction_id"] == "TXN_PIPELINE_ZERO_AMOUNT"
    assert "risk" in result
    assert "diagnosis" in result
    assert "policy" in result


# ============================================================
# EXCESSIVE AMOUNT SHOULD BE BLOCKED
# ============================================================

def test_excessive_amount_is_blocked_by_policy():
    payment = make_payment(
        transaction_id="TXN_PIPELINE_HIGH_AMOUNT",
        amount=100000.0
    )

    result = run_pipeline(payment)

    assert result["policy"]["approved"] is False
    assert result["policy"]["decision"] == "BLOCKED"

    assert result["status"] == "blocked"


# ============================================================
# RETRY LIMIT
# ============================================================

def test_retry_limit_prevents_automatic_retry():
    payment = make_payment(
        transaction_id="TXN_PIPELINE_RETRY_LIMIT",
        attempt_count=3
    )

    result = run_pipeline(payment)

    assert result["diagnosis"]["retryable"] is False
    assert result["diagnosis"]["automatic_recovery"] is False
    assert result["diagnosis"]["recovery_strategy"] == "ESCALATE"


# ============================================================
# MISSING TRANSACTION ID
# ============================================================

def test_missing_transaction_id_is_rejected():
    payment = make_payment()

    del payment["transaction_id"]

    with pytest.raises(ValueError):
        run_pipeline(payment)


# ============================================================
# NON-DICTIONARY INPUT
# ============================================================

def test_non_dictionary_input_is_rejected():
    with pytest.raises(TypeError):
        run_pipeline("invalid payment")


# ============================================================
# MISSING RISK FIELD
# ============================================================

def test_missing_risk_field_is_rejected():
    payment = make_payment()

    del payment["amount"]

    with pytest.raises(ValueError):
        run_pipeline(payment)


# ============================================================
# INVALID SUCCESS RATE
# ============================================================

def test_invalid_success_rate_is_rejected():
    payment = make_payment()

    payment["previous_success_rate"] = 1.5

    with pytest.raises(ValueError):
        run_pipeline(payment)


# ============================================================
# INVALID HOUR
# ============================================================

def test_invalid_hour_is_rejected():
    payment = make_payment()

    payment["hour_of_day"] = 25

    with pytest.raises(ValueError):
        run_pipeline(payment)


# ============================================================
# INVALID WEEKEND FLAG
# ============================================================

def test_invalid_weekend_flag_is_rejected():
    payment = make_payment()

    payment["is_weekend"] = 2

    with pytest.raises(ValueError):
        run_pipeline(payment)


# ============================================================
# NEGATIVE AMOUNT
# ============================================================

def test_negative_amount_is_rejected():
    payment = make_payment(
        amount=-500
    )

    with pytest.raises(ValueError):
        run_pipeline(payment)


# ============================================================
# PIPELINE VERSION
# ============================================================

def test_pipeline_contains_version():
    payment = make_payment(
        transaction_id="TXN_PIPELINE_VERSION"
    )

    result = run_pipeline(payment)

    assert "pipeline_version" in result
    assert result["pipeline_version"] == "V1"


# ============================================================
# TIMESTAMPS
# ============================================================

def test_pipeline_contains_timestamps():
    payment = make_payment(
        transaction_id="TXN_PIPELINE_TIMESTAMP"
    )

    result = run_pipeline(payment)

    assert "started_at" in result
    assert "completed_at" in result


# ============================================================
# PIPELINE RESULT FILE
# ============================================================

def test_pipeline_result_file_is_created():
    payment = make_payment(
        transaction_id="TXN_PIPELINE_FILE"
    )

    result = run_pipeline(payment)

    assert "pipeline_result_file" in result

    result_file = result["pipeline_result_file"]

    assert os.path.exists(result_file)


# ============================================================
# SAVED RESULT IS VALID JSON
# ============================================================

def test_pipeline_result_file_contains_valid_json():
    payment = make_payment(
        transaction_id="TXN_PIPELINE_JSON"
    )

    result = run_pipeline(payment)

    result_file = result["pipeline_result_file"]

    assert os.path.exists(result_file)

    with open(
        result_file,
        "r",
        encoding="utf-8"
    ) as file:
        saved_result = json.load(file)

    assert saved_result["transaction_id"] == (
        "TXN_PIPELINE_JSON"
    )

    assert "risk" in saved_result
    assert "diagnosis" in saved_result
    assert "policy" in saved_result
    assert "action" in saved_result
    assert "verification" in saved_result


# ============================================================
# SUCCESSFUL RECOVERY FLOW
# ============================================================

def test_successful_pipeline_contains_recovery_information():
    payment = make_payment(
        transaction_id="TXN_PIPELINE_RECOVERY"
    )

    result = run_pipeline(payment)

    if result["status"] == "recovered":
        assert result["verification"]["recovered"] is True

        assert (
            result["verification"]["revenue_recovered"]
            >= 0.0
        )

    else:
        assert result["status"] in {
            "not_recovered",
            "blocked"
        }


# ============================================================
# NO ACTION AFTER POLICY BLOCK
# ============================================================

def test_blocked_policy_does_not_execute_action():
    payment = make_payment(
        transaction_id="TXN_PIPELINE_BLOCKED",
        amount=100000.0
    )

    result = run_pipeline(payment)

    assert result["status"] == "blocked"
    assert result["policy"]["approved"] is False

    assert result["action"]["executed"] is False

    assert result["verification"]["verified"] is False


# ============================================================
# END-TO-END FIELD CONSISTENCY
# ============================================================

def test_pipeline_transaction_id_is_consistent():
    transaction_id = "TXN_PIPELINE_CONSISTENCY"

    payment = make_payment(
        transaction_id=transaction_id
    )

    result = run_pipeline(payment)

    assert result["transaction_id"] == transaction_id
    assert result["risk"]["transaction_id"] == transaction_id
    assert result["diagnosis"]["transaction_id"] == transaction_id
    assert result["policy"]["transaction_id"] == transaction_id
    assert result["action"]["transaction_id"] == transaction_id
    assert result["verification"]["transaction_id"] == transaction_id
# ============================================================
# FAILURE-PATH HARDENING TESTS
# ============================================================

def test_risk_failure_is_recorded_and_raised(monkeypatch):
    import orchestrator

    payment = make_payment(
        transaction_id="TXN_PIPELINE_RISK_FAILURE"
    )

    def fake_detect_risk(payment):
        return {
            "status": "failed",
            "reason": "Model unavailable"
        }

    monkeypatch.setattr(
        orchestrator,
        "detect_risk",
        fake_detect_risk
    )

    with pytest.raises(
        RuntimeError,
        match="Risk detection failed"
    ):
        run_pipeline(payment)

    result_file = os.path.join(
        orchestrator.RESULT_DIR,
        "TXN_PIPELINE_RISK_FAILURE.json"
    )

    assert os.path.exists(result_file)

    with open(
        result_file,
        "r",
        encoding="utf-8"
    ) as file:
        saved = json.load(file)

    assert saved["status"] == "failed"
    assert saved["error"]["error_type"] == "RuntimeError"
    assert "Risk detection failed" in saved["error"]["error"]


def test_diagnosis_failure_is_recorded_and_raised(monkeypatch):
    import orchestrator

    payment = make_payment(
        transaction_id="TXN_PIPELINE_DIAGNOSIS_FAILURE"
    )

    def fake_diagnose_payment(payment):
        return {
            "status": "failed",
            "reason": "Diagnosis unavailable"
        }

    monkeypatch.setattr(
        orchestrator,
        "diagnose_payment",
        fake_diagnose_payment
    )

    with pytest.raises(
        RuntimeError,
        match="Diagnosis failed"
    ):
        run_pipeline(payment)

    result_file = os.path.join(
        orchestrator.RESULT_DIR,
        "TXN_PIPELINE_DIAGNOSIS_FAILURE.json"
    )

    assert os.path.exists(result_file)

    with open(
        result_file,
        "r",
        encoding="utf-8"
    ) as file:
        saved = json.load(file)

    assert saved["status"] == "failed"
    assert saved["error"]["error_type"] == "RuntimeError"
    assert "Diagnosis failed" in saved["error"]["error"]


def test_action_not_executed_skips_verification(monkeypatch):
    import orchestrator

    payment = make_payment(
        transaction_id="TXN_PIPELINE_ACTION_NOT_EXECUTED"
    )

    fake_action_result = {
        "status": "blocked",
        "action_id": "ACT_TEST_001",
        "transaction_id": "TXN_PIPELINE_ACTION_NOT_EXECUTED",
        "action": "RETRY_PAYMENT",
        "executed": False,
        "reason": "Retry limit reached."
    }

    monkeypatch.setattr(
        orchestrator,
        "execute_action",
        lambda policy_result: fake_action_result
    )

    verification_called = False

    def fake_verify_action(action_result):
        nonlocal verification_called
        verification_called = True
        raise AssertionError(
            "Verification must not run when action was not executed."
        )

    monkeypatch.setattr(
        orchestrator,
        "verify_action",
        fake_verify_action
    )

    result = run_pipeline(payment)

    assert result["status"] == "not_recovered"

    assert result["action"]["executed"] is False

    assert result["verification"]["status"] == "not_executed"
    assert result["verification"]["verified"] is False

    assert verification_called is False


def test_unexpected_system_error_is_recorded(monkeypatch):
    import orchestrator

    payment = make_payment(
        transaction_id="TXN_PIPELINE_SYSTEM_ERROR"
    )

    def fake_detect_risk(payment):
        raise RuntimeError(
            "Simulated model infrastructure failure"
        )

    monkeypatch.setattr(
        orchestrator,
        "detect_risk",
        fake_detect_risk
    )

    with pytest.raises(
        RuntimeError,
        match="Simulated model infrastructure failure"
    ):
        run_pipeline(payment)

    result_file = os.path.join(
        orchestrator.RESULT_DIR,
        "TXN_PIPELINE_SYSTEM_ERROR.json"
    )

    assert os.path.exists(result_file)

    with open(
        result_file,
        "r",
        encoding="utf-8"
    ) as file:
        saved = json.load(file)

    assert saved["status"] == "failed"

    assert saved["error"]["error_type"] == (
        "RuntimeError"
    )

    assert saved["error"]["error"] == (
        "Simulated model infrastructure failure"
    )

    assert "completed_at" in saved


def test_save_pipeline_result_raise_error():
    import orchestrator

    result = {
        "transaction_id": "TXN_PIPELINE_SAVE_ERROR",
        "status": "failed",
        "error": {
            "error_type": "RuntimeError",
            "error": "Synthetic pipeline failure"
        }
    }

    with pytest.raises(
        RuntimeError,
        match="RuntimeError: Synthetic pipeline failure"
    ):
        orchestrator.save_pipeline_result(
            result,
            raise_error=True
        )

    result_file = os.path.join(
        orchestrator.RESULT_DIR,
        "TXN_PIPELINE_SAVE_ERROR.json"
    )

    assert os.path.exists(result_file)
