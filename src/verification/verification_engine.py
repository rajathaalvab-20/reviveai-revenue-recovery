from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any


# ============================================================
# REVIVEAI - VERIFICATION ENGINE
# ============================================================
#
# Pipeline:
#
#   Risk -> Diagnosis -> Policy -> Action -> Verification
#
# Verification has TWO modes:
#
# 1. DATASET GROUND-TRUTH MODE
#    Used by the simulation when payment_events.csv contains:
#
#       actual_recovery
#       recovered_amount
#
#    This is the preferred evaluation mode.
#
# 2. DETERMINISTIC FALLBACK MODE
#    Used when no ground truth is supplied.
#
#    This keeps the verification engine usable independently
#    and preserves deterministic unit-test behaviour.
#
# IMPORTANT:
#
# The production/simulation evaluation MUST pass ground truth
# whenever it is available.
#
# The deterministic fallback is NOT used when dataset ground
# truth is available.
# ============================================================


VERIFICATION_VERSION = "V2"


VERIFICATION_DIR = os.path.join(
    os.path.dirname(__file__),
    "results",
)

os.makedirs(
    VERIFICATION_DIR,
    exist_ok=True,
)


# ============================================================
# ACTION DEFINITIONS
# ============================================================

RECOVERABLE_ACTIONS = {
    "RETRY_PAYMENT",
    "PAYMENT_REMINDER",
    "REQUEST_PAYMENT_METHOD_UPDATE",
}


PENDING_ACTIONS = {
    "ESCALATE",
    "HUMAN_REVIEW",
}


# ============================================================
# INPUT VALIDATION
# ============================================================

