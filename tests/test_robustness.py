"""
ReviveAI - Robustness Test Suite

Purpose:
    Validate that ReviveAI remains safe and predictable when receiving
    malformed, adversarial, extreme, or inconsistent inputs.

These tests intentionally exercise failure conditions rather than
normal happy-path behavior.
"""

import math
import pytest

from pipeline.orchestrator import run_pipeline
from batch_simulator import BatchSimulator
from analytics import BatchAnalytics


# ============================================================
# TEST DATA HELPERS
# ============================================================

def make_valid_payment(
    transaction_id="ROBUST_001",
    amount=100.0,
    success_rate=0.8,
    hour=12,
    is_weekend=0,
    failure_code="BANK_TIMEOUT",
    failure_type="TRANSIENT",
):
    return {
        "transaction_id": transaction_id,
        "amount": amount,
        "payment_method": "CARD",
        "customer_type": "RETURNING",
        "customer_age_days": 365,
        "previous_transactions": 10,
        "previous_success_rate": success_rate,
        "failure_code": failure_code,
        "failure_type": failure_type,
        "attempt_count": 0,
        "time_since_failure_min": 5,
        "hour_of_day": hour,
        "is_weekend": is_weekend,
    }


# ============================================================
# PIPELINE ROBUSTNESS
# ============================================================

def test_pipeline_rejects_none():
    with pytest.raises((TypeError, ValueError)):
        run_pipeline(None)


def test_pipeline_rejects_list():
    with pytest.raises((TypeError, ValueError)):
        run_pipeline([])


def test_pipeline_rejects_string():
    with pytest.raises((TypeError, ValueError)):
        run_pipeline("invalid")


def test_pipeline_rejects_negative_amount():
    payment = make_valid_payment(amount=-1)

    with pytest.raises((TypeError, ValueError)):
        run_pipeline(payment)


def test_pipeline_rejects_invalid_success_rate():
    payment = make_valid_payment(
        success_rate=1.5
    )

    with pytest.raises((TypeError, ValueError)):
        run_pipeline(payment)


def test_pipeline_rejects_negative_success_rate():
    payment = make_valid_payment(
        success_rate=-0.1
    )

    with pytest.raises((TypeError, ValueError)):
        run_pipeline(payment)


def test_pipeline_rejects_invalid_hour():
    payment = make_valid_payment(
        hour=25
    )

    with pytest.raises((TypeError, ValueError)):
        run_pipeline(payment)


def test_pipeline_rejects_negative_hour():
    payment = make_valid_payment(
        hour=-1
    )

    with pytest.raises((TypeError, ValueError)):
        run_pipeline(payment)


def test_pipeline_rejects_invalid_weekend_flag():
    payment = make_valid_payment(
        is_weekend=5
    )

    with pytest.raises((TypeError, ValueError)):
        run_pipeline(payment)


def test_pipeline_rejects_missing_transaction_id():
    payment = make_valid_payment()

    del payment["transaction_id"]

    with pytest.raises((TypeError, ValueError)):
        run_pipeline(payment)


def test_pipeline_rejects_empty_transaction_id():
    payment = make_valid_payment(
        transaction_id=""
    )

    with pytest.raises((TypeError, ValueError)):
        run_pipeline(payment)


# ============================================================
# NUMERIC EDGE CASES
# ============================================================

def test_pipeline_rejects_nan_amount():
    payment = make_valid_payment(
        amount=float("nan")
    )

    with pytest.raises((TypeError, ValueError)):
        run_pipeline(payment)


def test_pipeline_rejects_infinite_amount():
    payment = make_valid_payment(
        amount=float("inf")
    )

    with pytest.raises((TypeError, ValueError)):
        run_pipeline(payment)


def test_pipeline_rejects_negative_infinite_amount():
    payment = make_valid_payment(
        amount=float("-inf")
    )

    with pytest.raises((TypeError, ValueError)):
        run_pipeline(payment)


# ============================================================
# BATCH ROBUSTNESS
# ============================================================

def test_batch_rejects_none():
    simulator = BatchSimulator()

    with pytest.raises((TypeError, ValueError)):
        simulator.run(None)


def test_batch_rejects_dictionary():
    simulator = BatchSimulator()

    with pytest.raises((TypeError, ValueError)):
        simulator.run({})


def test_batch_rejects_string():
    simulator = BatchSimulator()

    with pytest.raises((TypeError, ValueError)):
        simulator.run("invalid")


def test_batch_rejects_nested_invalid_item():
    simulator = BatchSimulator()

    payments = [
        make_valid_payment("ROBUST_001"),
        "INVALID_PAYMENT",
    ]

    with pytest.raises((TypeError, ValueError)):
        simulator.run(payments)


def test_batch_survives_transaction_failure():
    simulator = BatchSimulator()

    payments = [
        make_valid_payment("ROBUST_GOOD"),
        {
            "transaction_id": "ROBUST_BAD",
            "amount": -100,
        },
    ]

    result = simulator.run(payments)

    assert result["status"] == "completed"
    assert len(result["transactions"]) == 2


