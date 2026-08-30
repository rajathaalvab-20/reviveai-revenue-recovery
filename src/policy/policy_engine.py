import json
import math
import os
from datetime import datetime, timezone


# ============================================================
# REVIVEAI - POLICY / GUARDRAIL ENGINE
# ============================================================
#
# Purpose:
#   Decide whether an automatic recovery action is authorized.
#
# Pipeline:
#
#   Risk Detector
#        ↓
#   Diagnosis
#        ↓
#   Policy / Guardrails
#        ↓
#   Action Engine
#        ↓
#   Verification
#
# IMPORTANT:
#   The policy engine NEVER executes payments.
#   It only authorizes or blocks an action.
#
# Design principles:
#   1. Fail closed
#   2. Explicit guardrails
#   3. Deterministic decisions
#   4. Independent action authorization
#   5. Auditability
#   6. Strong input validation
#   7. No automatic recovery for hard failures
#   8. Explicit applicability of every guardrail
# ============================================================


# ============================================================
# CONFIGURATION
# ============================================================

POLICY_VERSION = "V1"

MIN_RECOVERY_PROBABILITY = 0.50

MAX_RETRY_ATTEMPTS = 3

MAX_AUTO_RECOVERY_AMOUNT = 50000.0


# ============================================================
# ACTION POLICY
# ============================================================

ALLOWED_ACTIONS = {
    "TRANSIENT": "RETRY_PAYMENT",
    "CUSTOMER_ACTION_REQUIRED": "REQUEST_PAYMENT_METHOD_UPDATE",
    "HARD_FAILURE": "ESCALATE",
}


SUPPORTED_ACTIONS = {
    "RETRY_PAYMENT",
    "REQUEST_PAYMENT_METHOD_UPDATE",
    "ESCALATE",
    "HUMAN_REVIEW",
}


# ============================================================
# FAILURE TAXONOMY
# ============================================================

TRANSIENT_FAILURES = {
    "BANK_TIMEOUT",
    "NETWORK_ERROR",
    "GATEWAY_TIMEOUT",
    "BANK_SERVER_ERROR",
}


CUSTOMER_ACTION_FAILURES = {
    "INSUFFICIENT_FUNDS",
    "EXPIRED_CARD",
    "AUTHENTICATION_FAILED",
}


HARD_FAILURES = {
    "INVALID_CARD",
    "CARD_BLOCKED",
    "FRAUD_SUSPECTED",
}


# ============================================================
# AUDIT STORAGE
# ============================================================

AUDIT_DIR = os.path.join(
    "src",
    "policy",
    "audit",
)

os.makedirs(
    AUDIT_DIR,
    exist_ok=True,
)


# ============================================================
# NUMERIC VALIDATION HELPERS
# ============================================================

def _is_finite_number(value):
    """
    Return True only when value can safely be interpreted
    as a finite numeric value.

    Rejects:
        NaN
        +inf
        -inf
        non-numeric values
    """

    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return False

    return math.isfinite(number)


def _parse_probability(value):
    """
    Safely validate recovery probability.
    """

    if not _is_finite_number(value):
        raise ValueError(
            "recovery_probability must be a finite number."
        )

    probability = float(value)

    if not 0.0 <= probability <= 1.0:
        raise ValueError(
            "recovery_probability must be between 0 and 1."
        )

    return probability


