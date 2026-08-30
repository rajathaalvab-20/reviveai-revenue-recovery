import pytest

from payment_gateway import PaymentGatewaySimulator


def test_successful_payment():
    gateway = PaymentGatewaySimulator(
        default_outcome="SUCCESS"
    )

    result = gateway.charge(
        "TXN_SUCCESS_001",
        5000.0
    )

    assert result.success is True
    assert result.status == "succeeded"
    assert result.transaction_id == "TXN_SUCCESS_001"
    assert result.gateway_reference is not None


def test_declined_payment():
    gateway = PaymentGatewaySimulator(
        default_outcome="DECLINED"
    )

    result = gateway.charge(
        "TXN_DECLINED_001",
        5000.0
    )

    assert result.success is False
    assert result.status == "declined"
    assert result.gateway_reference is None


def test_timeout_payment():
    gateway = PaymentGatewaySimulator(
        default_outcome="TIMEOUT"
    )

    result = gateway.charge(
        "TXN_TIMEOUT_001",
        5000.0
    )

    assert result.success is False
    assert result.status == "timeout"


def test_network_error_payment():
    gateway = PaymentGatewaySimulator(
        default_outcome="NETWORK_ERROR"
    )

    result = gateway.charge(
        "TXN_NETWORK_001",
        5000.0
    )

    assert result.success is False
    assert result.status == "network_error"


def test_transaction_specific_outcome():
    gateway = PaymentGatewaySimulator(
        default_outcome="SUCCESS"
    )

    gateway.set_transaction_outcome(
        "TXN_SPECIFIC_001",
        "TIMEOUT"
    )

    result = gateway.charge(
        "TXN_SPECIFIC_001",
        5000.0
    )

    assert result.success is False
    assert result.status == "timeout"


def test_transaction_specific_outcome_does_not_affect_other_transactions():
    gateway = PaymentGatewaySimulator(
        default_outcome="SUCCESS"
    )

    gateway.set_transaction_outcome(
        "TXN_TIMEOUT_002",
        "TIMEOUT"
    )

    failed_result = gateway.charge(
        "TXN_TIMEOUT_002",
        5000.0
    )

    success_result = gateway.charge(
        "TXN_SUCCESS_002",
        5000.0
    )

    assert failed_result.status == "timeout"
    assert success_result.status == "succeeded"


def test_attempt_count_is_tracked():
    gateway = PaymentGatewaySimulator()

    gateway.charge(
        "TXN_ATTEMPT_001",
        1000.0
    )

    gateway.charge(
        "TXN_ATTEMPT_001",
        1000.0
    )

    assert gateway.get_attempt_count(
        "TXN_ATTEMPT_001"
    ) == 2


def test_new_transaction_has_zero_attempts():
    gateway = PaymentGatewaySimulator()

    assert gateway.get_attempt_count(
        "TXN_NEW_001"
    ) == 0


def test_clear_transaction_outcome():
    gateway = PaymentGatewaySimulator(
        default_outcome="SUCCESS"
    )

    gateway.set_transaction_outcome(
        "TXN_CLEAR_001",
        "TIMEOUT"
    )

    gateway.clear_transaction_outcome(
        "TXN_CLEAR_001"
    )

    result = gateway.charge(
        "TXN_CLEAR_001",
        1000.0
    )

    assert result.status == "succeeded"


def test_invalid_transaction_id_type():
    gateway = PaymentGatewaySimulator()

    with pytest.raises(TypeError):
        gateway.charge(
            12345,
            1000.0
        )


def test_empty_transaction_id():
    gateway = PaymentGatewaySimulator()

    with pytest.raises(ValueError):
        gateway.charge(
            "",
            1000.0
        )


def test_negative_amount_is_rejected():
    gateway = PaymentGatewaySimulator()

    with pytest.raises(ValueError):
        gateway.charge(
            "TXN_NEGATIVE_001",
            -100.0
        )


def test_invalid_amount_type():
    gateway = PaymentGatewaySimulator()

    with pytest.raises(TypeError):
        gateway.charge(
            "TXN_INVALID_AMOUNT_001",
            "5000"
        )


def test_invalid_default_outcome():
    with pytest.raises(ValueError):
        PaymentGatewaySimulator(
            default_outcome="INVALID"
        )


def test_invalid_transaction_outcome():
    gateway = PaymentGatewaySimulator()

    with pytest.raises(ValueError):
        gateway.set_transaction_outcome(
            "TXN_INVALID_OUTCOME_001",
            "UNKNOWN"
        )


def test_invalid_transaction_outcome_type():
    gateway = PaymentGatewaySimulator()

    with pytest.raises(TypeError):
        gateway.set_transaction_outcome(
            "TXN_INVALID_OUTCOME_002",
            123
        )


def test_response_contains_timestamp():
    gateway = PaymentGatewaySimulator()

    result = gateway.charge(
        "TXN_TIMESTAMP_001",
        1000.0
    )

    assert result.timestamp is not None
    assert isinstance(
        result.timestamp,
        str
    )


def test_gateway_reference_is_unique():
    gateway = PaymentGatewaySimulator()

    result1 = gateway.charge(
        "TXN_REFERENCE_001",
        1000.0
    )

    result2 = gateway.charge(
        "TXN_REFERENCE_002",
        1000.0
    )

    assert result1.gateway_reference != result2.gateway_reference