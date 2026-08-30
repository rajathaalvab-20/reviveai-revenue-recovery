import json
import os

import pytest

import verification_engine


def make_action_result(**overrides):
    data = {
        "status": "success",
        "action_id": "ACT_TEST_001",
        "transaction_id": "TXN_TEST_001",
        "action": "RETRY_PAYMENT",
        "executed": True,
        "simulation": True,
        "amount": 5000.0
    }

    data.update(overrides)

    return data


# ============================================================
# BASIC RECOVERY
# ============================================================

def test_retry_payment_verification_is_deterministic():

    action = make_action_result()

    result1 = verification_engine.verify_action(
        action
    )

    result2 = verification_engine.verify_action(
        action
    )

    assert (
        result1["verification_status"]
        ==
        result2["verification_status"]
    )

    assert (
        result1["revenue_recovered"]
        ==
        result2["revenue_recovered"]
    )


def test_recovered_result_has_revenue_fields():

    result = verification_engine.verify_action(
        make_action_result(
            transaction_id="TXN_RECOVERY_001",
            action_id="ACT_RECOVERY_001"
        )
    )

    assert result["status"] == "verified"

    assert "verification_status" in result
    assert "recovered" in result
    assert "revenue_recovered" in result
    assert "amount_at_risk" in result
    assert "reason" in result


# ============================================================
# NON-EXECUTED ACTION
# ============================================================

def test_non_executed_action_is_not_recovered():

    result = verification_engine.verify_action(
        make_action_result(
            executed=False
        )
    )

    assert result["verification_status"] == (
        "NOT_RECOVERED"
    )

    assert result["recovered"] is False

    assert result["revenue_recovered"] == 0.0

    assert result["amount_at_risk"] == 5000.0


# ============================================================
# PENDING ACTIONS
# ============================================================

def test_escalation_is_pending():

    result = verification_engine.verify_action(
        make_action_result(
            action="ESCALATE"
        )
    )

    assert result["verification_status"] == (
        "PENDING"
    )

    assert result["recovered"] is False

    assert result["revenue_recovered"] == 0.0


def test_human_review_is_pending():

    result = verification_engine.verify_action(
        make_action_result(
            action="HUMAN_REVIEW"
        )
    )

    assert result["verification_status"] == (
        "PENDING"
    )

    assert result["recovered"] is False


# ============================================================
# SUPPORTED RECOVERY ACTIONS
# ============================================================

def test_payment_reminder_is_supported():

    result = verification_engine.verify_action(
        make_action_result(
            action="PAYMENT_REMINDER"
        )
    )

    assert result["status"] == "verified"

    assert result["action"] == (
        "PAYMENT_REMINDER"
    )


def test_payment_method_update_is_supported():

    result = verification_engine.verify_action(
        make_action_result(
            action="REQUEST_PAYMENT_METHOD_UPDATE"
        )
    )

    assert result["status"] == "verified"

    assert result["action"] == (
        "REQUEST_PAYMENT_METHOD_UPDATE"
    )


# ============================================================
# INVALID ACTION
# ============================================================

def test_unsupported_action_is_rejected():

    with pytest.raises(
        ValueError,
        match="Unsupported verification action"
    ):
        verification_engine.verify_action(
            make_action_result(
                action="INVALID_ACTION"
            )
        )


# ============================================================
# VALIDATION
# ============================================================

def test_missing_transaction_id_is_rejected():

    action = make_action_result()

    del action["transaction_id"]

    with pytest.raises(
        ValueError,
        match="missing fields"
    ):
        verification_engine.verify_action(
            action
        )


def test_missing_action_id_is_rejected():

    action = make_action_result()

    del action["action_id"]

    with pytest.raises(
        ValueError,
        match="missing fields"
    ):
        verification_engine.verify_action(
            action
        )


def test_missing_action_is_rejected():

    action = make_action_result()

    del action["action"]

    with pytest.raises(
        ValueError,
        match="missing fields"
    ):
        verification_engine.verify_action(
            action
        )


def test_missing_executed_is_rejected():

    action = make_action_result()

    del action["executed"]

    with pytest.raises(
        ValueError,
        match="missing fields"
    ):
        verification_engine.verify_action(
            action
        )


def test_missing_amount_is_rejected():

    action = make_action_result()

    del action["amount"]

    with pytest.raises(
        ValueError,
        match="missing fields"
    ):
        verification_engine.verify_action(
            action
        )


