import json
import math
import os
import uuid
from datetime import datetime, timezone


# ============================================================
# REVIVEAI - ACTION ENGINE
# ============================================================
#
# Purpose:
#   Execute an action that has already been authorized by the
#   Policy / Guardrail Engine.
#
# Pipeline:
#
#   Risk Detector
#        |
#        v
#   Diagnosis
#        |
#        v
#   Policy / Guardrails
#        |
#        v
#   ACTION ENGINE
#        |
#        v
#   Verification
#
# IMPORTANT:
#
#   The Action Engine NEVER overrides policy decisions.
#
#   It does NOT:
#       - calculate recovery probability
#       - determine whether an action is safe
#       - bypass policy
#       - execute real payments
#       - modify policy decisions
#
#   This implementation uses simulated actions only.
#
# Design principles:
#
#   1. Fail closed
#   2. Strong input validation
#   3. Policy decision integrity
#   4. No action inference
#   5. Retry protection
#   6. Finite numeric validation
#   7. Path traversal protection
#   8. Auditability
#   9. Deterministic execution logic
#  10. No external money movement
#  11. Defensive validation of persisted results
# ============================================================


# ============================================================
# CONFIGURATION
# ============================================================

ACTION_VERSION = "V2"

MAX_RETRY_ATTEMPTS = 3

ACTION_DIR = os.path.join(
    "src",
    "actions",
    "results",
)


# ============================================================
# SUPPORTED ACTIONS
# ============================================================

SUPPORTED_ACTIONS = frozenset(
    {
        "RETRY_PAYMENT",
        "PAYMENT_REMINDER",
        "REQUEST_PAYMENT_METHOD_UPDATE",
        "ESCALATE",
        "HUMAN_REVIEW",
    }
)


SUPPORTED_DECISIONS = frozenset(
    {
        "APPROVED",
        "BLOCKED",
    }
)


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def _is_finite_number(value):
    """
    Return True only if value can safely be converted to
    a finite float.

    Rejects:
        NaN
        +inf
        -inf
        invalid strings
        None
        arbitrary objects
    """

    try:
        number = float(value)
    except (
        TypeError,
        ValueError,
        OverflowError,
    ):
        return False

    return math.isfinite(number)


def _parse_amount(value):
    """
    Validate and normalize transaction amount.

    Amount must be:
        - numeric
        - finite
        - non-negative
    """

    if not _is_finite_number(value):
        raise ValueError(
            "amount must be a finite number."
        )

    amount = float(value)

    if amount < 0:
        raise ValueError(
            "amount cannot be negative."
        )

    return amount


def _parse_attempt_count(value):
    """
    Validate and normalize retry attempt count.

    Requirements:
        - integer
        - finite
        - non-negative
        - bool rejected explicitly

    Examples rejected:
        1.5
        2.2
        NaN
        inf
        -inf
        "invalid"
        None
        []
        {}
        True
        False
    """

    if isinstance(value, bool):
        raise ValueError(
            "attempt_count must be a non-negative integer."
        )

    try:
        numeric_value = float(value)
    except (
        TypeError,
        ValueError,
        OverflowError,
    ):
        raise ValueError(
            "attempt_count must be a non-negative integer."
        )

    if not math.isfinite(numeric_value):
        raise ValueError(
            "attempt_count must be a non-negative integer."
        )

    if not numeric_value.is_integer():
        raise ValueError(
            "attempt_count must be a non-negative integer."
        )

    attempts = int(numeric_value)

    if attempts < 0:
        raise ValueError(
            "attempt_count cannot be negative."
        )

    return attempts


def _validate_transaction_id(value):
    """
    Validate transaction ID before it is used in an audit
    filename.

    Prevents:
        - empty IDs
        - path traversal
        - absolute paths
        - directory separators
    """

    if value is None:
        raise ValueError(
            "transaction_id cannot be empty."
        )

    transaction_id = str(value).strip()

    if not transaction_id:
        raise ValueError(
            "transaction_id cannot be empty."
        )

    # Reject Windows and Unix path separators.
    if "/" in transaction_id or "\\" in transaction_id:
        raise ValueError(
            "Invalid transaction_id."
        )

    # Reject special path components.
    if transaction_id in {
        ".",
        "..",
    }:
        raise ValueError(
            "Invalid transaction_id."
        )

    # Additional basename protection.
    if os.path.basename(transaction_id) != transaction_id:
        raise ValueError(
            "Invalid transaction_id."
        )

    return transaction_id


def _create_action_id():
    """
    Generate a unique action identifier.
    """

    return (
        "ACT_"
        + uuid.uuid4().hex[:12].upper()
    )