def test_batch_preserves_transaction_isolation():
    simulator = BatchSimulator()

    payments = [
        make_valid_payment("ROBUST_001"),
        make_valid_payment("ROBUST_002"),
    ]

    result = simulator.run(payments)

    ids = [
        item["transaction_id"]
        for item in result["transactions"]
    ]

    assert ids == [
        "ROBUST_001",
        "ROBUST_002",
    ]


# ============================================================
# DUPLICATE / REPLAY TEST
# ============================================================

def test_duplicate_transaction_ids_do_not_crash_batch():
    simulator = BatchSimulator()

    payments = [
        make_valid_payment("DUPLICATE_001"),
        make_valid_payment("DUPLICATE_001"),
    ]

    result = simulator.run(payments)

    assert result["status"] == "completed"
    assert len(result["transactions"]) == 2


# ============================================================
# ANALYTICS ROBUSTNESS
# ============================================================

def make_analytics_transaction(
    transaction_id="ANALYTICS_001",
    status="recovered",
    amount=100.0,
    recovered=100.0,
):
    return {
        "transaction_id": transaction_id,
        "status": status,
        "revenue_at_risk": amount,
        "revenue_recovered": recovered,
        "pipeline_result": {
            "action": {
                "action": "RETRY_PAYMENT"
            },
            "diagnosis": {
                "failure_code": "BANK_TIMEOUT",
                "failure_type": "TRANSIENT",
            },
        },
    }


def test_analytics_rejects_recovered_revenue_above_risk():

    batch = {
        "status": "completed",
        "transactions": [
            make_analytics_transaction(
                amount=100,
                recovered=101,
            )
        ],
    }

    with pytest.raises(ValueError):
        BatchAnalytics().analyze(batch)


def test_analytics_rejects_negative_risk():

    batch = {
        "status": "completed",
        "transactions": [
            make_analytics_transaction(
                amount=-100,
                recovered=0,
            )
        ],
    }

    with pytest.raises(ValueError):
        BatchAnalytics().analyze(batch)


def test_analytics_rejects_negative_recovered_revenue():

    batch = {
        "status": "completed",
        "transactions": [
            make_analytics_transaction(
                amount=100,
                recovered=-1,
            )
        ],
    }

    with pytest.raises(ValueError):
        BatchAnalytics().analyze(batch)


def test_analytics_handles_empty_batch():

    batch = {
        "status": "completed",
        "transactions": [],
    }

    result = BatchAnalytics().analyze(batch)

    assert result["status"] == "success"

    assert (
        result["summary"]["total_transactions"]
        == 0
    )


# ============================================================
# REVENUE ACCOUNTING INVARIANTS
# ============================================================

def test_recovery_rate_never_exceeds_one():

    batch = {
        "status": "completed",
        "transactions": [
            make_analytics_transaction(
                amount=100,
                recovered=50,
            ),
            make_analytics_transaction(
                transaction_id="ANALYTICS_002",
                amount=200,
                recovered=100,
            ),
        ],
    }

    result = BatchAnalytics().analyze(batch)

    assert (
        0.0
        <= result["summary"]["revenue_recovery_rate"]
        <= 1.0
    )


def test_transaction_recovery_rate_never_exceeds_one():

    batch = {
        "status": "completed",
        "transactions": [
            make_analytics_transaction(
                transaction_id="TX1",
                status="recovered",
            ),
            make_analytics_transaction(
                transaction_id="TX2",
                status="not_recovered",
                recovered=0,
            ),
        ],
    }

    result = BatchAnalytics().analyze(batch)

    assert (
        0.0
        <= result["summary"]["transaction_recovery_rate"]
        <= 1.0
    )


# ============================================================
# EXTREME BUT VALID VALUES
# ============================================================

def test_pipeline_handles_zero_amount():

    payment = make_valid_payment(
        transaction_id="ZERO_AMOUNT",
        amount=0,
    )

    result = run_pipeline(payment)

    assert result is not None
    assert result["transaction_id"] == "ZERO_AMOUNT"


def test_pipeline_handles_small_positive_amount():

    payment = make_valid_payment(
        transaction_id="SMALL_AMOUNT",
        amount=0.01,
    )

    result = run_pipeline(payment)

    assert result is not None


def test_pipeline_handles_large_allowed_amount():

    payment = make_valid_payment(
        transaction_id="LARGE_AMOUNT",
        amount=50000,
    )

    result = run_pipeline(payment)

    assert result is not None


# ============================================================
# TYPE ROBUSTNESS
# ============================================================

@pytest.mark.parametrize(
    "amount",
    [
        "100",
        None,
        [],
        {},
        object(),
    ],
)
def test_invalid_amount_types_are_rejected(amount):

    payment = make_valid_payment(
        transaction_id="INVALID_AMOUNT",
        amount=amount,
    )

    with pytest.raises((TypeError, ValueError)):
        run_pipeline(payment)


@pytest.mark.parametrize(
    "success_rate",
    [
        "0.8",
        None,
        [],
        {},
        object(),
    ],
)
def test_invalid_success_rate_types_are_rejected(
    success_rate
):

    payment = make_valid_payment(
        transaction_id="INVALID_RATE",
        success_rate=success_rate,
    )

    with pytest.raises((TypeError, ValueError)):
        run_pipeline(payment)