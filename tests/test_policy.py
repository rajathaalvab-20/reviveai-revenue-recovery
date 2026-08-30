import json
import math
import os

import pytest

from policy_engine import (
    evaluate_policy,
    save_audit,
    validate_input,
    determine_action,
    is_supported_failure,
)


# ============================================================
# TEST DATA HELPER
# ============================================================

def make_policy_input(**overrides):
    data = {
        "transaction_id": "TEST_POLICY_001",
        "recovery_probability": 0.875,
        "failure_code": "BANK_TIMEOUT",
        "failure_type": "TRANSIENT",
        "attempt_count": 1,
        "amount": 5000.0,
    }

    data.update(overrides)

    return data


# ============================================================
# VALID POLICY
# ============================================================

def test_policy_approves_valid_retry():

    result = evaluate_policy(
        make_policy_input()
    )

    assert result["status"] == "success"
    assert result["decision"] == "APPROVED"
    assert result["approved"] is True
    assert result["action"] == "RETRY_PAYMENT"
    assert result["guardrails_passed"] is True


def test_policy_result_has_expected_action():

    result = evaluate_policy(
        make_policy_input()
    )

    assert result["expected_action"] == "RETRY_PAYMENT"


# ============================================================
# PROBABILITY
# ============================================================

def test_policy_blocks_low_probability():

    result = evaluate_policy(
        make_policy_input(
            recovery_probability=0.30
        )
    )

    assert result["decision"] == "BLOCKED"
    assert result["approved"] is False
    assert "probability" in result["reason"].lower()


def test_zero_probability_is_valid_but_blocked():

    result = evaluate_policy(
        make_policy_input(
            recovery_probability=0.0
        )
    )

    assert result["decision"] == "BLOCKED"
    assert result["approved"] is False


def test_exact_probability_threshold_is_allowed():

    result = evaluate_policy(
        make_policy_input(
            recovery_probability=0.50
        )
    )

    assert result["decision"] == "APPROVED"
    assert result["approved"] is True


def test_probability_one_is_allowed():

    result = evaluate_policy(
        make_policy_input(
            recovery_probability=1.0
        )
    )

    assert result["decision"] == "APPROVED"


@pytest.mark.parametrize(
    "probability",
    [
        -0.1,
        1.1,
    ],
)
def test_invalid_probability_range_is_rejected(
    probability
):

    with pytest.raises(
        ValueError,
        match="between 0 and 1"
    ):
        evaluate_policy(
            make_policy_input(
                recovery_probability=probability
            )
        )


@pytest.mark.parametrize(
    "probability",
    [
        float("nan"),
        float("inf"),
        float("-inf"),
        "not-a-number",
        None,
    ],
)
def test_non_finite_or_invalid_probability_is_rejected(
    probability
):

    with pytest.raises(
        ValueError,
        match="finite number"
    ):
        evaluate_policy(
            make_policy_input(
                recovery_probability=probability
            )
        )


# ============================================================
# AMOUNT
# ============================================================

def test_policy_blocks_excessive_amount():

    result = evaluate_policy(
        make_policy_input(
            amount=50001.0
        )
    )

    assert result["decision"] == "BLOCKED"
    assert result["approved"] is False
    assert "amount" in result["reason"].lower()


def test_exact_amount_limit_is_allowed():

    result = evaluate_policy(
        make_policy_input(
            amount=50000.0
        )
    )

    assert result["decision"] == "APPROVED"
    assert result["approved"] is True


def test_zero_amount_is_allowed():

    result = evaluate_policy(
        make_policy_input(
            amount=0.0
        )
    )

    assert result["decision"] == "APPROVED"


def test_negative_amount_is_rejected():

    with pytest.raises(
        ValueError,
        match="cannot be negative"
    ):
        evaluate_policy(
            make_policy_input(
                amount=-1.0
            )
        )