def validate_action_result(
    action_result: dict[str, Any],
) -> None:
    """
    Validate the Action Engine result.

    Raises:
        TypeError
        ValueError
    """

    if not isinstance(action_result, dict):
        raise TypeError(
            "action_result must be a dictionary."
        )

    required_fields = [
        "transaction_id",
        "action_id",
        "action",
        "executed",
        "amount",
    ]

    missing = [
        field
        for field in required_fields
        if field not in action_result
    ]

    if missing:
        raise ValueError(
            "Action result missing fields: "
            + ", ".join(missing)
        )

    if not isinstance(
        action_result["executed"],
        bool,
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
# GROUND TRUTH VALIDATION
# ============================================================

def _parse_bool(
    value: Any,
) -> bool:
    """
    Convert common CSV/API boolean representations
    into a real Python boolean.
    """

    if isinstance(value, bool):
        return value

    if isinstance(value, int):
        if value in (0, 1):
            return bool(value)

    if isinstance(value, float):
        if value in (0.0, 1.0):
            return bool(value)

    if isinstance(value, str):

        normalized = value.strip().lower()

        if normalized in {
            "1",
            "true",
            "yes",
            "y",
            "recovered",
        }:
            return True

        if normalized in {
            "0",
            "false",
            "no",
            "n",
            "not_recovered",
            "not recovered",
        }:
            return False

    raise ValueError(
        "actual_recovery must be boolean-like "
        "(0/1, true/false, yes/no)."
    )


def validate_ground_truth(
    ground_truth: dict[str, Any],
) -> dict[str, Any]:
    """
    Validate and normalize payment ground truth.

    Required fields:

        actual_recovery
        recovered_amount

    Optional fields are preserved.
    """

    if not isinstance(
        ground_truth,
        dict,
    ):
        raise TypeError(
            "ground_truth must be a dictionary."
        )

    required_fields = [
        "actual_recovery",
        "recovered_amount",
    ]

    missing = [
        field
        for field in required_fields
        if field not in ground_truth
    ]

    if missing:
        raise ValueError(
            "Payment ground truth missing fields: "
            + ", ".join(missing)
        )

    actual_recovery = _parse_bool(
        ground_truth["actual_recovery"]
    )

    try:
        recovered_amount = float(
            ground_truth["recovered_amount"]
        )
    except (TypeError, ValueError) as error:
        raise TypeError(
            "recovered_amount must be numeric."
        ) from error

    if recovered_amount < 0:
        raise ValueError(
            "recovered_amount cannot be negative."
        )

    normalized = dict(
        ground_truth
    )

    normalized[
        "actual_recovery"
    ] = actual_recovery

    normalized[
        "recovered_amount"
    ] = recovered_amount

    return normalized


# ============================================================
# DETERMINISTIC FALLBACK
# ============================================================

def deterministic_recovery_check(
    transaction_id: str,
    action_id: str,
    action: str,
) -> bool:
    """
    Deterministically simulate recovery.

    This function exists primarily for:
        - standalone verification
        - backwards compatibility
        - unit tests

    IMPORTANT:

    It is NOT used when dataset ground truth is supplied.
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
        16,
    )

    # Deterministic 70% simulated recovery.
    return (
        value % 100
    ) < 70


# ============================================================
# TIMESTAMP
# ============================================================

def _timestamp() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


# ============================================================
# BASE RESULT
# ============================================================

def _base_result(
    transaction_id: str,
    action_id: str,
    action: str,
) -> dict[str, Any]:

    return {
        "status": "verified",
        "transaction_id": transaction_id,
        "action_id": action_id,
        "action": action,
        "timestamp": _timestamp(),
        "verification_version": (
            VERIFICATION_VERSION
        ),
    }


# ============================================================
# VERIFICATION
# ============================================================

def verify_action(
    action_result: dict[str, Any],
    ground_truth: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Verify the outcome of an Action Engine decision.

    Parameters
    ----------
    action_result:
        Result returned by Action Engine.

    ground_truth:
        Optional payment-event ground truth.

        Expected fields:

            actual_recovery
            recovered_amount

    Verification behaviour
    ----------------------

    If ground_truth is supplied:
        Dataset ground truth is authoritative.

    If ground_truth is not supplied:
        Deterministic fallback is used for recoverable actions.

    Possible verification states:

        RECOVERED
        NOT_RECOVERED
        PENDING
        NOT_EXECUTED

    Revenue is counted as recovered only when the
    verification result confirms recovery.
    """

    # --------------------------------------------------------
    # Validate action result
    # --------------------------------------------------------

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
    # Validate ground truth when supplied
    # --------------------------------------------------------

    normalized_ground_truth = None

    if ground_truth is not None:

        normalized_ground_truth = (
            validate_ground_truth(
                ground_truth
            )
        )

    # ========================================================
    # ACTION NOT EXECUTED
    # ========================================================

    if not executed:

        result = _base_result(
            transaction_id,
            action_id,
            action,
        )

        result.update({

            "verification_status":
                "NOT_RECOVERED",

            "recovered":
                False,

            "revenue_recovered":
                0.0,

            "amount_at_risk":
                amount,

            "ground_truth":
                normalized_ground_truth,

            "actual_recovery":
                (
                    normalized_ground_truth[
                        "actual_recovery"
                    ]
                    if normalized_ground_truth
                    is not None
                    else None
                ),

            "actual_recovered_amount":
                (
                    normalized_ground_truth[
                        "recovered_amount"
                    ]
                    if normalized_ground_truth
                    is not None
                    else 0.0
                ),

            "reason":
                "Recovery action was not executed.",
        })

        return result

    # ========================================================
    # PENDING / DOWNSTREAM ACTION
    # ========================================================

    if action in PENDING_ACTIONS:

        result = _base_result(
            transaction_id,
            action_id,
            action,
        )

        actual_recovery = None
        actual_recovered_amount = 0.0

        if normalized_ground_truth is not None:

            actual_recovery = (
                normalized_ground_truth[
                    "actual_recovery"
                ]
            )

            actual_recovered_amount = (
                normalized_ground_truth[
                    "recovered_amount"
                ]
            )

        result.update({

            "verification_status":
                "PENDING",

            "recovered":
                False,

            "revenue_recovered":
                0.0,

            "amount_at_risk":
                amount,

            "ground_truth":
                normalized_ground_truth,

            "actual_recovery":
                actual_recovery,

            "actual_recovered_amount":
                actual_recovered_amount,

            "reason":
                "Action requires downstream human "
                "or external verification.",
        })

        return result

    # ========================================================
    # UNSUPPORTED ACTION
    # ========================================================

    if action not in RECOVERABLE_ACTIONS:

        raise ValueError(
            "Unsupported verification action: "
            + action
        )

    # ========================================================
    # DATASET GROUND TRUTH MODE
    # ========================================================

    if normalized_ground_truth is not None:

        actual_recovery = (
            normalized_ground_truth[
                "actual_recovery"
            ]
        )

        actual_recovered_amount = (
            normalized_ground_truth[
                "recovered_amount"
            ]
        )

        if actual_recovery:

            verification_status = (
                "RECOVERED"
            )

            recovered = True

            revenue_recovered = (
                actual_recovered_amount
            )

            reason = (
                "Payment recovery confirmed "
                "by supplied ground truth."
            )

        else:

            verification_status = (
                "NOT_RECOVERED"
            )

            recovered = False

            revenue_recovered = 0.0

            reason = (
                "Action executed but supplied "
                "ground truth indicates that "
                "payment was not recovered."
            )

        result = _base_result(
            transaction_id,
            action_id,
            action,
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

            "ground_truth":
                normalized_ground_truth,

            "actual_recovery":
                actual_recovery,

            "actual_recovered_amount":
                actual_recovered_amount,

            "verification_source":
                "dataset_ground_truth",

            "reason":
                reason,
        })

        return result

    # ========================================================
    # DETERMINISTIC FALLBACK MODE
    # ========================================================

    recovered = deterministic_recovery_check(
        transaction_id,
        action_id,
        action,
    )

    if recovered:

        verification_status = (
            "RECOVERED"
        )

        revenue_recovered = amount

        actual_recovery = True

        actual_recovered_amount = amount

        reason = (
            "Payment recovery confirmed by "
            "deterministic simulation fallback."
        )

    else:

        verification_status = (
            "NOT_RECOVERED"
        )

        revenue_recovered = 0.0

        actual_recovery = False

        actual_recovered_amount = 0.0

        reason = (
            "Recovery action executed but "
            "deterministic simulation indicates "
            "payment was not recovered."
        )

    result = _base_result(
        transaction_id,
        action_id,
        action,
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

        "ground_truth":
            None,

        "actual_recovery":
            actual_recovery,

        "actual_recovered_amount":
            actual_recovered_amount,

        "verification_source":
            "deterministic_fallback",

        "reason":
            reason,
    })

    return result


# ============================================================
# PERSISTENCE
# ============================================================

def save_verification_result(
    result: dict[str, Any],
) -> str:
    """
    Persist one verification result as JSON.
    """

    if not isinstance(
        result,
        dict,
    ):
        raise TypeError(
            "result must be a dictionary."
        )

    if "transaction_id" not in result:

        raise ValueError(
            "Verification result missing "
            "transaction_id."
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
        exist_ok=True,
    )

    path = os.path.join(
        VERIFICATION_DIR,
        f"{transaction_id}.json",
    )

    with open(
        path,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            result,
            file,
            indent=2,
            ensure_ascii=False,
            default=str,
        )

    return path


# ============================================================
# DEMO / CLI
# ============================================================

def main() -> dict[str, Any]:

    demo_action_result = {

        "status":
            "success",

        "action_id":
            "ACT_DEMO_001",

        "transaction_id":
            "TXN_DEMO_001",

        "action":
            "RETRY_PAYMENT",

        "executed":
            True,

        "simulation":
            True,

        "attempt_count_before":
            1,

        "attempt_count_after":
            2,

        "amount":
            5000.0,
    }

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
            indent=2,
            ensure_ascii=False,
        )
    )

    return result


if __name__ == "__main__":
    main()