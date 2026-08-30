import json
import os
import pytest

from analytics import BatchAnalytics


# ============================================================
# TEST HELPERS
# ============================================================

def make_transaction(
    transaction_id="TX001",
    status="recovered",
    amount=100.0,
    recovered=100.0,
    action="RETRY_PAYMENT",
    failure_code="BANK_TIMEOUT",
    failure_type="TRANSIENT"
):
    return {
        "transaction_id": transaction_id,
        "status": status,
        "revenue_at_risk": amount,
        "revenue_recovered": recovered,
        "pipeline_result": {
            "action": {
                "action": action
            },
            "diagnosis": {
                "failure_code": failure_code,
                "failure_type": failure_type
            }
        }
    }


def make_batch(transactions):
    return {
        "status": "completed",
        "transactions": transactions
    }


# ============================================================
# BASIC ANALYSIS
# ============================================================

def test_basic_analysis():

    batch = make_batch([
        make_transaction()
    ])

    result = BatchAnalytics().analyze(batch)

    assert result["status"] == "success"
    assert result["summary"]["total_transactions"] == 1
    assert result["summary"]["recovered_transactions"] == 1
    assert result["analytics_version"] == "V1"
    assert "analyzed_at" in result


def test_revenue_metrics():

    batch = make_batch([
        make_transaction(
            amount=100,
            recovered=60
        )
    ])

    result = BatchAnalytics().analyze(batch)

    summary = result["summary"]

    assert summary["revenue_at_risk"] == 100
    assert summary["revenue_recovered"] == 60
    assert summary["revenue_not_recovered"] == 40
    assert summary["revenue_recovery_rate"] == 0.6


def test_transaction_recovery_rate():

    batch = make_batch([
        make_transaction(
            transaction_id="TX1",
            status="recovered"
        ),
        make_transaction(
            transaction_id="TX2",
            status="not_recovered",
            recovered=0
        ),
        make_transaction(
            transaction_id="TX3",
            status="blocked",
            recovered=0
        )
    ])

    result = BatchAnalytics().analyze(batch)

    assert (
        result["summary"]
        ["transaction_recovery_rate"]
        == pytest.approx(1 / 3)
    )


# ============================================================
# STATUS ANALYSIS
# ============================================================

def test_status_analysis():

    batch = make_batch([
        make_transaction(
            transaction_id="TX1",
            status="recovered"
        ),
        make_transaction(
            transaction_id="TX2",
            status="blocked",
            recovered=0
        ),
        make_transaction(
            transaction_id="TX3",
            status="not_recovered",
            recovered=0
        )
    ])

    result = BatchAnalytics().analyze(batch)

    status = result["status_analysis"]

    assert status["recovered"] == 1
    assert status["blocked"] == 1
    assert status["not_recovered"] == 1


def test_unknown_status_is_counted():

    batch = make_batch([
        make_transaction(
            transaction_id="TX_UNKNOWN",
            status="unexpected_status",
            recovered=0
        )
    ])

    result = BatchAnalytics().analyze(batch)

    assert (
        result["status_analysis"]
        ["unexpected_status"]
        == 1
    )


def test_missing_status_defaults_to_unknown():

    transaction = make_transaction(
        recovered=0
    )

    del transaction["status"]

    result = BatchAnalytics().analyze(
        make_batch([transaction])
    )

    assert result["status_analysis"]["unknown"] == 1


# ============================================================
# ACTION ANALYSIS
# ============================================================

def test_action_analysis():

    batch = make_batch([
        make_transaction(
            transaction_id="TX1",
            action="RETRY_PAYMENT"
        ),
        make_transaction(
            transaction_id="TX2",
            action="RETRY_PAYMENT",
            status="not_recovered",
            recovered=0
        ),
        make_transaction(
            transaction_id="TX3",
            action="ESCALATE",
            status="not_recovered",
            recovered=0
        )
    ])

    result = BatchAnalytics().analyze(batch)

    actions = result["action_analysis"]

    assert actions["RETRY_PAYMENT"]["transactions"] == 2
    assert actions["ESCALATE"]["transactions"] == 1

    assert (
        actions["RETRY_PAYMENT"]
        ["revenue_at_risk"]
        == 200
    )

    assert (
        actions["RETRY_PAYMENT"]
        ["revenue_recovered"]
        == 100
    )

    assert (
        actions["RETRY_PAYMENT"]
        ["recovery_rate"]
        == 0.5
    )


