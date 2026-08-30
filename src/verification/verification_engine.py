import json
import os
import hashlib
from datetime import datetime, timezone


# ============================================================
# REVIVEAI - VERIFICATION ENGINE
# ============================================================
#
# Pipeline:
#   Risk -> Diagnosis -> Policy -> Action -> Verification
#
# Purpose:
#   Verify whether the recovery action actually succeeded.
#
# IMPORTANT:
#   This implementation uses deterministic simulation.
#   No real payment API is called.
#
# Design goals:
#   - Deterministic verification
#   - Strong input validation
#   - Explicit recovery states
#   - Revenue recovery measurement
#   - Safe handling of non-executed actions
#   - Audit-friendly result structure
#   - Testable CLI/demo entry point
# ============================================================


VERIFICATION_VERSION = "V1"

VERIFICATION_DIR = "src/verification/results"

os.makedirs(
    VERIFICATION_DIR,
    exist_ok=True
)


# Actions that can directly recover revenue.
RECOVERABLE_ACTIONS = {
    "RETRY_PAYMENT",
    "PAYMENT_REMINDER",
    "REQUEST_PAYMENT_METHOD_UPDATE"
}


# Actions that require downstream processing.
PENDING_ACTIONS = {
    "ESCALATE",
    "HUMAN_REVIEW"
}


# ============================================================
# VALIDATION
# ============================================================

def validate_action_result(action_result):
    """
    Validate the result received from the Action Engine.

    The verification layer must reject malformed action results
    instead of silently attempting verification.
    """

    if not isinstance(action_result, dict):
        raise TypeError(
            "action_result must be a dictionary."
        )

    required = [
        "transaction_id",
        "action_id",
        "action",
        "executed",
        "amount"
    ]

    missing = [
        field
        for field in required
        if field not in action_result
    ]

    if missing:
        raise ValueError(
            "Action result missing fields: "
            + ", ".join(missing)
        )

    if not isinstance(
        action_result["executed"],
        bool
    ):
        raise TypeError(
            "executed must be boolean."
        )

    try:
        amount = float(
            action_result["amount"]
        )
    except (TypeError, ValueError) as error:
        raise TypeError(
            "amount must be numeric."
        ) from error

    if amount < 0:
        raise ValueError(
            "amount cannot be negative."
        )

    transaction_id = str(
        action_result["transaction_id"]
    ).strip()

    if not transaction_id:
        raise ValueError(
            "transaction_id cannot be empty."
        )

    action_id = str(
        action_result["action_id"]
    ).strip()

    if not action_id:
        raise ValueError(
            "action_id cannot be empty."
        )

    action = str(
        action_result["action"]
    ).strip()

    if not action:
        raise ValueError(
            "action cannot be empty."
        )


# ============================================================
# DETERMINISTIC RECOVERY SIMULATION
# ============================================================

def deterministic_recovery_check(
    transaction_id,
    action_id,
    action
):
    """
    Deterministically simulate whether an executed recovery
    action successfully recovered the payment.

    SHA-256 is used so the same inputs always produce the
    same result across executions.
    """

    seed = (
        str(transaction_id)
        + "|"
        + str(action_id)
        + "|"
        + str(action)
    )

    digest = hashlib.sha256(
        seed.encode("utf-8")
    ).hexdigest()

    value = int(
        digest[:8],
        16
    )

    return (
        value % 100
    ) < 70


# ============================================================
# RESULT BUILDERS
# ============================================================

def _timestamp():
    return datetime.now(
        timezone.utc
    ).isoformat()


def _base_result(
    transaction_id,
    action_id,
    action
):
    return {
        "status": "verified",
        "transaction_id": transaction_id,
        "action_id": action_id,
        "action": action,
        "timestamp": _timestamp(),
        "verification_version": VERIFICATION_VERSION
    }


# ============================================================
# VERIFICATION
# ============================================================

