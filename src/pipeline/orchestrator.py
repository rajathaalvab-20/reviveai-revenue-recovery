import json
import os
from datetime import datetime, timezone

from risk_detector import detect_risk
from diagnosis_engine import diagnose_payment
from policy_engine import evaluate_policy, save_audit
from action_engine import execute_action, save_action_result
from verification_engine import verify_action, save_verification_result


PIPELINE_VERSION = "V1"

RESULT_DIR = os.path.join(
    os.path.dirname(__file__),
    "results"
)

os.makedirs(RESULT_DIR, exist_ok=True)


def validate_payment(payment):
    if not isinstance(payment, dict):
        raise TypeError("Payment input must be a dictionary.")

    if not payment.get("transaction_id"):
        raise ValueError("transaction_id is required.")


def run_pipeline(payment):

    validate_payment(payment)

    transaction_id = str(payment["transaction_id"])
    started_at = datetime.now(timezone.utc).isoformat()

    pipeline = {
        "status": "started",
        "pipeline_version": PIPELINE_VERSION,
        "transaction_id": transaction_id,
        "started_at": started_at
    }

    try:

        # ----------------------------------------------------
        # 1. RISK DETECTION
        # ----------------------------------------------------

        risk_result = detect_risk(payment)

        if risk_result.get("status") != "success":
            raise RuntimeError("Risk detection failed.")

        pipeline["risk"] = risk_result

        # ----------------------------------------------------
        # 2. DIAGNOSIS
        # ----------------------------------------------------

        diagnosis_result = diagnose_payment(payment)

        if diagnosis_result.get("status") != "success":
            raise RuntimeError("Diagnosis failed.")

        pipeline["diagnosis"] = diagnosis_result

        # ----------------------------------------------------
        # 3. POLICY / GUARDRAILS
        # ----------------------------------------------------

        policy_input = {
            "transaction_id": transaction_id,
            "recovery_probability": risk_result[
                "recovery_probability"
            ],
            "failure_code": diagnosis_result[
                "failure_code"
            ],
            "failure_type": diagnosis_result[
                "failure_type"
            ],
            "attempt_count": diagnosis_result[
                "attempt_count"
            ],
            "amount": float(payment["amount"])
        }

        policy_result = evaluate_policy(
            policy_input
        )

        audit_file = save_audit(
            policy_result
        )

        policy_result["audit_file"] = audit_file

        pipeline["policy"] = policy_result

        # ----------------------------------------------------
        # 4. ABSOLUTE ACTION GATE
        # ----------------------------------------------------

        if not policy_result["approved"]:

            pipeline["action"] = {
                "status": "blocked",
                "executed": False,
                "reason": "Action blocked by policy engine."
            }

            pipeline["verification"] = {
                "status": "not_executed",
                "verified": False,
                "reason": (
                    "Verification skipped because "
                    "action was blocked."
                )
            }

            pipeline["status"] = "blocked"

            pipeline["completed_at"] = datetime.now(
                timezone.utc
            ).isoformat()

            return save_pipeline_result(
                pipeline
            )

        # ----------------------------------------------------
        # 5. ACTION EXECUTION
        # ----------------------------------------------------

        action_result = execute_action(
            policy_result
        )

        action_file = save_action_result(
            action_result
        )

        action_result["result_file"] = action_file

        pipeline["action"] = action_result

        # ----------------------------------------------------
        # 6. VERIFY ACTION
        # ----------------------------------------------------

        if not action_result.get("executed"):

            pipeline["verification"] = {
                "status": "not_executed",
                "verified": False,
                "reason": "Action was not executed."
            }

            pipeline["status"] = "not_recovered"

            pipeline["completed_at"] = datetime.now(
                timezone.utc
            ).isoformat()

            return save_pipeline_result(
                pipeline
            )

        verification_result = verify_action(
            action_result
        )

        verification_file = save_verification_result(
            verification_result
        )

        verification_result["result_file"] = (
            verification_file
        )

        pipeline["verification"] = (
            verification_result
        )

        # ----------------------------------------------------
        # 7. FINAL STATUS
        # ----------------------------------------------------

        if verification_result.get("recovered"):

            pipeline["status"] = "recovered"

        else:

            pipeline["status"] = "not_recovered"

        pipeline["completed_at"] = datetime.now(
            timezone.utc
        ).isoformat()

        return save_pipeline_result(
            pipeline
        )

    # --------------------------------------------------------
    # INPUT VALIDATION ERRORS
    # --------------------------------------------------------

    except (ValueError, TypeError):

        # Preserve validation exception types.
        # Tests and callers can correctly identify
        # invalid input as ValueError / TypeError.

        raise

    # --------------------------------------------------------
    # UNEXPECTED SYSTEM ERRORS
    # --------------------------------------------------------

    except Exception as error:

        pipeline["status"] = "failed"

        pipeline["error"] = {
            "error_type": type(error).__name__,
            "error": str(error)
        }

        pipeline["completed_at"] = datetime.now(
            timezone.utc
        ).isoformat()

        return save_pipeline_result(
            pipeline,
            raise_error=True
        )


def save_pipeline_result(
    result,
    raise_error=False
):

    transaction_id = result["transaction_id"]

    path = os.path.join(
        RESULT_DIR,
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

    result["pipeline_result_file"] = path

    if raise_error:

        error = result["error"]

        raise RuntimeError(
            f"{error['error_type']}: "
            f"{error['error']}"
        )

    return result


# ============================================================
# DEMO EXECUTION
# ============================================================

if __name__ == "__main__":

    demo_payment = {

        "transaction_id": "TXN_PIPELINE_001",

        "amount": 5000.0,

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

    try:

        result = run_pipeline(
            demo_payment
        )

        print(
            json.dumps(
                result,
                indent=2
            )
        )

    except Exception as error:

        print(
            json.dumps(
                {
                    "status": "error",
                    "error_type": type(error).__name__,
                    "error": str(error)
                },
                indent=2
            )
        )

        raise