def _utc_timestamp():
    """
    Return an ISO-8601 UTC timestamp.
    """

    return datetime.now(
        timezone.utc
    ).isoformat()


# ============================================================
# POLICY RESULT VALIDATION
# ============================================================

def validate_policy_result(policy_result):
    """
    Validate the complete policy result before execution.

    This is a security boundary.

    The Action Engine must reject malformed or contradictory
    policy results before performing any action.
    """

    # --------------------------------------------------------
    # Top-level type
    # --------------------------------------------------------

    if not isinstance(
        policy_result,
        dict,
    ):
        raise TypeError(
            "Policy result must be a dictionary."
        )

    # --------------------------------------------------------
    # Required fields
    # --------------------------------------------------------

    required = [
        "transaction_id",
        "decision",
        "approved",
        "action",
        "attempt_count",
        "amount",
    ]

    missing = [
        field
        for field in required
        if field not in policy_result
    ]

    if missing:
        raise ValueError(
            "Policy result missing fields: "
            + ", ".join(missing)
        )

    # --------------------------------------------------------
    # Transaction ID
    # --------------------------------------------------------

    transaction_id = _validate_transaction_id(
        policy_result["transaction_id"]
    )

    # --------------------------------------------------------
    # Decision
    # --------------------------------------------------------

    decision = policy_result["decision"]

    if decision not in SUPPORTED_DECISIONS:
        raise ValueError(
            "Invalid policy decision."
        )

    # --------------------------------------------------------
    # Approved field
    # --------------------------------------------------------

    approved = policy_result["approved"]

    if not isinstance(
        approved,
        bool,
    ):
        raise TypeError(
            "Policy approved field must be boolean."
        )

    # --------------------------------------------------------
    # Decision / approved consistency
    # --------------------------------------------------------
    #
    # Security invariant:
    #
    #   APPROVED + True
    #       -> valid
    #
    #   APPROVED + False
    #       -> invalid
    #
    #   BLOCKED + False
    #       -> valid
    #
    #   BLOCKED + True
    #       -> invalid
    #
    # Never silently repair a contradictory policy result.
    # --------------------------------------------------------

    expected_approved = (
        decision == "APPROVED"
    )

    if approved != expected_approved:
        raise ValueError(
            "Policy decision and approved field are inconsistent."
        )

    # --------------------------------------------------------
    # Action
    # --------------------------------------------------------

    action = policy_result["action"]

    if not isinstance(
        action,
        str,
    ):
        raise TypeError(
            "Policy action must be a string."
        )

    action = action.strip()

    if action not in SUPPORTED_ACTIONS:
        raise ValueError(
            "Unsupported recovery action: "
            + str(action)
        )

    # --------------------------------------------------------
    # Attempt count
    # --------------------------------------------------------

    attempt_count = _parse_attempt_count(
        policy_result["attempt_count"]
    )

    # --------------------------------------------------------
    # Amount
    # --------------------------------------------------------

    amount = _parse_amount(
        policy_result["amount"]
    )

    # --------------------------------------------------------
    # Return normalized validation result
    # --------------------------------------------------------

    return {
        "transaction_id": transaction_id,
        "decision": decision,
        "approved": approved,
        "action": action,
        "attempt_count": attempt_count,
        "amount": amount,
    }


# ============================================================
# BLOCKED RESULT
# ============================================================

def _blocked_result(
    transaction_id,
    action,
    reason,
    action_id=None,
):
    """
    Construct a consistent blocked-action result.
    """

    if action_id is None:
        action_id = _create_action_id()

    return {
        "status": "blocked",
        "action_id": action_id,
        "transaction_id": transaction_id,
        "action": action,
        "executed": False,
        "reason": reason,
        "timestamp": _utc_timestamp(),
        "action_version": ACTION_VERSION,
    }


# ============================================================
# EXECUTION
# ============================================================