def verify_action(action_result):
    """
    Verify the outcome of an Action Engine decision.

    Possible verification states:

        RECOVERED
        NOT_RECOVERED
        PENDING

    Revenue is counted as recovered only when verification
    explicitly confirms recovery.
    """

    validate_action_result(
        action_result
    )

    transaction_id = str(
        action_result["transaction_id"]
    )

    action_id = str(
        action_result["action_id"]
    )

    action = str(
        action_result["action"]
    )

    executed = action_result[
        "executed"
    ]

    amount = float(
        action_result["amount"]
    )

    # --------------------------------------------------------
    # Action was not executed
    # --------------------------------------------------------

    if not executed:
        result = _base_result(
            transaction_id,
            action_id,
            action
        )

        result.update({
            "verification_status": "NOT_RECOVERED",
            "recovered": False,
            "revenue_recovered": 0.0,
            "amount_at_risk": amount,
            "reason": (
                "Recovery action was not executed."
            )
        })

        return result

    # --------------------------------------------------------
    # Actions requiring downstream processing
    # --------------------------------------------------------

    if action in PENDING_ACTIONS:
        result = _base_result(
            transaction_id,
            action_id,
            action
        )

        result.update({
            "verification_status": "PENDING",
            "recovered": False,
            "revenue_recovered": 0.0,
            "amount_at_risk": amount,
            "reason": (
                "Action requires downstream human "
                "or external verification."
            )
        })

        return result

    # --------------------------------------------------------
    # Unsupported verification action
    # --------------------------------------------------------

    if action not in RECOVERABLE_ACTIONS:
        raise ValueError(
            "Unsupported verification action: "
            + action
        )

    # --------------------------------------------------------
    # Deterministic recovery verification
    # --------------------------------------------------------

    recovered = deterministic_recovery_check(
        transaction_id,
        action_id,
        action
    )

    if recovered:

        verification_status = (
            "RECOVERED"
        )

        revenue_recovered = amount

        reason = (
            "Payment recovery confirmed by simulation."
        )

    else:

        verification_status = (
            "NOT_RECOVERED"
        )

        revenue_recovered = 0.0

        reason = (
            "Recovery action executed but payment "
            "was not recovered."
        )

    result = _base_result(
        transaction_id,
        action_id,
        action
    )

    result.update({
        "verification_status":
            verification_status,

        "recovered":
            recovered,

        "revenue_recovered":
            revenue_recovered,

        "amount_at_risk":
            amount,

        "reason":
            reason
    })

    return result


# ============================================================
# PERSISTENCE
# ============================================================

def save_verification_result(result):
    """
    Persist a verification result as JSON.

    One transaction produces one audit result file.
    """

    if not isinstance(result, dict):
        raise TypeError(
            "result must be a dictionary."
        )

    if "transaction_id" not in result:
        raise ValueError(
            "Verification result missing transaction_id."
        )

    transaction_id = str(
        result["transaction_id"]
    ).strip()

    if not transaction_id:
        raise ValueError(
            "transaction_id cannot be empty."
        )

    os.makedirs(
        VERIFICATION_DIR,
        exist_ok=True
    )

    path = os.path.join(
        VERIFICATION_DIR,
        f"{transaction_id}.json"
    )

    with open(
        path,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            result,
            file,
            indent=2
        )

    return path


# ============================================================
# DEMO / CLI
# ============================================================

def main():
    """
    Demonstration entry point.

    This is deliberately separated from the core verification
    logic so it can be tested independently.
    """

    demo_action_result = {
        "status": "success",
        "action_id": "ACT_DEMO_001",
        "transaction_id": "TXN_DEMO_001",
        "action": "RETRY_PAYMENT",
        "executed": True,
        "simulation": True,
        "attempt_count_before": 1,
        "attempt_count_after": 2,
        "amount": 5000.0
    }

    try:

        result = verify_action(
            demo_action_result
        )

        result["result_file"] = (
            save_verification_result(
                result
            )
        )

        print(
            json.dumps(
                result,
                indent=2
            )
        )

        return result

    except Exception as error:

        error_result = {
            "status": "error",
            "error_type": type(error).__name__,
            "error": str(error)
        }

        print(
            json.dumps(
                error_result,
                indent=2
            )
        )

        raise


if __name__ == "__main__":
    main()