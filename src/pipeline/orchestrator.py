from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from risk_detector import detect_risk
from diagnosis_engine import diagnose_payment
from policy_engine import evaluate_policy, save_audit
from action_engine import execute_action, save_action_result
from verification.verification_engine import (
    verify_action,
    save_verification_result,
)


# ============================================================
# CONFIGURATION
# ============================================================

# IMPORTANT:
# Existing project tests expect V1.
PIPELINE_VERSION = "V1"


RESULT_DIR = os.path.join(
    os.path.dirname(__file__),
    "results",
)

os.makedirs(
    RESULT_DIR,
    exist_ok=True,
)


# ============================================================
# TIMESTAMP
# ============================================================

def _timestamp() -> str:
    """
    Return the current UTC timestamp in ISO-8601 format.
    """
    return datetime.now(
        timezone.utc
    ).isoformat()


# ============================================================
# INPUT VALIDATION
# ============================================================

def validate_payment(
    payment: dict[str, Any],
) -> None:
    """
    Validate the minimum payment structure required by
    the pipeline.

    Ground-truth fields are intentionally NOT required here.

    Normal production pipeline inputs may not contain
    simulation/evaluation ground truth.
    """

    if not isinstance(
        payment,
        dict,
    ):
        raise TypeError(
            "Payment input must be a dictionary."
        )

    transaction_id = payment.get(
        "transaction_id"
    )

    if transaction_id is None:
        raise ValueError(
            "transaction_id is required."
        )

    if not str(
        transaction_id
    ).strip():
        raise ValueError(
            "transaction_id is required."
        )


# ============================================================
# GROUND TRUTH EXTRACTION
# ============================================================

def extract_ground_truth(
    payment: dict[str, Any],
) -> dict[str, Any] | None:
    """
    Extract simulation ground truth from a payment record.

    Ground truth is optional.

    Expected dataset fields:

        actual_recovery
        recovered_amount

    If either field is absent, return None.

    This is important because normal pipeline tests and
    production-style payment events do not necessarily
    contain evaluation labels.
    """

    if not isinstance(
        payment,
        dict,
    ):
        return None

    if (
        "actual_recovery" not in payment
        or "recovered_amount" not in payment
    ):
        return None

    actual_recovery = payment.get(
        "actual_recovery"
    )

    recovered_amount = payment.get(
        "recovered_amount"
    )

    # --------------------------------------------------------
    # Normalize actual_recovery
    # --------------------------------------------------------

    if isinstance(
        actual_recovery,
        bool,
    ):
        normalized_recovery = (
            actual_recovery
        )

    elif isinstance(
        actual_recovery,
        str,
    ):
        normalized_recovery = (
            actual_recovery.strip().lower()
            in {
                "1",
                "true",
                "yes",
                "y",
                "recovered",
            }
        )

    else:
        normalized_recovery = bool(
            actual_recovery
        )

    # --------------------------------------------------------
    # Normalize recovered amount
    # --------------------------------------------------------

    try:
        normalized_amount = float(
            recovered_amount
        )
    except (
        TypeError,
        ValueError,
    ):
        normalized_amount = 0.0

    if normalized_amount < 0:
        normalized_amount = 0.0

    return {
        "actual_recovery":
            normalized_recovery,

        "recovered_amount":
            normalized_amount,
    }


# ============================================================
# MAIN PIPELINE
# ============================================================