def execute_action(policy_result):
    """
    Execute a policy-authorized recovery action.

    The function is deliberately conservative:

        invalid input
            -> exception

        contradictory policy
            -> exception

        blocked policy
            -> blocked result

        retry limit reached
            -> blocked result

        approved supported action
            -> simulated execution

    No real payment API is called.
    """

    validated = validate_policy_result(
        policy_result
    )

    transaction_id = validated[
        "transaction_id"
    ]

    decision = validated[
        "decision"
    ]

    approved = validated[
        "approved"
    ]

    action = validated[
        "action"
    ]

    attempt_count = validated[
        "attempt_count"
    ]

    amount = validated[
        "amount"
    ]

    action_id = _create_action_id()

    timestamp = _utc_timestamp()

    # ========================================================
    # ABSOLUTE POLICY GATE
    # ========================================================
    #
    # This is intentionally redundant with the consistency
    # validation above.
    #
    # Defense in depth:
    # even if future code changes validation behavior,
    # execution still requires explicit approval.
    # ========================================================

    if (
        not approved
        or decision != "APPROVED"
    ):
        return _blocked_result(
            transaction_id=transaction_id,
            action=action,
            reason=(
                "Action blocked by policy engine."
            ),
            action_id=action_id,
        )

    # ========================================================
    # RETRY PAYMENT
    # ========================================================

    if action == "RETRY_PAYMENT":

        if attempt_count >= MAX_RETRY_ATTEMPTS:

            return _blocked_result(
                transaction_id=transaction_id,
                action=action,
                reason=(
                    "Retry limit reached."
                ),
                action_id=action_id,
            )

        new_attempt_count = (
            attempt_count + 1
        )

        return {
            "status": "success",
            "action_id": action_id,
            "transaction_id": transaction_id,
            "action": action,
            "executed": True,
            "simulation": True,
            "attempt_count_before": (
                attempt_count
            ),
            "attempt_count_after": (
                new_attempt_count
            ),
            "amount": amount,
            "message": (
                "Payment retry executed "
                "in simulation."
            ),
            "timestamp": timestamp,
            "action_version": ACTION_VERSION,
        }

    # ========================================================
    # PAYMENT METHOD UPDATE
    # ========================================================

    if action == "REQUEST_PAYMENT_METHOD_UPDATE":

        return {
            "status": "success",
            "action_id": action_id,
            "transaction_id": transaction_id,
            "action": action,
            "executed": True,
            "simulation": True,
            "amount": amount,
            "message": (
                "Customer payment-method "
                "update requested."
            ),
            "timestamp": timestamp,
            "action_version": ACTION_VERSION,
        }

    # ========================================================
    # PAYMENT REMINDER
    # ========================================================

    if action == "PAYMENT_REMINDER":

        return {
            "status": "success",
            "action_id": action_id,
            "transaction_id": transaction_id,
            "action": action,
            "executed": True,
            "simulation": True,
            "amount": amount,
            "message": (
                "Payment reminder generated."
            ),
            "timestamp": timestamp,
            "action_version": ACTION_VERSION,
        }

    # ========================================================
    # ESCALATION
    # ========================================================

    if action == "ESCALATE":

        return {
            "status": "success",
            "action_id": action_id,
            "transaction_id": transaction_id,
            "action": action,
            "executed": True,
            "simulation": True,
            "amount": amount,
            "message": (
                "Transaction escalated "
                "for review."
            ),
            "timestamp": timestamp,
            "action_version": ACTION_VERSION,
        }

    # ========================================================
    # HUMAN REVIEW
    # ========================================================

    if action == "HUMAN_REVIEW":

        return {
            "status": "success",
            "action_id": action_id,
            "transaction_id": transaction_id,
            "action": action,
            "executed": True,
            "simulation": True,
            "amount": amount,
            "message": (
                "Transaction routed to "
                "human review."
            ),
            "timestamp": timestamp,
            "action_version": ACTION_VERSION,
        }

    # ========================================================
    # DEFENSIVE FAIL-CLOSED PROTECTION
    # ========================================================
    #
    # This should be unreachable because action validation
    # happens before execution.
    # ========================================================

    raise RuntimeError(
        "Unexpected action reached execution layer."
    )


# ============================================================
# ACTION RESULT VALIDATION
# ============================================================