@pytest.mark.parametrize(
    "amount",
    [
        float("nan"),
        float("inf"),
        float("-inf"),
        "invalid",
        None,
        [],
        {},
    ],
)
def test_invalid_amount_is_rejected(amount):

    with pytest.raises(
        ValueError,
        match="finite number"
    ):
        evaluate_policy(
            make_policy_input(
                amount=amount
            )
        )


# ============================================================
# RETRY
# ============================================================

def test_policy_blocks_retry_limit():

    result = evaluate_policy(
        make_policy_input(
            attempt_count=3
        )
    )

    assert result["decision"] == "BLOCKED"
    assert result["approved"] is False
    assert "retry" in result["reason"].lower()


def test_policy_allows_retry_at_attempt_two():

    result = evaluate_policy(
        make_policy_input(
            attempt_count=2
        )
    )

    assert result["decision"] == "APPROVED"
    assert result["approved"] is True
    assert result["action"] == "RETRY_PAYMENT"


def test_zero_attempts_are_allowed():

    result = evaluate_policy(
        make_policy_input(
            attempt_count=0
        )
    )

    assert result["decision"] == "APPROVED"


def test_negative_attempt_count_is_rejected():

    with pytest.raises(
        ValueError,
        match="cannot be negative"
    ):
        evaluate_policy(
            make_policy_input(
                attempt_count=-1
            )
        )


@pytest.mark.parametrize(
    "attempt_count",
    [
        1.5,
        2.2,
        float("nan"),
        float("inf"),
        float("-inf"),
        "invalid",
        None,
        [],
        {},
    ],
)
def test_invalid_attempt_count_is_rejected(
    attempt_count
):

    with pytest.raises(
        ValueError,
        match="non-negative integer"
    ):
        evaluate_policy(
            make_policy_input(
                attempt_count=attempt_count
            )
        )


def test_boolean_attempt_count_is_rejected():

    with pytest.raises(
        ValueError,
        match="non-negative integer"
    ):
        evaluate_policy(
            make_policy_input(
                attempt_count=True
            )
        )


# ============================================================
# CUSTOMER ACTION
# ============================================================

def test_customer_action_failure():

    result = evaluate_policy(
        make_policy_input(
            failure_code="INSUFFICIENT_FUNDS",
            failure_type="CUSTOMER_ACTION_REQUIRED",
            recovery_probability=0.90,
        )
    )

    assert result["decision"] == "APPROVED"
    assert result["approved"] is True
    assert (
        result["action"]
        == "REQUEST_PAYMENT_METHOD_UPDATE"
    )


def test_expired_card_requires_customer_action():

    result = evaluate_policy(
        make_policy_input(
            failure_code="EXPIRED_CARD",
            failure_type="CUSTOMER_ACTION_REQUIRED",
            recovery_probability=0.90,
        )
    )

    assert result["decision"] == "APPROVED"
    assert (
        result["action"]
        == "REQUEST_PAYMENT_METHOD_UPDATE"
    )


def test_authentication_failure_requires_customer_action():

    result = evaluate_policy(
        make_policy_input(
            failure_code="AUTHENTICATION_FAILED",
            failure_type="CUSTOMER_ACTION_REQUIRED",
            recovery_probability=0.90,
        )
    )

    assert result["decision"] == "APPROVED"
    assert (
        result["action"]
        == "REQUEST_PAYMENT_METHOD_UPDATE"
    )


# ============================================================
# HARD FAILURE
# ============================================================

@pytest.mark.parametrize(
    "failure_code",
    [
        "INVALID_CARD",
        "CARD_BLOCKED",
        "FRAUD_SUSPECTED",
    ],
)
def test_hard_failures_escalate(
    failure_code
):

    result = evaluate_policy(
        make_policy_input(
            failure_code=failure_code,
            failure_type="HARD_FAILURE",
            recovery_probability=0.10,
        )
    )

    assert result["decision"] == "APPROVED"
    assert result["approved"] is True
    assert result["action"] == "ESCALATE"
    assert result["expected_action"] == "ESCALATE"