def run_pipeline(
    payment: dict[str, Any],
) -> dict[str, Any]:
    """
    Execute the complete ReviveAI recovery pipeline.

    Stages:

        Payment
           |
           v
        Risk Detection
           |
           v
        Diagnosis
           |
           v
        Policy / Guardrails
           |
           +---- BLOCKED ----> Stop
           |
           v
        Action Execution
           |
           v
        Verification
           |
           v
        Final Status

    Important safety properties:

    1. Policy approval is an absolute action gate.
    2. No action is executed when policy approval is false.
    3. Verification is never called for a non-executed action.
    4. Ground truth is optional for normal pipeline execution.
    5. Dataset ground truth is passed to verification when available.
    """

    # ========================================================
    # INPUT VALIDATION
    # ========================================================

    validate_payment(
        payment
    )

    transaction_id = str(
        payment["transaction_id"]
    ).strip()

    started_at = _timestamp()

    pipeline: dict[str, Any] = {

        "status":
            "started",

        "pipeline_version":
            PIPELINE_VERSION,

        "transaction_id":
            transaction_id,

        "started_at":
            started_at,
    }

    try:

        # ====================================================
        # 1. RISK DETECTION
        # ====================================================

        risk_result = detect_risk(
            payment
        )

        if not isinstance(
            risk_result,
            dict,
        ):
            raise RuntimeError(
                "Risk detection returned "
                "an invalid result."
            )

        if risk_result.get(
            "status"
        ) != "success":
            raise RuntimeError(
                "Risk detection failed."
            )

        pipeline[
            "risk"
        ] = risk_result

        # ====================================================
        # 2. DIAGNOSIS
        # ====================================================

        diagnosis_result = diagnose_payment(
            payment
        )

        if not isinstance(
            diagnosis_result,
            dict,
        ):
            raise RuntimeError(
                "Diagnosis engine returned "
                "an invalid result."
            )

        if diagnosis_result.get(
            "status"
        ) != "success":
            raise RuntimeError(
                "Diagnosis failed."
            )

        pipeline[
            "diagnosis"
        ] = diagnosis_result

        # ====================================================
        # 3. POLICY / GUARDRAILS
        # ====================================================

        policy_input = {

            "transaction_id":
                transaction_id,

            "recovery_probability":
                risk_result[
                    "recovery_probability"
                ],

            "failure_code":
                diagnosis_result[
                    "failure_code"
                ],

            "failure_type":
                diagnosis_result[
                    "failure_type"
                ],

            "attempt_count":
                diagnosis_result[
                    "attempt_count"
                ],

            "amount":
                float(
                    payment.get(
                        "amount",
                        0.0,
                    )
                ),
        }

        policy_result = evaluate_policy(
            policy_input
        )

        if not isinstance(
            policy_result,
            dict,
        ):
            raise RuntimeError(
                "Policy engine returned "
                "an invalid result."
            )

        # ----------------------------------------------------
        # Save policy audit
        # ----------------------------------------------------

        audit_file = save_audit(
            policy_result
        )

        policy_result[
            "audit_file"
        ] = audit_file

        pipeline[
            "policy"
        ] = policy_result

        # ====================================================
        # 4. ABSOLUTE ACTION GATE
        # ====================================================

        approved = bool(
            policy_result.get(
                "approved",
                False,
            )
        )

        # ----------------------------------------------------
        # Policy BLOCK
        # ----------------------------------------------------

        if not approved:

            pipeline[
                "action"
            ] = {

                "status":
                    "blocked",

                "executed":
                    False,

                "transaction_id":
                    transaction_id,

                "reason":
                    "Action blocked by "
                    "policy engine.",
            }

            # ------------------------------------------------
            # Verification is NOT run because no action
            # was executed.
            # ------------------------------------------------

            pipeline[
                "verification"
            ] = {

                "status":
                    "not_executed",

                "verification_status":
                    "NOT_RECOVERED",

                "verified":
                    False,

                "recovered":
                    False,

                "revenue_recovered":
                    0.0,

                "amount_at_risk":
                    float(
                        payment.get(
                            "amount",
                            0.0,
                        )
                    ),

                "reason":
                    "Verification skipped "
                    "because action was blocked.",
            }

            pipeline[
                "status"
            ] = "blocked"

            pipeline[
                "completed_at"
            ] = _timestamp()

            return save_pipeline_result(
                pipeline
            )

        # ====================================================
        # 5. ACTION EXECUTION
        # ====================================================

        action_result = execute_action(
            policy_result
        )

        if not isinstance(
            action_result,
            dict,
        ):
            raise RuntimeError(
                "Action engine returned "
                "an invalid result."
            )

        # ----------------------------------------------------
        # Persist action result
        # ----------------------------------------------------

        action_file = save_action_result(
            action_result
        )

        action_result[
            "result_file"
        ] = action_file

        pipeline[
            "action"
        ] = action_result

        # ====================================================
        # 6. CHECK WHETHER ACTION WAS ACTUALLY EXECUTED
        # ====================================================

        executed = bool(
            action_result.get(
                "executed",
                False,
            )
        )

        # ----------------------------------------------------
        # CRITICAL:
        #
        # If the action was not executed, verification MUST
        # NOT be called.
        #
        # This preserves the safety boundary:
        #
        #     no execution -> no verification
        #
        # It also prevents compatibility problems with tests
        # that intentionally replace verify_action() with a
        # function that accepts only action_result.
        # ----------------------------------------------------

        if not executed:

            pipeline[
                "verification"
            ] = {

                "status":
                    "not_executed",

                "verification_status":
                    "NOT_RECOVERED",

                "verified":
                    False,

                "recovered":
                    False,

                "revenue_recovered":
                    0.0,

                "amount_at_risk":
                    float(
                        action_result.get(
                            "amount",
                            payment.get(
                                "amount",
                                0.0,
                            ),
                        )
                    ),

                "reason":
                    "Verification skipped "
                    "because action was not executed.",
            }

            pipeline[
                "status"
            ] = "not_recovered"

            pipeline[
                "completed_at"
            ] = _timestamp()

            return save_pipeline_result(
                pipeline
            )

        # ====================================================
        # 7. EXTRACT OPTIONAL GROUND TRUTH
        # ====================================================

        ground_truth = extract_ground_truth(
            payment
        )

        # ====================================================
        # 8. VERIFY EXECUTED ACTION
        # ====================================================

        # ----------------------------------------------------
        # Ground truth is passed only when it exists.
        #
        # This supports:
        #
        #   - simulation datasets
        #   - evaluation
        #   - normal pipeline tests
        #   - production-style inputs
        # ----------------------------------------------------

        if ground_truth is not None:

            verification_result = verify_action(
                action_result,
                ground_truth=ground_truth,
            )

        else:

            # ------------------------------------------------
            # Compatibility path:
            #
            # Existing unit tests may monkeypatch verify_action
            # with a one-argument function.
            #
            # The verification engine itself handles the
            # deterministic fallback when ground truth is
            # absent.
            # ------------------------------------------------

            verification_result = verify_action(
                action_result
            )

        if not isinstance(
            verification_result,
            dict,
        ):
            raise RuntimeError(
                "Verification engine returned "
                "an invalid result."
            )

        # ----------------------------------------------------
        # Persist verification result
        # ----------------------------------------------------

        verification_file = (
            save_verification_result(
                verification_result
            )
        )

        verification_result[
            "result_file"
        ] = verification_file

        pipeline[
            "verification"
        ] = verification_result

        # ====================================================
        # 9. FINAL STATUS
        # ====================================================

        if verification_result.get(
            "recovered",
            False,
        ):

            pipeline[
                "status"
            ] = "recovered"

        else:

            pipeline[
                "status"
            ] = "not_recovered"

        pipeline[
            "completed_at"
        ] = _timestamp()

        return save_pipeline_result(
            pipeline
        )

    # ========================================================
    # INPUT VALIDATION ERRORS
    # ========================================================

    except (
        ValueError,
        TypeError,
    ):

        # ----------------------------------------------------
        # Preserve validation exception types.
        #
        # Important for:
        #
        #   - unit tests
        #   - callers
        #   - debugging
        #   - security validation
        # ----------------------------------------------------

        raise

    # ========================================================
    # UNEXPECTED SYSTEM ERRORS
    # ========================================================

    except Exception as error:

        pipeline[
            "status"
        ] = "failed"

        pipeline[
            "error"
        ] = {

            "error_type":
                type(error).__name__,

            "error":
                str(error),
        }

        pipeline[
            "completed_at"
        ] = _timestamp()

        return save_pipeline_result(
            pipeline,
            raise_error=True,
        )