def test_executed_must_be_boolean():

    action = make_action_result(
        executed="true"
    )

    with pytest.raises(
        TypeError,
        match="executed must be boolean"
    ):
        verification_engine.verify_action(
            action
        )


def test_negative_amount_is_rejected():

    action = make_action_result(
        amount=-100
    )

    with pytest.raises(
        ValueError,
        match="amount cannot be negative"
    ):
        verification_engine.verify_action(
            action
        )


def test_non_numeric_amount_is_rejected():

    action = make_action_result(
        amount="invalid"
    )

    with pytest.raises(
        TypeError,
        match="amount must be numeric"
    ):
        verification_engine.verify_action(
            action
        )


def test_action_result_must_be_dictionary():

    with pytest.raises(
        TypeError,
        match="must be a dictionary"
    ):
        verification_engine.verify_action(
            None
        )


# ============================================================
# EMPTY IDENTIFIERS
# ============================================================

def test_empty_transaction_id_is_rejected():

    with pytest.raises(
        ValueError,
        match="transaction_id cannot be empty"
    ):
        verification_engine.verify_action(
            make_action_result(
                transaction_id="   "
            )
        )


def test_empty_action_id_is_rejected():

    with pytest.raises(
        ValueError,
        match="action_id cannot be empty"
    ):
        verification_engine.verify_action(
            make_action_result(
                action_id="   "
            )
        )


def test_empty_action_is_rejected():

    with pytest.raises(
        ValueError,
        match="action cannot be empty"
    ):
        verification_engine.verify_action(
            make_action_result(
                action="   "
            )
        )


# ============================================================
# DETERMINISTIC FUNCTION
# ============================================================

def test_deterministic_recovery_returns_boolean():

    result = verification_engine.deterministic_recovery_check(
        "TXN_001",
        "ACT_001",
        "RETRY_PAYMENT"
    )

    assert isinstance(
        result,
        bool
    )


def test_deterministic_recovery_is_repeatable():

    result1 = (
        verification_engine
        .deterministic_recovery_check(
            "TXN_002",
            "ACT_002",
            "RETRY_PAYMENT"
        )
    )

    result2 = (
        verification_engine
        .deterministic_recovery_check(
            "TXN_002",
            "ACT_002",
            "RETRY_PAYMENT"
        )
    )

    assert result1 == result2


# ============================================================
# SAVE RESULT
# ============================================================

def test_save_verification_result(tmp_path):

    original_dir = (
        verification_engine.VERIFICATION_DIR
    )

    verification_engine.VERIFICATION_DIR = (
        str(tmp_path)
    )

    try:

        result = verification_engine.verify_action(
            make_action_result(
                transaction_id="TXN_SAVE_001"
            )
        )

        path = (
            verification_engine
            .save_verification_result(
                result
            )
        )

        assert os.path.exists(path)

        assert path.endswith(
            "TXN_SAVE_001.json"
        )

        with open(
            path,
            "r",
            encoding="utf-8"
        ) as file:

            saved = json.load(file)

        assert (
            saved["transaction_id"]
            ==
            "TXN_SAVE_001"
        )

        assert (
            saved["action_id"]
            ==
            result["action_id"]
        )

    finally:

        verification_engine.VERIFICATION_DIR = (
            original_dir
        )


def test_save_result_requires_dictionary():

    with pytest.raises(
        TypeError,
        match="must be a dictionary"
    ):
        verification_engine.save_verification_result(
            None
        )


def test_save_result_requires_transaction_id():

    with pytest.raises(
        ValueError,
        match="missing transaction_id"
    ):
        verification_engine.save_verification_result(
            {
                "status": "verified"
            }
        )


# ============================================================
# MAIN / DEMO
# ============================================================

def test_main_returns_verification_result(
    tmp_path
):

    original_dir = (
        verification_engine.VERIFICATION_DIR
    )

    verification_engine.VERIFICATION_DIR = (
        str(tmp_path)
    )

    try:

        result = verification_engine.main()

        assert result["status"] == (
            "verified"
        )

        assert result["transaction_id"] == (
            "TXN_DEMO_001"
        )

        assert "result_file" in result

        assert os.path.exists(
            result["result_file"]
        )

    finally:

        verification_engine.VERIFICATION_DIR = (
            original_dir
        )