def validate_action_result(result):
    """
    Validate an action result before persisting it.

    This protects the audit layer from malformed records.
    """

    if not isinstance(
        result,
        dict,
    ):
        raise TypeError(
            "Action result must be a dictionary."
        )

    required = [
        "status",
        "action_id",
        "transaction_id",
        "action",
        "executed",
        "timestamp",
        "action_version",
    ]

    missing = [
        field
        for field in required
        if field not in result
    ]

    if missing:
        raise ValueError(
            "Action result missing fields: "
            + ", ".join(missing)
        )

    # --------------------------------------------------------
    # Transaction ID
    # --------------------------------------------------------

    _validate_transaction_id(
        result["transaction_id"]
    )

    # --------------------------------------------------------
    # Status
    # --------------------------------------------------------

    if result["status"] not in {
        "success",
        "blocked",
    }:
        raise ValueError(
            "Invalid action result status."
        )

    # --------------------------------------------------------
    # Executed
    # --------------------------------------------------------

    if not isinstance(
        result["executed"],
        bool,
    ):
        raise TypeError(
            "Action result executed field "
            "must be boolean."
        )

    # --------------------------------------------------------
    # Execution/status consistency
    # --------------------------------------------------------

    if (
        result["status"] == "success"
        and result["executed"] is not True
    ):
        raise ValueError(
            "Successful action result must have "
            "executed=True."
        )

    if (
        result["status"] == "blocked"
        and result["executed"] is not False
    ):
        raise ValueError(
            "Blocked action result must have "
            "executed=False."
        )

    # --------------------------------------------------------
    # Action
    # --------------------------------------------------------

    if result["action"] not in SUPPORTED_ACTIONS:
        raise ValueError(
            "Unsupported action in result."
        )

    # --------------------------------------------------------
    # Action ID
    # --------------------------------------------------------

    if not isinstance(
        result["action_id"],
        str,
    ):
        raise TypeError(
            "action_id must be a string."
        )

    if not result["action_id"].strip():
        raise ValueError(
            "action_id cannot be empty."
        )

    # --------------------------------------------------------
    # Timestamp
    # --------------------------------------------------------

    if not isinstance(
        result["timestamp"],
        str,
    ):
        raise TypeError(
            "timestamp must be a string."
        )

    if not result["timestamp"].strip():
        raise ValueError(
            "timestamp cannot be empty."
        )

    # --------------------------------------------------------
    # Action version
    # --------------------------------------------------------

    if not isinstance(
        result["action_version"],
        str,
    ):
        raise TypeError(
            "action_version must be a string."
        )

    if not result["action_version"].strip():
        raise ValueError(
            "action_version cannot be empty."
        )

    return True


# ============================================================
# AUDIT RESULT NORMALIZATION
# ============================================================

def _normalize_audit_result(result):
    """
    Normalize an action result received from the pipeline
    before audit persistence.

    This function ONLY supplies audit metadata that may be
    absent from a mocked or externally produced result.

    It NEVER repairs:
        - decision
        - approval
        - action
        - execution status
        - transaction ID

    Security-critical fields must already be correct.
    """

    if not isinstance(
        result,
        dict,
    ):
        raise TypeError(
            "Action result must be a dictionary."
        )

    normalized = dict(result)

    if not normalized.get(
        "timestamp"
    ):
        normalized["timestamp"] = _utc_timestamp()

    if not normalized.get(
        "action_version"
    ):
        normalized["action_version"] = ACTION_VERSION

    return normalized


# ============================================================
# AUDIT PERSISTENCE
# ============================================================

def save_action_result(result):
    """
    Persist an action result as JSON.

    Path traversal through transaction_id is explicitly
    prevented.

    Minimal mocked results are allowed to receive audit
    metadata through _normalize_audit_result().
    """

    # --------------------------------------------------------
    # Normalize audit-only metadata.
    # --------------------------------------------------------

    result = _normalize_audit_result(
        result
    )

    # --------------------------------------------------------
    # Validate the complete result.
    # --------------------------------------------------------

    validate_action_result(
        result
    )

    # --------------------------------------------------------
    # Validate transaction ID again immediately before
    # filesystem use.
    # --------------------------------------------------------

    transaction_id = _validate_transaction_id(
        result["transaction_id"]
    )

    # --------------------------------------------------------
    # Create output directory.
    # --------------------------------------------------------

    os.makedirs(
        ACTION_DIR,
        exist_ok=True,
    )

    filename = (
        f"{transaction_id}.json"
    )

    path = os.path.join(
        ACTION_DIR,
        filename,
    )

    # --------------------------------------------------------
    # Final path safety check.
    # --------------------------------------------------------

    action_dir_abs = os.path.abspath(
        ACTION_DIR
    )

    path_abs = os.path.abspath(
        path
    )

    if os.path.dirname(
        path_abs
    ) != action_dir_abs:

        raise ValueError(
            "Invalid audit output path."
        )

    # --------------------------------------------------------
    # Write JSON.
    # --------------------------------------------------------

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
        )

    return path


# ============================================================
# DEMO / DIRECT EXECUTION
# ============================================================

if __name__ == "__main__":

    demo_policy_result = {
        "transaction_id": (
            "TXN_DEMO_001"
        ),
        "decision": "APPROVED",
        "approved": True,
        "action": "RETRY_PAYMENT",
        "attempt_count": 1,
        "amount": 5000.0,
    }

    try:

        result = execute_action(
            demo_policy_result
        )

        result["result_file"] = (
            save_action_result(
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

    except Exception as error:

        error_result = {
            "status": "error",
            "error_type": (
                type(error).__name__
            ),
            "error": str(error),
        }

        print(
            json.dumps(
                error_result,
                indent=2,
                ensure_ascii=False,
            )
        )

        raise
