import pytest

from diagnosis_engine import diagnose_payment


def test_transient_failure():
    payment = {
        "transaction_id": "TEST_DIAG_001",
        "failure_code": "BANK_TIMEOUT",
        "failure_type": "TRANSIENT",
        "attempt_count": 1
    }

    result = diagnose_payment(payment)

    assert result["status"] == "success"
    assert result["diagnosis_category"] == "TRANSIENT"
    assert result["recovery_strategy"] == "RETRY_PAYMENT"
    assert result["retryable"] is True
    assert result["automatic_recovery"] is True


def test_network_error_is_retryable():
    payment = {
        "transaction_id": "TEST_DIAG_002",
        "failure_code": "NETWORK_ERROR",
        "failure_type": "TRANSIENT",
        "attempt_count": 0
    }

    result = diagnose_payment(payment)

    assert result["diagnosis_category"] == "TRANSIENT"
    assert result["recovery_strategy"] == "RETRY_PAYMENT"
    assert result["retryable"] is True


def test_customer_action_required():
    payment = {
        "transaction_id": "TEST_DIAG_003",
        "failure_code": "INSUFFICIENT_FUNDS",
        "failure_type": "CUSTOMER_ACTION_REQUIRED",
        "attempt_count": 1
    }

    result = diagnose_payment(payment)

    assert result["status"] == "success"
    assert result["diagnosis_category"] == "CUSTOMER_ACTION_REQUIRED"
    assert result["recovery_strategy"] == "CUSTOMER_ACTION"
    assert result["retryable"] is False
    assert result["automatic_recovery"] is False


def test_expired_card_requires_customer_action():
    payment = {
        "transaction_id": "TEST_DIAG_004",
        "failure_code": "EXPIRED_CARD",
        "failure_type": "CUSTOMER_ACTION_REQUIRED",
        "attempt_count": 1
    }

    result = diagnose_payment(payment)

    assert result["diagnosis_category"] == "CUSTOMER_ACTION_REQUIRED"
    assert result["recovery_strategy"] == "CUSTOMER_ACTION"
    assert result["retryable"] is False
    assert result["automatic_recovery"] is False


def test_hard_failure_is_escalated():
    payment = {
        "transaction_id": "TEST_DIAG_005",
        "failure_code": "FRAUD_SUSPECTED",
        "failure_type": "HARD_FAILURE",
        "attempt_count": 1
    }

    result = diagnose_payment(payment)

    assert result["status"] == "success"
    assert result["diagnosis_category"] == "HARD_FAILURE"
    assert result["recovery_strategy"] == "ESCALATE"
    assert result["retryable"] is False
    assert result["automatic_recovery"] is False


def test_invalid_card_is_not_retried():
    payment = {
        "transaction_id": "TEST_DIAG_006",
        "failure_code": "INVALID_CARD",
        "failure_type": "HARD_FAILURE",
        "attempt_count": 1
    }

    result = diagnose_payment(payment)

    assert result["diagnosis_category"] == "HARD_FAILURE"
    assert result["recovery_strategy"] == "ESCALATE"
    assert result["retryable"] is False
    assert result["automatic_recovery"] is False


def test_unknown_failure_code_goes_to_human_review():
    payment = {
        "transaction_id": "TEST_DIAG_007",
        "failure_code": "UNKNOWN_FAILURE",
        "failure_type": "UNKNOWN",
        "attempt_count": 1
    }

    result = diagnose_payment(payment)

    assert result["status"] == "success"
    assert result["recovery_strategy"] == "HUMAN_REVIEW"
    assert result["retryable"] is False
    assert result["automatic_recovery"] is False


def test_retry_limit_reached():
    payment = {
        "transaction_id": "TEST_DIAG_008",
        "failure_code": "BANK_TIMEOUT",
        "failure_type": "TRANSIENT",
        "attempt_count": 3
    }

    result = diagnose_payment(payment)

    assert result["diagnosis_category"] == "TRANSIENT"
    assert result["recovery_strategy"] == "ESCALATE"
    assert result["retryable"] is False
    assert result["automatic_recovery"] is False
    assert "Retry limit has been reached." in result["diagnosis_reason"]


def test_attempt_count_cannot_be_negative():
    payment = {
        "transaction_id": "TEST_DIAG_009",
        "failure_code": "BANK_TIMEOUT",
        "failure_type": "TRANSIENT",
        "attempt_count": -1
    }

    with pytest.raises(ValueError):
        diagnose_payment(payment)


def test_attempt_count_must_be_integer():
    payment = {
        "transaction_id": "TEST_DIAG_010",
        "failure_code": "BANK_TIMEOUT",
        "failure_type": "TRANSIENT",
        "attempt_count": 1.5
    }

    with pytest.raises(TypeError):
        diagnose_payment(payment)


def test_missing_failure_code():
    payment = {
        "transaction_id": "TEST_DIAG_011",
        "failure_type": "TRANSIENT",
        "attempt_count": 1
    }

    with pytest.raises(ValueError):
        diagnose_payment(payment)


def test_missing_failure_type():
    payment = {
        "transaction_id": "TEST_DIAG_012",
        "failure_code": "BANK_TIMEOUT",
        "attempt_count": 1
    }

    with pytest.raises(ValueError):
        diagnose_payment(payment)


def test_missing_attempt_count():
    payment = {
        "transaction_id": "TEST_DIAG_013",
        "failure_code": "BANK_TIMEOUT",
        "failure_type": "TRANSIENT"
    }

    with pytest.raises(ValueError):
        diagnose_payment(payment)


def test_non_dictionary_input():
    with pytest.raises(TypeError):
        diagnose_payment("invalid_payment")