def test_hard_failure_does_not_require_probability():

    result = evaluate_policy(
        make_policy_input(
            failure_code="FRAUD_SUSPECTED",
            failure_type="HARD_FAILURE",
            recovery_probability=0.0,
        )
    )

    assert result["decision"] == "APPROVED"
    assert result["action"] == "ESCALATE"


# ============================================================
# UNKNOWN FAILURE
# ============================================================

def test_unknown_failure_is_blocked():

    result = evaluate_policy(
        make_policy_input(
            failure_code="UNKNOWN_FAILURE",
            failure_type="UNKNOWN",
        )
    )

    assert result["decision"] == "BLOCKED"
    assert result["approved"] is False
    assert "unsupported" in result["reason"].lower()


def test_unknown_failure_routes_to_human_review():

    result = evaluate_policy(
        make_policy_input(
            failure_code="UNKNOWN_FAILURE",
            failure_type="UNKNOWN",
        )
    )

    assert result["action"] == "HUMAN_REVIEW"
    assert result["expected_action"] == "HUMAN_REVIEW"
    assert result["decision"] == "BLOCKED"


# ============================================================
# REQUESTED ACTION VALIDATION
# ============================================================

def test_correct_requested_action_is_approved():

    result = evaluate_policy(
        make_policy_input(
            requested_action="RETRY_PAYMENT"
        )
    )

    assert result["decision"] == "APPROVED"
    assert result["action"] == "RETRY_PAYMENT"


def test_incorrect_requested_action_is_blocked():

    result = evaluate_policy(
        make_policy_input(
            requested_action="ESCALATE"
        )
    )

    assert result["decision"] == "BLOCKED"
    assert result["approved"] is False
    assert (
        "violates"
        in result["reason"].lower()
    )


def test_unsupported_requested_action_is_blocked():

    result = evaluate_policy(
        make_policy_input(
            requested_action="STEAL_PAYMENT"
        )
    )

    assert result["decision"] == "BLOCKED"
    assert result["approved"] is False


def test_empty_requested_action_is_rejected():

    with pytest.raises(
        ValueError,
        match="requested_action cannot be empty"
    ):
        evaluate_policy(
            make_policy_input(
                requested_action=""
            )
        )


def test_requested_action_whitespace_is_rejected():

    with pytest.raises(
        ValueError,
        match="requested_action cannot be empty"
    ):
        evaluate_policy(
            make_policy_input(
                requested_action="   "
            )
        )


# ============================================================
# MISSING FIELDS
# ============================================================

def test_policy_missing_required_field():

    data = make_policy_input()

    del data["amount"]

    with pytest.raises(
        ValueError,
        match="Missing required fields"
    ):
        evaluate_policy(data)


@pytest.mark.parametrize(
    "field",
    [
        "transaction_id",
        "recovery_probability",
        "failure_code",
        "failure_type",
        "attempt_count",
        "amount",
    ],
)
def test_each_required_field_is_required(field):

    data = make_policy_input()

    del data[field]

    with pytest.raises(
        ValueError,
        match="Missing required fields"
    ):
        evaluate_policy(data)


# ============================================================
# INPUT TYPE VALIDATION
# ============================================================

@pytest.mark.parametrize(
    "invalid_input",
    [
        None,
        [],
        (),
        "invalid",
        123,
        object(),
    ],
)
def test_policy_rejects_non_dictionary_input(
    invalid_input
):

    with pytest.raises(
        TypeError,
        match="dictionary"
    ):
        evaluate_policy(invalid_input)


def test_empty_transaction_id_is_rejected():

    with pytest.raises(
        ValueError,
        match="transaction_id cannot be empty"
    ):
        evaluate_policy(
            make_policy_input(
                transaction_id=""
            )
        )


def test_whitespace_transaction_id_is_rejected():

    with pytest.raises(
        ValueError,
        match="transaction_id cannot be empty"
    ):
        evaluate_policy(
            make_policy_input(
                transaction_id="   "
            )
        )


