from typing import Any


TRANSIENT_FAILURES = {
    "BANK_TIMEOUT",
    "NETWORK_ERROR",
    "GATEWAY_TIMEOUT",
    "BANK_SERVER_ERROR"
}

CUSTOMER_ACTION_FAILURES = {
    "INSUFFICIENT_FUNDS",
    "EXPIRED_CARD",
    "AUTHENTICATION_FAILED"
}

HARD_FAILURES = {
    "INVALID_CARD",
    "CARD_BLOCKED",
    "FRAUD_SUSPECTED"
}

REQUIRED_FIELDS = {
    "failure_code",
    "failure_type",
    "attempt_count"
}


def validate_payment(payment: dict[str, Any]) -> None:
    if not isinstance(payment, dict):
        raise TypeError("Payment input must be a dictionary.")

    missing = REQUIRED_FIELDS - payment.keys()

    if missing:
        raise ValueError(
            "Missing required fields: "
            + ", ".join(sorted(missing))
        )

    if not isinstance(payment["attempt_count"], int):
        raise TypeError("attempt_count must be an integer.")

    if payment["attempt_count"] < 0:
        raise ValueError("attempt_count cannot be negative.")


def diagnose_payment(payment: dict[str, Any]) -> dict[str, Any]:
    validate_payment(payment)

    failure_code = str(payment["failure_code"]).upper()
    failure_type = str(payment["failure_type"]).upper()
    attempt_count = payment["attempt_count"]

    if failure_code in TRANSIENT_FAILURES:
        category = "TRANSIENT"
        reason = "Temporary payment infrastructure or network failure."
        recovery_strategy = "RETRY_PAYMENT"
        automatic_recovery = True
        retryable = True
    elif failure_code in CUSTOMER_ACTION_FAILURES:
        category = "CUSTOMER_ACTION_REQUIRED"
        reason = "Customer intervention is required to recover the payment."
        recovery_strategy = "CUSTOMER_ACTION"
        automatic_recovery = False
        retryable = False
    elif failure_code in HARD_FAILURES:
        category = "HARD_FAILURE"
        reason = "Payment failure should not be automatically retried."
        recovery_strategy = "ESCALATE"
        automatic_recovery = False
        retryable = False
    else:
        category = failure_type
        reason = "Failure code is not explicitly classified."
        recovery_strategy = "HUMAN_REVIEW"
        automatic_recovery = False
        retryable = False

    if attempt_count >= 3:
        retryable = False
        automatic_recovery = False
        recovery_strategy = "ESCALATE"
        reason += " Retry limit has been reached."

    return {
        "status": "success",
        "transaction_id": payment.get("transaction_id"),
        "failure_code": failure_code,
        "failure_type": failure_type,
        "diagnosis_category": category,
        "diagnosis_reason": reason,
        "recovery_strategy": recovery_strategy,
        "retryable": retryable,
        "automatic_recovery": automatic_recovery,
        "attempt_count": attempt_count
    }


if __name__ == "__main__":
    sample_payment = {
        "transaction_id": "TXN_DEMO_001",
        "failure_code": "BANK_TIMEOUT",
        "failure_type": "TRANSIENT",
        "attempt_count": 1
    }

    result = diagnose_payment(sample_payment)

    import json
    print(json.dumps(result, indent=4))
