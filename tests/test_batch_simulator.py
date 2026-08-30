import pytest

from batch_simulator import BatchSimulator


def make_payment(
    transaction_id,
    amount=5000.0
):
    return {
        "transaction_id": transaction_id,
        "amount": amount,
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


def test_batch_runs_successfully():

    simulator = BatchSimulator()

    payments = [
        make_payment("BATCH001"),
        make_payment("BATCH002"),
    ]

    result = simulator.run(
        payments
    )

    assert result["status"] == "completed"

    assert (
        result["summary"]["total_transactions"]
        == 2
    )


def test_batch_contains_all_transactions():

    simulator = BatchSimulator()

    payments = [
        make_payment("BATCH003"),
        make_payment("BATCH004"),
        make_payment("BATCH005"),
    ]

    result = simulator.run(
        payments
    )

    transactions = result["transactions"]

    assert len(transactions) == 3

    ids = {
        item["transaction_id"]
        for item in transactions
    }

    assert ids == {
        "BATCH003",
        "BATCH004",
        "BATCH005"
    }


def test_revenue_at_risk_is_calculated():

    simulator = BatchSimulator()

    payments = [
        make_payment(
            "BATCH006",
            1000
        ),
        make_payment(
            "BATCH007",
            2000
        ),
    ]

    result = simulator.run(
        payments
    )

    assert (
        result["summary"]["revenue_at_risk"]
        == 3000
    )


def test_recovery_metrics_are_present():

    simulator = BatchSimulator()

    payments = [
        make_payment("BATCH008")
    ]

    result = simulator.run(
        payments
    )

    summary = result["summary"]

    assert "revenue_at_risk" in summary
    assert "revenue_recovered" in summary
    assert "revenue_not_recovered" in summary
    assert "revenue_recovery_rate" in summary
    assert "transaction_recovery_rate" in summary


def test_recovered_revenue_cannot_exceed_risk():

    simulator = BatchSimulator()

    payments = [
        make_payment("BATCH009"),
        make_payment("BATCH010"),
    ]

    result = simulator.run(
        payments
    )

    summary = result["summary"]

    assert (
        summary["revenue_recovered"]
        <= summary["revenue_at_risk"]
    )


def test_empty_batch_is_rejected():

    simulator = BatchSimulator()

    with pytest.raises(ValueError):

        simulator.run([])


def test_non_list_batch_is_rejected():

    simulator = BatchSimulator()

    with pytest.raises(TypeError):

        simulator.run(
            make_payment("INVALID001")
        )


def test_invalid_payment_is_rejected():

    simulator = BatchSimulator()

    with pytest.raises(ValueError):

        simulator.run(
            [
                {
                    "amount": 5000
                }
            ]
        )


def test_transaction_failure_does_not_crash_batch():

    simulator = BatchSimulator()

    payments = [
        make_payment("BATCH011"),
        {
            "transaction_id": "BATCH012",
            "amount": -500
        }
    ]

    result = simulator.run(
        payments
    )

    assert result["status"] == "completed"

    assert (
        len(result["transactions"])
        == 2
    )


def test_each_transaction_has_revenue_fields():

    simulator = BatchSimulator()

    payments = [
        make_payment("BATCH013"),
        make_payment("BATCH014"),
    ]

    result = simulator.run(
        payments
    )

    for transaction in result["transactions"]:

        assert (
            "revenue_at_risk"
            in transaction
        )

        assert (
            "revenue_recovered"
            in transaction
        )


def test_result_can_be_saved():

    simulator = BatchSimulator()

    payments = [
        make_payment("BATCH015")
    ]

    result = simulator.run(
        payments
    )

    path = simulator.save_result(
        result
    )

    assert path.endswith(".json")


def test_recovery_rate_is_between_zero_and_one():

    simulator = BatchSimulator()

    payments = [
        make_payment("BATCH016"),
        make_payment("BATCH017"),
    ]

    result = simulator.run(
        payments
    )

    rate = result[
        "summary"
    ][
        "revenue_recovery_rate"
    ]

    assert 0 <= rate <= 1


def test_transaction_recovery_rate_is_between_zero_and_one():

    simulator = BatchSimulator()

    payments = [
        make_payment("BATCH018"),
        make_payment("BATCH019"),
    ]

    result = simulator.run(
        payments
    )

    rate = result[
        "summary"
    ][
        "transaction_recovery_rate"
    ]

    assert 0 <= rate <= 1

