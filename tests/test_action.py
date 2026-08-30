import json
import os
import pytest

from action_engine import execute_action


# ============================================================
# TEST HELPERS
# ============================================================

def make_policy_result(**overrides):
    data = {
        "transaction_id": "TEST_ACTION_001",
        "decision": "APPROVED",
        "approved": True,
        "action": "RETRY_PAYMENT",
        "attempt_count": 1,
        "amount": 5000.0,
    }

    data.update(overrides)

    return data


# ============================================================
# RETRY PAYMENT
# ============================================================

def test_retry_payment_executes():
    result = execute_action(
        make_policy_result()
    )

    assert result["status"] == "success"
    assert result["executed"] is True
    assert result["simulation"] is True
    assert result["action"] == "RETRY_PAYMENT"

    assert result["attempt_count_before"] == 1
    assert result["attempt_count_after"] == 2

    assert result["amount"] == 5000.0

    assert result["action_id"].startswith(
        "ACT_"
    )


def test_retry_at_attempt_two():
    result = execute_action(
        make_policy_result(
            attempt_count=2
        )
    )

    assert result["status"] == "success"
    assert result["executed"] is True

    assert result["attempt_count_before"] == 2
    assert result["attempt_count_after"] == 3


def test_retry_limit_blocks_execution():
    result = execute_action(
        make_policy_result(
            attempt_count=3
        )
    )

    assert result["status"] == "blocked"
    assert result["executed"] is False

    assert "retry limit" in (
        result["reason"].lower()
    )


# ============================================================
# POLICY GATE
# ============================================================

def test_policy_block_prevents_execution():
    result = execute_action(
        make_policy_result(
            decision="BLOCKED",
            approved=False,
        )
    )

    assert result["status"] == "blocked"
    assert result["executed"] is False

    assert "policy" in (
        result["reason"].lower()
    )


def test_approved_false_prevents_execution():
    """
    An APPROVED + approved=False combination is
    contradictory and must be rejected rather than
    executed or silently treated as blocked.
    """

    with pytest.raises(
        ValueError,
        match="inconsistent"
    ):
        execute_action(
            make_policy_result(
                decision="APPROVED",
                approved=False,
            )
        )


def test_blocked_policy_with_approved_true_is_rejected():
    """
    A BLOCKED + approved=True combination is also
    contradictory and must fail closed.
    """

    with pytest.raises(
        ValueError,
        match="inconsistent"
    ):
        execute_action(
            make_policy_result(
                decision="BLOCKED",
                approved=True,
            )
        )


# ============================================================
# PAYMENT METHOD UPDATE
# ============================================================

def test_payment_method_update_executes():
    result = execute_action(
        make_policy_result(
            action="REQUEST_PAYMENT_METHOD_UPDATE"
        )
    )

    assert result["status"] == "success"
    assert result["executed"] is True
    assert result["simulation"] is True

    assert result["action"] == (
        "REQUEST_PAYMENT_METHOD_UPDATE"
    )


# ============================================================
# PAYMENT REMINDER
# ============================================================

def test_payment_reminder_executes():
    result = execute_action(
        make_policy_result(
            action="PAYMENT_REMINDER"
        )
    )

    assert result["status"] == "success"
    assert result["executed"] is True
    assert result["simulation"] is True

    assert result["action"] == (
        "PAYMENT_REMINDER"
    )


# ============================================================
# ESCALATION
# ============================================================

def test_escalation_executes():
    result = execute_action(
        make_policy_result(
            action="ESCALATE"
        )
    )

    assert result["status"] == "success"
    assert result["executed"] is True
    assert result["simulation"] is True

    assert result["action"] == "ESCALATE"


def test_human_review_executes():
    result = execute_action(
        make_policy_result(
            action="HUMAN_REVIEW"
        )
    )

    assert result["status"] == "success"
    assert result["executed"] is True
    assert result["simulation"] is True

    assert result["action"] == "HUMAN_REVIEW"


# ============================================================
# ACTION VALIDATION
# ============================================================

def test_invalid_action_is_rejected():
    with pytest.raises(
        ValueError,
        match="Unsupported recovery action"
    ):
        execute_action(
            make_policy_result(
                action="INVALID_ACTION"
            )
        )