def test_missing_action_defaults_to_unknown():

    transaction = make_transaction(
        recovered=0
    )

    del transaction["pipeline_result"]["action"]

    result = BatchAnalytics().analyze(
        make_batch([transaction])
    )

    assert (
        "UNKNOWN"
        in result["action_analysis"]
    )


def test_missing_pipeline_defaults_to_unknown_action():

    transaction = make_transaction(
        recovered=0
    )

    del transaction["pipeline_result"]

    result = BatchAnalytics().analyze(
        make_batch([transaction])
    )

    assert (
        "UNKNOWN"
        in result["action_analysis"]
    )


# ============================================================
# FAILURE ANALYSIS
# ============================================================

def test_failure_analysis():

    batch = make_batch([
        make_transaction(
            transaction_id="TX1",
            failure_code="BANK_TIMEOUT",
            failure_type="TRANSIENT"
        ),
        make_transaction(
            transaction_id="TX2",
            failure_code="BANK_TIMEOUT",
            failure_type="TRANSIENT",
            status="not_recovered",
            recovered=0
        )
    ])

    result = BatchAnalytics().analyze(batch)

    failures = result["failure_analysis"]

    key = "TRANSIENT:BANK_TIMEOUT"

    assert key in failures
    assert failures[key]["transactions"] == 2
    assert failures[key]["revenue_at_risk"] == 200
    assert failures[key]["revenue_recovered"] == 100
    assert failures[key]["recovery_rate"] == 0.5


def test_multiple_failure_groups():

    batch = make_batch([
        make_transaction(
            transaction_id="TX1",
            failure_code="BANK_TIMEOUT",
            failure_type="TRANSIENT"
        ),
        make_transaction(
            transaction_id="TX2",
            failure_code="INSUFFICIENT_FUNDS",
            failure_type="CUSTOMER_ACTION_REQUIRED",
            status="not_recovered",
            recovered=0
        ),
        make_transaction(
            transaction_id="TX3",
            failure_code="FRAUD_SUSPECTED",
            failure_type="HARD_FAILURE",
            status="blocked",
            recovered=0
        )
    ])

    result = BatchAnalytics().analyze(batch)

    failures = result["failure_analysis"]

    assert "TRANSIENT:BANK_TIMEOUT" in failures

    assert (
        "CUSTOMER_ACTION_REQUIRED:INSUFFICIENT_FUNDS"
        in failures
    )

    assert (
        "HARD_FAILURE:FRAUD_SUSPECTED"
        in failures
    )


def test_missing_diagnosis_defaults_to_unknown():

    transaction = make_transaction(
        recovered=0
    )

    del transaction["pipeline_result"]["diagnosis"]

    result = BatchAnalytics().analyze(
        make_batch([transaction])
    )

    assert (
        "UNKNOWN:UNKNOWN"
        in result["failure_analysis"]
    )


def test_missing_pipeline_defaults_to_unknown_failure():

    transaction = make_transaction(
        recovered=0
    )

    del transaction["pipeline_result"]

    result = BatchAnalytics().analyze(
        make_batch([transaction])
    )

    assert (
        "UNKNOWN:UNKNOWN"
        in result["failure_analysis"]
    )


# ============================================================
# VALIDATION
# ============================================================

def test_recovered_revenue_cannot_exceed_risk():

    batch = make_batch([
        make_transaction(
            amount=100,
            recovered=101
        )
    ])

    with pytest.raises(ValueError):
        BatchAnalytics().analyze(batch)


def test_negative_revenue_is_rejected():

    batch = make_batch([
        make_transaction(
            amount=-10,
            recovered=0
        )
    ])

    with pytest.raises(ValueError):
        BatchAnalytics().analyze(batch)


def test_negative_recovered_revenue_is_rejected():

    batch = make_batch([
        make_transaction(
            amount=100,
            recovered=-1
        )
    ])

    with pytest.raises(ValueError):
        BatchAnalytics().analyze(batch)