def test_empty_failure_code_is_rejected():

    with pytest.raises(
        ValueError,
        match="failure_code cannot be empty"
    ):
        evaluate_policy(
            make_policy_input(
                failure_code=""
            )
        )


def test_empty_failure_type_is_rejected():

    with pytest.raises(
        ValueError,
        match="failure_type cannot be empty"
    ):
        evaluate_policy(
            make_policy_input(
                failure_type=""
            )
        )


# ============================================================
# FAILURE CLASSIFICATION
# ============================================================

def test_determine_action_transient():

    assert (
        determine_action(
            "TRANSIENT",
            "BANK_TIMEOUT",
        )
        == "RETRY_PAYMENT"
    )


def test_determine_action_network_error():

    assert (
        determine_action(
            "TRANSIENT",
            "NETWORK_ERROR",
        )
        == "RETRY_PAYMENT"
    )


def test_determine_action_gateway_timeout():

    assert (
        determine_action(
            "TRANSIENT",
            "GATEWAY_TIMEOUT",
        )
        == "RETRY_PAYMENT"
    )


def test_determine_action_bank_server_error():

    assert (
        determine_action(
            "TRANSIENT",
            "BANK_SERVER_ERROR",
        )
        == "RETRY_PAYMENT"
    )


def test_determine_action_customer_action():

    assert (
        determine_action(
            "CUSTOMER_ACTION_REQUIRED",
            "INSUFFICIENT_FUNDS",
        )
        == "REQUEST_PAYMENT_METHOD_UPDATE"
    )


def test_determine_action_hard_failure():

    assert (
        determine_action(
            "HARD_FAILURE",
            "FRAUD_SUSPECTED",
        )
        == "ESCALATE"
    )


def test_determine_action_unknown_type_returns_human_review():

    assert (
        determine_action(
            "UNKNOWN",
            "UNKNOWN_FAILURE",
        )
        == "HUMAN_REVIEW"
    )


@pytest.mark.parametrize(
    "failure_code",
    [
        "BANK_TIMEOUT",
        "NETWORK_ERROR",
        "GATEWAY_TIMEOUT",
        "BANK_SERVER_ERROR",
        "INSUFFICIENT_FUNDS",
        "EXPIRED_CARD",
        "AUTHENTICATION_FAILED",
        "INVALID_CARD",
        "CARD_BLOCKED",
        "FRAUD_SUSPECTED",
    ],
)
def test_supported_failure_codes(
    failure_code
):

    assert is_supported_failure(
        failure_code
    ) is True


def test_unknown_failure_code_is_not_supported():

    assert (
        is_supported_failure(
            "UNKNOWN_FAILURE"
        )
        is False
    )


# ============================================================
# GUARDRAILS
# ============================================================

def test_guardrails_are_present():

    result = evaluate_policy(
        make_policy_input()
    )

    assert isinstance(
        result["guardrails"],
        list
    )

    assert len(
        result["guardrails"]
    ) == 6

    checks = {
        check["check"]
        for check in result["guardrails"]
    }

    assert "supported_failure" in checks
    assert "minimum_recovery_probability" in checks
    assert "retry_limit" in checks
    assert "automatic_amount_limit" in checks
    assert "action_consistency" in checks
    assert "hard_failure_protection" in checks


def test_all_guardrails_pass_for_valid_retry():

    result = evaluate_policy(
        make_policy_input()
    )

    for check in result["guardrails"]:
        assert check["passed"] is True


def test_probability_guardrail_fails_when_probability_low():

    result = evaluate_policy(
        make_policy_input(
            recovery_probability=0.20
        )
    )

    probability_check = next(
        check
        for check in result["guardrails"]
        if check["check"]
        == "minimum_recovery_probability"
    )

    assert probability_check["passed"] is False