def test_invalid_decision_is_rejected():
    with pytest.raises(
        ValueError,
        match="Invalid policy decision"
    ):
        execute_action(
            make_policy_result(
                decision="UNKNOWN"
            )
        )


# ============================================================
# ATTEMPT COUNT VALIDATION
# ============================================================

def test_negative_attempt_count_is_rejected():
    with pytest.raises(
        ValueError,
        match="cannot be negative"
    ):
        execute_action(
            make_policy_result(
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
        True,
        False,
    ],
)
def test_invalid_attempt_count_is_rejected(
    attempt_count
):
    with pytest.raises(
        ValueError,
        match="non-negative integer"
    ):
        execute_action(
            make_policy_result(
                attempt_count=attempt_count
            )
        )


def test_string_integer_attempt_count_is_normalized():
    result = execute_action(
        make_policy_result(
            attempt_count="1"
        )
    )

    assert result["executed"] is True
    assert result["attempt_count_before"] == 1
    assert result["attempt_count_after"] == 2


# ============================================================
# AMOUNT VALIDATION
# ============================================================

def test_negative_amount_is_rejected():
    with pytest.raises(
        ValueError,
        match="cannot be negative"
    ):
        execute_action(
            make_policy_result(
                amount=-100
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
def test_invalid_amount_is_rejected(
    amount
):
    with pytest.raises(
        ValueError,
        match="finite number"
    ):
        execute_action(
            make_policy_result(
                amount=amount
            )
        )


def test_string_amount_is_normalized():
    result = execute_action(
        make_policy_result(
            amount="5000"
        )
    )

    assert result["executed"] is True
    assert result["amount"] == 5000.0


# ============================================================
# TRANSACTION ID VALIDATION
# ============================================================

@pytest.mark.parametrize(
    "transaction_id",
    [
        "",
        " ",
        None,
        "../evil",
        "..\\evil",
        "folder/file",
        "folder\\file",
        ".",
        "..",
    ],
)
def test_invalid_transaction_id_is_rejected(
    transaction_id
):
    with pytest.raises(
        ValueError
    ):
        execute_action(
            make_policy_result(
                transaction_id=transaction_id
            )
        )


def test_transaction_id_is_stripped():
    result = execute_action(
        make_policy_result(
            transaction_id="  TEST_TXN_001  "
        )
    )

    assert result["transaction_id"] == (
        "TEST_TXN_001"
    )


# ============================================================
# POLICY RESULT STRUCTURE
# ============================================================

def test_missing_policy_field_is_rejected():
    policy = make_policy_result()

    del policy["transaction_id"]

    with pytest.raises(
        ValueError,
        match="missing fields"
    ):
        execute_action(policy)


@pytest.mark.parametrize(
    "field",
    [
        "decision",
        "approved",
        "action",
        "attempt_count",
        "amount",
    ],
)
def test_missing_required_policy_field_is_rejected(
    field
):
    policy = make_policy_result()

    del policy[field]

    with pytest.raises(
        ValueError,
        match="missing fields"
    ):
        execute_action(policy)


def test_policy_result_must_be_dictionary():
    with pytest.raises(
        TypeError,
        match="dictionary"
    ):
        execute_action([])


def test_approved_field_must_be_boolean():
    policy = make_policy_result(
        approved="true"
    )

    with pytest.raises(
        TypeError,
        match="approved field must be boolean"
    ):
        execute_action(policy)


def test_action_field_must_be_string():
    policy = make_policy_result(
        action=123
    )

    with pytest.raises(
        TypeError,
        match="action must be a string"
    ):
        execute_action(policy)


# ============================================================
# DECISION / APPROVED CONSISTENCY
# ============================================================

@pytest.mark.parametrize(
    "decision,approved",
    [
        ("APPROVED", False),
        ("BLOCKED", True),
    ],
)
def test_decision_and_approved_must_be_consistent(
    decision,
    approved,
):
    with pytest.raises(
        ValueError,
        match="inconsistent"
    ):
        execute_action(
            make_policy_result(
                decision=decision,
                approved=approved,
            )
        )


# ============================================================
# ACTION RESULT SCHEMA
# ============================================================

def test_action_result_contains_required_fields():
    result = execute_action(
        make_policy_result()
    )

    required_fields = {
        "status",
        "action_id",
        "transaction_id",
        "action",
        "executed",
        "timestamp",
        "action_version",
    }

    assert required_fields.issubset(
        result.keys()
    )


def test_blocked_result_contains_required_fields():
    result = execute_action(
        make_policy_result(
            decision="BLOCKED",
            approved=False,
        )
    )

    required_fields = {
        "status",
        "action_id",
        "transaction_id",
        "action",
        "executed",
        "reason",
        "timestamp",
        "action_version",
    }

    assert required_fields.issubset(
        result.keys()
    )


# ============================================================
# ACTION ID
# ============================================================

def test_action_id_is_unique():
    result1 = execute_action(
        make_policy_result(
            transaction_id="TEST_ACTION_002"
        )
    )

    result2 = execute_action(
        make_policy_result(
            transaction_id="TEST_ACTION_003"
        )
    )

    assert result1["action_id"] != (
        result2["action_id"]
    )


def test_action_id_format():
    result = execute_action(
        make_policy_result()
    )

    assert isinstance(
        result["action_id"],
        str
    )

    assert result["action_id"].startswith(
        "ACT_"
    )

    assert len(
        result["action_id"]
    ) == 16


# ============================================================
# SIMULATION SAFETY
# ============================================================

@pytest.mark.parametrize(
    "action",
    [
        "RETRY_PAYMENT",
        "PAYMENT_REMINDER",
        "REQUEST_PAYMENT_METHOD_UPDATE",
        "ESCALATE",
        "HUMAN_REVIEW",
    ],
)
def test_all_actions_are_simulated(
    action
):
    result = execute_action(
        make_policy_result(
            action=action
        )
    )

    assert result["executed"] is True
    assert result["simulation"] is True


# ============================================================
# RESULT VALIDATION / SAVE
# ============================================================

def test_save_action_result_creates_valid_json(
    tmp_path
):
    import action_engine

    original_dir = action_engine.ACTION_DIR

    action_engine.ACTION_DIR = str(
        tmp_path
    )

    try:
        result = execute_action(
            make_policy_result(
                transaction_id="TEST_ACTION_SAVE"
            )
        )

        path = action_engine.save_action_result(
            result
        )

        assert path.endswith(
            "TEST_ACTION_SAVE.json"
        )

        assert os.path.exists(path)

        with open(
            path,
            "r",
            encoding="utf-8"
        ) as file:
            saved_result = json.load(file)

        assert (
            saved_result["transaction_id"]
            == "TEST_ACTION_SAVE"
        )

        assert (
            saved_result["action_id"]
            == result["action_id"]
        )

    finally:
        action_engine.ACTION_DIR = (
            original_dir
        )


def test_malformed_action_result_cannot_be_saved(
    tmp_path
):
    import action_engine

    original_dir = action_engine.ACTION_DIR

    action_engine.ACTION_DIR = str(
        tmp_path
    )

    try:
        malformed_result = {
            "status": "success",
            "transaction_id": "TEST_BAD",
        }

        with pytest.raises(
            ValueError,
            match="missing fields"
        ):
            action_engine.save_action_result(
                malformed_result
            )

    finally:
        action_engine.ACTION_DIR = (
            original_dir
        )


# ============================================================
# PATH TRAVERSAL PROTECTION DURING SAVE
# ============================================================

def test_save_rejects_path_traversal(
    tmp_path
):
    import action_engine

    original_dir = action_engine.ACTION_DIR

    action_engine.ACTION_DIR = str(
        tmp_path
    )

    try:
        result = execute_action(
            make_policy_result(
                transaction_id="SAFE_TXN"
            )
        )

        result["transaction_id"] = (
            "../evil"
        )

        with pytest.raises(
            ValueError,
            match="Invalid transaction_id"
        ):
            action_engine.save_action_result(
                result
            )

    finally:
        action_engine.ACTION_DIR = (
            original_dir
        )