# ============================================================
# PIPELINE RESULT PERSISTENCE
# ============================================================

def save_pipeline_result(
    result: dict[str, Any],
    raise_error: bool = False,
) -> dict[str, Any]:
    """
    Persist the complete pipeline result.

    One JSON file is created per transaction.
    """

    transaction_id = str(
        result[
            "transaction_id"
        ]
    )

    path = os.path.join(
        RESULT_DIR,
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

    result[
        "pipeline_result_file"
    ] = path

    # --------------------------------------------------------
    # Re-raise unexpected errors after persistence.
    # --------------------------------------------------------

    if raise_error:

        error = result.get(
            "error",
            {},
        )

        raise RuntimeError(
            f"{error.get('error_type', 'RuntimeError')}: "
            f"{error.get('error', 'Unknown pipeline error')}"
        )

    return result


# ============================================================
# DEMO EXECUTION
# ============================================================

if __name__ == "__main__":

    demo_payment = {

        "transaction_id":
            "TXN_PIPELINE_001",

        "amount":
            5000.0,

        "payment_method":
            "CARD",

        "customer_type":
            "RETURNING",

        "customer_age_days":
            240,

        "previous_transactions":
            25,

        "previous_success_rate":
            0.92,

        "failure_code":
            "BANK_TIMEOUT",

        "failure_type":
            "TRANSIENT",

        "attempt_count":
            1,

        "time_since_failure_min":
            10,

        "hour_of_day":
            14,

        "is_weekend":
            0,
    }

    try:

        result = run_pipeline(
            demo_payment
        )

        print(
            json.dumps(
                result,
                indent=2,
                ensure_ascii=False,
                default=str,
            )
        )

    except Exception as error:

        print(
            json.dumps(
                {
                    "status":
                        "error",

                    "error_type":
                        type(error).__name__,

                    "error":
                        str(error),
                },
                indent=2,
                ensure_ascii=False,
            )
        )

        raise