def test_retry_guardrail_fails_at_limit():

    result = evaluate_policy(
        make_policy_input(
            attempt_count=3
        )
    )

    retry_check = next(
        check
        for check in result["guardrails"]
        if check["check"] == "retry_limit"
    )

    assert retry_check["passed"] is False


def test_amount_guardrail_fails_above_limit():

    result = evaluate_policy(
        make_policy_input(
            amount=50001
        )
    )

    amount_check = next(
        check
        for check in result["guardrails"]
        if check["check"]
        == "automatic_amount_limit"
    )

    assert amount_check["passed"] is False


def test_action_consistency_guardrail_fails():

    result = evaluate_policy(
        make_policy_input(
            requested_action="ESCALATE"
        )
    )

    consistency_check = next(
        check
        for check in result["guardrails"]
        if check["check"]
        == "action_consistency"
    )

    assert consistency_check["passed"] is False


# ============================================================
# HARD FAILURE PROTECTION
# ============================================================

def test_hard_failure_protection_passes_for_escalation():

    result = evaluate_policy(
        make_policy_input(
            failure_code="FRAUD_SUSPECTED",
            failure_type="HARD_FAILURE",
            requested_action="ESCALATE",
        )
    )

    hard_check = next(
        check
        for check in result["guardrails"]
        if check["check"]
        == "hard_failure_protection"
    )

    assert hard_check["passed"] is True


# ============================================================
# AUDIT
# ============================================================

def test_save_audit():

    result = evaluate_policy(
        make_policy_input()
    )

    path = save_audit(result)

    assert path
    assert os.path.isfile(path)

    with open(
        path,
        "r",
        encoding="utf-8"
    ) as file:

        saved = json.load(file)

    assert (
        saved["transaction_id"]
        == "TEST_POLICY_001"
    )


def test_save_audit_rejects_non_dictionary():

    with pytest.raises(
        TypeError,
        match="dictionary"
    ):
        save_audit(None)


@pytest.mark.parametrize(
    "result",
    [
        {},
        {"status": "success"},
    ],
)
def test_save_audit_requires_transaction_id(
    result
):

    with pytest.raises(
        ValueError,
        match="transaction_id"
    ):
        save_audit(result)


def test_save_audit_rejects_empty_transaction_id():

    result = {
        "transaction_id": ""
    }

    with pytest.raises(
        ValueError,
        match="transaction_id cannot be empty"
    ):
        save_audit(result)


@pytest.mark.parametrize(
    "transaction_id",
    [
        "../malicious",
        "..\\malicious",
        "folder/file",
        "folder\\file",
    ],
)
def test_save_audit_rejects_path_traversal(
    transaction_id
):

    result = {
        "transaction_id": transaction_id
    }

    with pytest.raises(
        ValueError,
        match="Invalid transaction_id"
    ):
        save_audit(result)


# ============================================================
# RESULT SCHEMA
# ============================================================

def test_policy_result_contains_required_fields():

    result = evaluate_policy(
        make_policy_input()
    )

    required_fields = {
        "status",
        "transaction_id",
        "policy_version",
        "decision",
        "approved",
        "action",
        "expected_action",
        "reason",
        "recovery_probability",
        "failure_code",
        "failure_type",
        "attempt_count",
        "amount",
        "guardrails_passed",
        "guardrails",
        "timestamp",
    }

    assert required_fields.issubset(
        result.keys()
    )


def test_policy_timestamp_exists():

    result = evaluate_policy(
        make_policy_input()
    )

    assert result["timestamp"]
    assert "T" in result["timestamp"]


def test_blocked_policy_has_approved_false():

    result = evaluate_policy(
        make_policy_input(
            recovery_probability=0.1
        )
    )

    assert result["decision"] == "BLOCKED"
    assert result["approved"] is False


def test_approved_policy_has_approved_true():

    result = evaluate_policy(
        make_policy_input()
    )

    assert result["decision"] == "APPROVED"
    assert result["approved"] is True