def test_non_numeric_revenue_at_risk_is_rejected():

    batch = make_batch([
        make_transaction(
            amount="invalid",
            recovered=0
        )
    ])

    with pytest.raises(TypeError):
        BatchAnalytics().analyze(batch)


def test_non_numeric_recovered_revenue_is_rejected():

    batch = make_batch([
        make_transaction(
            amount=100,
            recovered="invalid"
        )
    ])

    with pytest.raises(TypeError):
        BatchAnalytics().analyze(batch)


def test_transaction_must_be_dictionary():

    batch = make_batch([
        "invalid transaction"
    ])

    with pytest.raises(TypeError):
        BatchAnalytics().analyze(batch)


def test_transaction_id_is_required():

    transaction = make_transaction()

    del transaction["transaction_id"]

    with pytest.raises(
        ValueError,
        match="transaction_id"
    ):
        BatchAnalytics().analyze(
            make_batch([transaction])
        )


def test_transactions_must_be_list():

    batch = {
        "status": "completed",
        "transactions": "invalid"
    }

    with pytest.raises(TypeError):
        BatchAnalytics().analyze(batch)


def test_batch_status_field_is_required():

    with pytest.raises(ValueError):
        BatchAnalytics().analyze({
            "transactions": []
        })


def test_non_dictionary_batch_is_rejected():

    with pytest.raises(TypeError):
        BatchAnalytics().analyze([])


def test_empty_batch_is_allowed():

    batch = make_batch([])

    result = BatchAnalytics().analyze(batch)

    assert (
        result["summary"]
        ["total_transactions"]
        == 0
    )

    assert (
        result["summary"]
        ["revenue_at_risk"]
        == 0
    )

    assert (
        result["summary"]
        ["revenue_recovered"]
        == 0
    )

    assert (
        result["summary"]
        ["revenue_recovery_rate"]
        == 0.0
    )

    assert (
        result["summary"]
        ["transaction_recovery_rate"]
        == 0.0
    )


# ============================================================
# DEFAULT VALUE / ZERO DIVISION
# ============================================================

def test_zero_revenue_transaction():

    batch = make_batch([
        make_transaction(
            amount=0,
            recovered=0,
            status="not_recovered"
        )
    ])

    result = BatchAnalytics().analyze(batch)

    summary = result["summary"]

    assert summary["revenue_at_risk"] == 0
    assert summary["revenue_recovered"] == 0
    assert summary["revenue_recovery_rate"] == 0.0


# ============================================================
# FILE ANALYSIS
# ============================================================

def test_analyze_file(tmp_path):

    batch = make_batch([
        make_transaction(
            transaction_id="FILE_TX"
        )
    ])

    input_file = tmp_path / "batch.json"

    with open(
        input_file,
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            batch,
            file,
            indent=2
        )

    result = BatchAnalytics().analyze_file(
        str(input_file)
    )

    assert result["status"] == "success"

    assert (
        result["summary"]
        ["total_transactions"]
        == 1
    )

    assert (
        result["summary"]
        ["revenue_recovered"]
        == 100
    )


def test_analyze_file_missing_file():

    with pytest.raises(FileNotFoundError):

        BatchAnalytics().analyze_file(
            "does_not_exist.json"
        )


def test_analyze_file_invalid_json(tmp_path):

    input_file = tmp_path / "invalid.json"

    with open(
        input_file,
        "w",
        encoding="utf-8"
    ) as file:
        file.write(
            "{ invalid json"
        )

    with pytest.raises(
        json.JSONDecodeError
    ):
        BatchAnalytics().analyze_file(
            str(input_file)
        )


# ============================================================
# SAVE RESULT
# ============================================================

def test_save_result(tmp_path, monkeypatch):

    batch = make_batch([
        make_transaction()
    ])

    result = BatchAnalytics().analyze(
        batch
    )

    import analytics

    monkeypatch.setattr(
        analytics,
        "ANALYTICS_RESULT_DIR",
        str(tmp_path)
    )

    path = BatchAnalytics.save_result(
        result
    )

    assert path
    assert os.path.isfile(path)
    assert path.endswith(".json")

    with open(
        path,
        "r",
        encoding="utf-8"
    ) as file:
        saved = json.load(file)

    assert saved["status"] == "success"

    assert (
        saved["summary"]
        ["revenue_recovered"]
        == 100
    )