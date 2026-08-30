import pytest

from failure_injector import FailureInjector


def test_default_success_payment():
    injector = FailureInjector()

    result = injector.process_payment(
        "TXN001",
        5000
    )

    assert result["outcome"] == "SUCCESS"
    assert result["successful"] is True
    assert result["attempt_count"] == 1


def test_default_declined_payment():
    injector = FailureInjector(
        default_outcome="DECLINED"
    )

    result = injector.process_payment(
        "TXN002",
        5000
    )

    assert result["outcome"] == "DECLINED"
    assert result["successful"] is False


def test_timeout_payment():
    injector = FailureInjector(
        default_outcome="TIMEOUT"
    )

    result = injector.process_payment(
        "TXN003",
        5000
    )

    assert result["outcome"] == "TIMEOUT"
    assert result["successful"] is False


def test_network_error_payment():
    injector = FailureInjector(
        default_outcome="NETWORK_ERROR"
    )

    result = injector.process_payment(
        "TXN004",
        5000
    )

    assert result["outcome"] == "NETWORK_ERROR"
    assert result["successful"] is False


def test_transaction_specific_outcome():
    injector = FailureInjector()

    injector.set_transaction_outcome(
        "TXN005",
        "TIMEOUT"
    )

    result = injector.process_payment(
        "TXN005",
        5000
    )

    assert result["outcome"] == "TIMEOUT"
    assert result["successful"] is False


def test_transaction_sequence_timeout_then_success():
    injector = FailureInjector()

    injector.set_transaction_outcomes(
        "TXN006",
        [
            "TIMEOUT",
            "SUCCESS"
        ]
    )

    first = injector.process_payment(
        "TXN006",
        5000
    )

    second = injector.process_payment(
        "TXN006",
        5000
    )

    assert first["outcome"] == "TIMEOUT"
    assert first["successful"] is False

    assert second["outcome"] == "SUCCESS"
    assert second["successful"] is True

    assert first["attempt_count"] == 1
    assert second["attempt_count"] == 2


def test_multiple_failures_then_success():
    injector = FailureInjector()

    injector.set_transaction_outcomes(
        "TXN007",
        [
            "TIMEOUT",
            "NETWORK_ERROR",
            "SUCCESS"
        ]
    )

    results = []

    for _ in range(3):
        results.append(
            injector.process_payment(
                "TXN007",
                5000
            )
        )

    assert results[0]["outcome"] == "TIMEOUT"
    assert results[1]["outcome"] == "NETWORK_ERROR"
    assert results[2]["outcome"] == "SUCCESS"


def test_final_outcome_is_reused_after_sequence():
    injector = FailureInjector()

    injector.set_transaction_outcomes(
        "TXN008",
        [
            "TIMEOUT",
            "SUCCESS"
        ]
    )

    injector.process_payment(
        "TXN008",
        5000
    )

    injector.process_payment(
        "TXN008",
        5000
    )

    third = injector.process_payment(
        "TXN008",
        5000
    )

    assert third["outcome"] == "SUCCESS"
    assert third["attempt_count"] == 3


def test_attempt_count_is_tracked():
    injector = FailureInjector()

    injector.set_transaction_outcome(
        "TXN009",
        "TIMEOUT"
    )

    injector.process_payment(
        "TXN009",
        1000
    )

    injector.process_payment(
        "TXN009",
        1000
    )

    assert injector.get_attempt_count(
        "TXN009"
    ) == 2


def test_new_transaction_has_zero_attempts():
    injector = FailureInjector()

    assert injector.get_attempt_count(
        "NEW_TXN"
    ) == 0


def test_transactions_are_independent():
    injector = FailureInjector()

    injector.set_transaction_outcome(
        "TXN_A",
        "TIMEOUT"
    )

    injector.set_transaction_outcome(
        "TXN_B",
        "SUCCESS"
    )

    result_a = injector.process_payment(
        "TXN_A",
        1000
    )

    result_b = injector.process_payment(
        "TXN_B",
        1000
    )

    assert result_a["outcome"] == "TIMEOUT"
    assert result_b["outcome"] == "SUCCESS"

    assert result_a["attempt_count"] == 1
    assert result_b["attempt_count"] == 1


def test_gateway_reference_is_unique_per_attempt():
    injector = FailureInjector()

    injector.set_transaction_outcome(
        "TXN010",
        "TIMEOUT"
    )

    first = injector.process_payment(
        "TXN010",
        1000
    )

    second = injector.process_payment(
        "TXN010",
        1000
    )

    assert (
        first["gateway_reference"]
        != second["gateway_reference"]
    )


def test_invalid_transaction_id_type():
    injector = FailureInjector()

    with pytest.raises(TypeError):
        injector.process_payment(
            123,
            1000
        )


def test_empty_transaction_id():
    injector = FailureInjector()

    with pytest.raises(ValueError):
        injector.process_payment(
            "",
            1000
        )


def test_negative_amount_is_rejected():
    injector = FailureInjector()

    with pytest.raises(ValueError):
        injector.process_payment(
            "TXN011",
            -500
        )


def test_invalid_amount_type():
    injector = FailureInjector()

    with pytest.raises(TypeError):
        injector.process_payment(
            "TXN012",
            "5000"
        )


def test_invalid_default_outcome():
    with pytest.raises(ValueError):
        FailureInjector(
            default_outcome="INVALID"
        )


def test_invalid_transaction_outcome():
    injector = FailureInjector()

    with pytest.raises(ValueError):
        injector.set_transaction_outcome(
            "TXN013",
            "INVALID"
        )


def test_invalid_transaction_outcome_type():
    injector = FailureInjector()

    with pytest.raises(TypeError):
        injector.set_transaction_outcome(
            "TXN014",
            123
        )


def test_empty_outcome_sequence():
    injector = FailureInjector()

    with pytest.raises(ValueError):
        injector.set_transaction_outcomes(
            "TXN015",
            []
        )


def test_clear_transaction():
    injector = FailureInjector()

    injector.set_transaction_outcome(
        "TXN016",
        "TIMEOUT"
    )

    injector.process_payment(
        "TXN016",
        1000
    )

    injector.clear_transaction(
        "TXN016"
    )

    assert injector.get_attempt_count(
        "TXN016"
    ) == 0


def test_reset_clears_all_transactions():
    injector = FailureInjector()

    injector.set_transaction_outcome(
        "TXN017",
        "TIMEOUT"
    )

    injector.set_transaction_outcome(
        "TXN018",
        "SUCCESS"
    )

    injector.process_payment(
        "TXN017",
        1000
    )

    injector.process_payment(
        "TXN018",
        1000
    )

    injector.reset()

    assert injector.get_attempt_count(
        "TXN017"
    ) == 0

    assert injector.get_attempt_count(
        "TXN018"
    ) == 0