def _parse_amount(value):
    """
    Safely validate transaction amount.
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
    Safely validate retry attempt count.

    Requirements:
        - must be finite
        - must be an integer
        - must be >= 0
        - bool is rejected
        - NaN / infinity are rejected
        - fractional values are rejected

    Examples of invalid values:
        1.5
        2.2
        NaN
        +inf
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

    # Check finiteness BEFORE calling int().
    #
    # This prevents:
    #
    #     int(float("inf"))
    #
    # from raising OverflowError.
    if not _is_finite_number(value):
        raise ValueError(
            "attempt_count must be a non-negative integer."
        )

    try:
        numeric_value = float(value)
    except (TypeError, ValueError, OverflowError):
        raise ValueError(
            "attempt_count must be a non-negative integer."
        )

    try:
        attempts = int(value)
    except (TypeError, ValueError, OverflowError):
        raise ValueError(
            "attempt_count must be a non-negative integer."
        )

    # Reject fractional values such as 1.5.
    if numeric_value != attempts:
        raise ValueError(
            "attempt_count must be a non-negative integer."
        )

    if attempts < 0:
        raise ValueError(
            "attempt_count cannot be negative."
        )

    return attempts


# ============================================================
# INPUT VALIDATION
# ============================================================

def validate_input(data):
    """
    Validate policy input.

    Required fields:

        transaction_id
        recovery_probability
        failure_code
        failure_type
        attempt_count
        amount

    requested_action is optional for backward compatibility.

    When supplied, requested_action is independently checked
    against the policy-derived action.
    """

    if not isinstance(data, dict):
        raise TypeError(
            "Policy input must be a dictionary."
        )

    required = [
        "transaction_id",
        "recovery_probability",
        "failure_code",
        "failure_type",
        "attempt_count",
        "amount",
    ]

    missing = [
        field
        for field in required
        if field not in data
    ]

    if missing:
        raise ValueError(
            "Missing required fields: "
            + ", ".join(missing)
        )

    # --------------------------------------------------------
    # Transaction ID
    # --------------------------------------------------------

    transaction_id = str(
        data["transaction_id"]
    ).strip()

    if not transaction_id:
        raise ValueError(
            "transaction_id cannot be empty."
        )

    # --------------------------------------------------------
    # Probability
    # --------------------------------------------------------

    probability = _parse_probability(
        data["recovery_probability"]
    )

    # --------------------------------------------------------
    # Amount
    # --------------------------------------------------------

    amount = _parse_amount(
        data["amount"]
    )

    # --------------------------------------------------------
    # Attempt count
    # --------------------------------------------------------

    attempts = _parse_attempt_count(
        data["attempt_count"]
    )

    # --------------------------------------------------------
    # Failure code
    # --------------------------------------------------------

    failure_code = str(
        data["failure_code"]
    ).strip()

    if not failure_code:
        raise ValueError(
            "failure_code cannot be empty."
        )

    # --------------------------------------------------------
    # Failure type
    # --------------------------------------------------------

    failure_type = str(
        data["failure_type"]
    ).strip()

    if not failure_type:
        raise ValueError(
            "failure_type cannot be empty."
        )

    # --------------------------------------------------------
    # Optional requested action
    # --------------------------------------------------------

    requested_action = None

    if "requested_action" in data:

        requested_action = str(
            data["requested_action"]
        ).strip()

        if not requested_action:
            raise ValueError(
                "requested_action cannot be empty."
            )

    return {
        "transaction_id": transaction_id,
        "recovery_probability": probability,
        "failure_code": failure_code,
        "failure_type": failure_type,
        "attempt_count": attempts,
        "amount": amount,
        "requested_action": requested_action,
    }


# ============================================================
# FAILURE CLASSIFICATION
# ============================================================

def determine_action(
    failure_type,
    failure_code,
):
    """
    Determine the policy-permitted action.

    Failure code takes precedence over failure type because
    the concrete failure code is more specific.
    """

    if failure_code in TRANSIENT_FAILURES:
        return "RETRY_PAYMENT"

    if failure_code in CUSTOMER_ACTION_FAILURES:
        return "REQUEST_PAYMENT_METHOD_UPDATE"

    if failure_code in HARD_FAILURES:
        return "ESCALATE"

    return ALLOWED_ACTIONS.get(
        failure_type,
        "HUMAN_REVIEW",
    )


def is_supported_failure(failure_code):
    """
    Return True when the failure code belongs to the
    explicitly supported failure taxonomy.
    """

    return (
        failure_code in TRANSIENT_FAILURES
        or failure_code in CUSTOMER_ACTION_FAILURES
        or failure_code in HARD_FAILURES
    )


# ============================================================
# POLICY EVALUATION
# ============================================================

def evaluate_policy(data):
    """
    Evaluate a payment recovery request.

    Possible decisions:

        APPROVED
        BLOCKED

    The policy engine NEVER executes an action.

    Important:
        ESCALATE is an approved routing decision.
        It does not authorize an automatic payment recovery.
    """

    validated = validate_input(data)

    transaction_id = validated[
        "transaction_id"
    ]

    probability = validated[
        "recovery_probability"
    ]

    failure_code = validated[
        "failure_code"
    ]

    failure_type = validated[
        "failure_type"
    ]

    attempt_count = validated[
        "attempt_count"
    ]

    amount = validated[
        "amount"
    ]

    supplied_action = validated[
        "requested_action"
    ]

    # ========================================================
    # INDEPENDENT ACTION DETERMINATION
    # ========================================================

    expected_action = determine_action(
        failure_type,
        failure_code,
    )

    if supplied_action is None:
        requested_action = expected_action
    else:
        requested_action = supplied_action

    # ========================================================
    # DECISION STATE
    # ========================================================

    checks = []

    decision = "APPROVED"

    reason = (
        "All applicable policy guardrails passed."
    )

    def block(message):
        """
        Fail-closed blocking mechanism.

        The first blocking reason is retained for auditability.
        """

        nonlocal decision
        nonlocal reason

        if decision == "APPROVED":
            decision = "BLOCKED"
            reason = message

    # ========================================================
    # GUARDRAIL 1
    # SUPPORTED FAILURE
    # ========================================================

    supported = is_supported_failure(
        failure_code
    )

    checks.append(
        {
            "check": "supported_failure",
            "passed": supported,
            "applicable": True,
        }
    )

    if not supported:
        block(
            "Unsupported failure code."
        )

    # ========================================================
    # GUARDRAIL 2
    # RECOVERY PROBABILITY
    # ========================================================
    #
    # Recovery probability is required for AUTOMATIC
    # recovery actions.
    #
    # ESCALATE does not require recovery probability because
    # escalation does not execute a recovery attempt.
    # ========================================================

    probability_applicable = (
        requested_action != "ESCALATE"
    )

    probability_ok = (
        probability
        >= MIN_RECOVERY_PROBABILITY
    )

    probability_guardrail_passed = (
        probability_ok
        if probability_applicable
        else True
    )

    checks.append(
        {
            "check": "minimum_recovery_probability",
            "passed": probability_guardrail_passed,
            "applicable": probability_applicable,
            "value": probability,
            "threshold": MIN_RECOVERY_PROBABILITY,
            "reason": (
                "Recovery probability meets threshold."
                if probability_applicable
                and probability_ok
                else
                "Recovery probability below automatic-recovery threshold."
                if probability_applicable
                else
                "Not applicable to escalation."
            ),
        }
    )

    if (
        probability_applicable
        and not probability_ok
    ):
        block(
            "Recovery probability below "
            "automatic-recovery threshold."
        )

    # ========================================================
    # GUARDRAIL 3
    # RETRY LIMIT
    # ========================================================
    #
    # Retry limit applies only to RETRY_PAYMENT.
    #
    # Other actions do not consume payment retry attempts.
    # ========================================================

    retry_applicable = (
        requested_action == "RETRY_PAYMENT"
    )

    retry_limit_ok = (
        attempt_count < MAX_RETRY_ATTEMPTS
    )

    retry_guardrail_passed = (
        retry_limit_ok
        if retry_applicable
        else True
    )

    checks.append(
        {
            "check": "retry_limit",
            "passed": retry_guardrail_passed,
            "applicable": retry_applicable,
            "attempt_count": attempt_count,
            "maximum": MAX_RETRY_ATTEMPTS,
            "reason": (
                "Retry attempt limit satisfied."
                if retry_applicable
                and retry_limit_ok
                else
                "Maximum retry attempts reached."
                if retry_applicable
                else
                "Not applicable to selected action."
            ),
        }
    )

    if (
        retry_applicable
        and not retry_limit_ok
    ):
        block(
            "Maximum retry attempts reached."
        )

    # ========================================================
    # GUARDRAIL 4
    # AUTOMATIC RECOVERY AMOUNT
    # ========================================================
    #
    # Amount limit applies only when the action can trigger
    # an automatic recovery operation.
    #
    # ESCALATE is excluded because it does not execute money
    # movement.
    # ========================================================

    amount_applicable = (
        requested_action != "ESCALATE"
    )

    amount_ok = (
        amount <= MAX_AUTO_RECOVERY_AMOUNT
    )

    amount_guardrail_passed = (
        amount_ok
        if amount_applicable
        else True
    )

    checks.append(
        {
            "check": "automatic_amount_limit",
            "passed": amount_guardrail_passed,
            "applicable": amount_applicable,
            "amount": amount,
            "maximum": MAX_AUTO_RECOVERY_AMOUNT,
            "reason": (
                "Transaction amount is within automatic recovery limit."
                if amount_applicable
                and amount_ok
                else
                "Transaction exceeds automatic recovery amount limit."
                if amount_applicable
                else
                "Not applicable to escalation."
            ),
        }
    )

    if (
        amount_applicable
        and not amount_ok
    ):
        block(
            "Transaction exceeds automatic "
            "recovery amount limit."
        )

    # ========================================================
    # GUARDRAIL 5
    # ACTION CONSISTENCY
    # ========================================================
    #
    # The action supplied by diagnosis is independently
    # compared with the action independently derived by the
    # policy engine.
    #
    # This prevents a diagnosis component from requesting an
    # action that conflicts with the policy taxonomy.
    # ========================================================

    action_consistent = (
        requested_action
        == expected_action
    )

    checks.append(
        {
            "check": "action_consistency",
            "passed": action_consistent,
            "applicable": True,
            "requested_action": requested_action,
            "expected_action": expected_action,
        }
    )

    if not action_consistent:
        block(
            "Requested action violates "
            "failure-type policy."
        )

    # ========================================================
    # GUARDRAIL 6
    # HARD FAILURE PROTECTION
    # ========================================================
    #
    # A hard failure is allowed only to ESCALATE.
    #
    # No automatic recovery is permitted for:
    #
    #     INVALID_CARD
    #     CARD_BLOCKED
    #     FRAUD_SUSPECTED
    # ========================================================

    hard_failure = (
        failure_code in HARD_FAILURES
    )

    hard_failure_protection = (
        not hard_failure
        or requested_action == "ESCALATE"
    )

    checks.append(
        {
            "check": "hard_failure_protection",
            "passed": hard_failure_protection,
            "applicable": True,
            "hard_failure": hard_failure,
            "action": requested_action,
        }
    )

    if not hard_failure_protection:
        block(
            "Hard failure cannot be "
            "automatically recovered."
        )

    # ========================================================
    # ACTION VALIDATION
    # ========================================================
    #
    # This is an additional fail-closed check.
    #
    # It is intentionally not added to the six historical
    # guardrails because existing tests expect exactly six
    # guardrails.
    # ========================================================

    action_known = (
        requested_action
        in SUPPORTED_ACTIONS
    )

    if not action_known:
        block(
            "Requested action is not supported."
        )

    # ========================================================
    # FINAL GUARDRAIL STATE
    # ========================================================
    #
    # Only applicable guardrails participate in the final
    # authorization decision.
    #
    # Every guardrail still has a "passed" field so the audit
    # record remains explicit and machine-readable.
    # ========================================================

    guardrails_passed = all(
        check["passed"]
        for check in checks
    )

    if not guardrails_passed:
        decision = "BLOCKED"

        if reason == (
            "All applicable policy guardrails passed."
        ):
            reason = (
                "One or more policy "
                "guardrails failed."
            )

    # ========================================================
    # FINAL SAFETY INVARIANT
    # ========================================================
    #
    # Never allow approval when:
    #
    #   1. action is unknown
    #   2. hard failure is not escalated
    #   3. any guardrail failed
    #
    # This provides an explicit final fail-closed boundary.
    # ========================================================

    if not action_known:
        decision = "BLOCKED"

    if hard_failure and requested_action != "ESCALATE":
        decision = "BLOCKED"

    if not guardrails_passed:
        decision = "BLOCKED"

    # ========================================================
    # FINAL RESULT
    # ========================================================

    result = {
        "status": "success",

        "transaction_id": transaction_id,

        "policy_version": POLICY_VERSION,

        "decision": decision,

        "approved": (
            decision == "APPROVED"
        ),

        "action": requested_action,

        "expected_action": expected_action,

        "reason": reason,

        "recovery_probability": probability,

        "failure_code": failure_code,

        "failure_type": failure_type,

        "attempt_count": attempt_count,

        "amount": amount,

        "guardrails_passed": (
            guardrails_passed
        ),

        "guardrails": checks,

        "timestamp": datetime.now(
            timezone.utc
        ).isoformat(),
    }

    return result


# ============================================================
# AUDIT PERSISTENCE
# ============================================================

def save_audit(result):
    """
    Persist a policy decision as an audit record.

    Returns:
        path to saved JSON file.
    """

    if not isinstance(result, dict):
        raise TypeError(
            "Policy result must be a dictionary."
        )

    if "transaction_id" not in result:
        raise ValueError(
            "Policy result is missing transaction_id."
        )

    transaction_id = str(
        result["transaction_id"]
    ).strip()

    if not transaction_id:
        raise ValueError(
            "transaction_id cannot be empty."
        )

    # --------------------------------------------------------
    # Prevent path traversal
    # --------------------------------------------------------

    safe_transaction_id = os.path.basename(
        transaction_id
    )

    if safe_transaction_id != transaction_id:
        raise ValueError(
            "Invalid transaction_id for audit filename."
        )

    # --------------------------------------------------------
    # Ensure audit directory exists
    # --------------------------------------------------------

    os.makedirs(
        AUDIT_DIR,
        exist_ok=True,
    )

    path = os.path.join(
        AUDIT_DIR,
        f"{safe_transaction_id}.json",
    )

    # --------------------------------------------------------
    # Write audit record
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

    demo_transaction = {
        "transaction_id": "TXN_DEMO_001",

        "recovery_probability": 0.875,

        "failure_code": "BANK_TIMEOUT",

        "failure_type": "TRANSIENT",

        "attempt_count": 1,

        "amount": 5000.0,

        "requested_action": "RETRY_PAYMENT",
    }

    try:

        result = evaluate_policy(
            demo_transaction
        )

        audit_path = save_audit(
            result
        )

        result["audit_file"] = (
            audit_path
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
            "error_type": type(error).__name__,
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