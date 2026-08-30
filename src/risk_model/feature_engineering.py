import numpy as np
import pandas as pd


# ============================================================
# REVIVEAI - SHARED FEATURE ENGINEERING
# ============================================================
#
# IMPORTANT:
# This module is the SINGLE SOURCE OF TRUTH for risk-model
# feature engineering.
#
# Training, calibration, evaluation and inference MUST use
# this same implementation.
# ============================================================


CATEGORICAL_FEATURES = [
    "payment_method",
    "customer_type",
    "failure_code",
    "failure_type"
]


FEATURES = [

    # Original numerical
    "amount",
    "customer_age_days",
    "previous_transactions",
    "previous_success_rate",
    "attempt_count",
    "time_since_failure_min",
    "hour_of_day",
    "is_weekend",

    # Transaction features
    "log_amount",
    "high_value_transaction",
    "very_high_value_transaction",

    # Customer features
    "customer_reliability",
    "customer_history_strength",
    "is_established_customer",
    "is_long_term_customer",

    # Retry features
    "retry_pressure",
    "has_previous_retry",
    "retry_limit_reached",

    # Time features
    "log_time_since_failure",
    "failure_recent",
    "failure_very_recent",
    "failure_old",
    "is_business_hour",
    "is_night",

    # Failure features
    "is_transient_failure",
    "is_customer_action_failure",
    "is_hard_failure",
    "retryable_failure",
    "requires_customer_action",

    # Interaction features
    "reliability_x_transient",
    "reliability_x_hard_failure",
    "attempt_x_transient",
    "attempt_x_hard_failure",
    "value_x_reliability",
    "value_x_transient",

    # Categorical
    "payment_method",
    "customer_type",
    "failure_code",
    "failure_type"
]


NUMERIC_FEATURES = [
    feature
    for feature in FEATURES
    if feature not in CATEGORICAL_FEATURES
]


def create_features(df: pd.DataFrame) -> pd.DataFrame:

    data = df.copy()

    # --------------------------------------------------------
    # Required input validation
    # --------------------------------------------------------

    required_columns = [
        "amount",
        "payment_method",
        "customer_type",
        "customer_age_days",
        "previous_transactions",
        "previous_success_rate",
        "failure_code",
        "failure_type",
        "attempt_count",
        "time_since_failure_min",
        "hour_of_day",
        "is_weekend"
    ]

    missing = [
        column
        for column in required_columns
        if column not in data.columns
    ]

    if missing:
        raise ValueError(
            "Missing required input columns: "
            + ", ".join(missing)
        )

    # --------------------------------------------------------
    # Transaction value
    # --------------------------------------------------------

    data["log_amount"] = np.log1p(
        data["amount"]
    )

    data["high_value_transaction"] = (
        data["amount"] >= 25000
    ).astype(int)

    data["very_high_value_transaction"] = (
        data["amount"] >= 50000
    ).astype(int)

    # --------------------------------------------------------
    # Customer reliability
    # --------------------------------------------------------

    data["customer_reliability"] = (
        data["previous_success_rate"]
        * np.log1p(
            data["previous_transactions"]
        )
    )

    data["customer_history_strength"] = (
        np.log1p(
            data["previous_transactions"]
        )
        * data["previous_success_rate"]
    )

    # --------------------------------------------------------
    # Customer experience
    # --------------------------------------------------------

    data["is_established_customer"] = (
        data["customer_age_days"] >= 180
    ).astype(int)

    data["is_long_term_customer"] = (
        data["customer_age_days"] >= 365
    ).astype(int)

    # --------------------------------------------------------
    # Retry pressure
    # --------------------------------------------------------

    data["retry_pressure"] = (
        data["attempt_count"] / 3.0
    )

    data["has_previous_retry"] = (
        data["attempt_count"] > 0
    ).astype(int)

    data["retry_limit_reached"] = (
        data["attempt_count"] >= 3
    ).astype(int)

    # --------------------------------------------------------
    # Failure age
    # --------------------------------------------------------

    data["log_time_since_failure"] = np.log1p(
        data["time_since_failure_min"]
    )

    data["failure_recent"] = (
        data["time_since_failure_min"] <= 60
    ).astype(int)

    data["failure_very_recent"] = (
        data["time_since_failure_min"] <= 15
    ).astype(int)

    data["failure_old"] = (
        data["time_since_failure_min"] >= 720
    ).astype(int)

    # --------------------------------------------------------
    # Time features
    # --------------------------------------------------------

    data["is_business_hour"] = (
        (data["hour_of_day"] >= 9)
        & (data["hour_of_day"] <= 18)
    ).astype(int)

    data["is_night"] = (
        (data["hour_of_day"] < 6)
        | (data["hour_of_day"] >= 22)
    ).astype(int)

    # --------------------------------------------------------
    # Failure category features
    # --------------------------------------------------------

    transient_codes = [
        "BANK_TIMEOUT",
        "NETWORK_ERROR",
        "GATEWAY_TIMEOUT",
        "BANK_SERVER_ERROR"
    ]

    customer_action_codes = [
        "INSUFFICIENT_FUNDS",
        "EXPIRED_CARD",
        "AUTHENTICATION_FAILED"
    ]

    hard_failure_codes = [
        "INVALID_CARD",
        "CARD_BLOCKED",
        "FRAUD_SUSPECTED"
    ]

    data["is_transient_failure"] = (
        data["failure_code"]
        .isin(transient_codes)
    ).astype(int)

    data["is_customer_action_failure"] = (
        data["failure_code"]
        .isin(customer_action_codes)
    ).astype(int)

    data["is_hard_failure"] = (
        data["failure_code"]
        .isin(hard_failure_codes)
    ).astype(int)

    # --------------------------------------------------------
    # Recovery suitability
    # --------------------------------------------------------

    data["retryable_failure"] = (
        data["failure_code"].isin(
            transient_codes
        )
    ).astype(int)

    data["requires_customer_action"] = (
        data["failure_code"].isin(
            customer_action_codes
        )
    ).astype(int)

    # --------------------------------------------------------
    # Interaction features
    # --------------------------------------------------------

    data["reliability_x_transient"] = (
        data["previous_success_rate"]
        * data["is_transient_failure"]
    )

    data["reliability_x_hard_failure"] = (
        data["previous_success_rate"]
        * data["is_hard_failure"]
    )

    data["attempt_x_transient"] = (
        data["attempt_count"]
        * data["is_transient_failure"]
    )

    data["attempt_x_hard_failure"] = (
        data["attempt_count"]
        * data["is_hard_failure"]
    )

    data["value_x_reliability"] = (
        data["amount"]
        * data["previous_success_rate"]
    )

    data["value_x_transient"] = (
        data["amount"]
        * data["is_transient_failure"]
    )

    # --------------------------------------------------------
    # Final schema validation
    # --------------------------------------------------------

    missing_features = [
        feature
        for feature in FEATURES
        if feature not in data.columns
    ]

    if missing_features:
        raise RuntimeError(
            "Feature engineering failed. "
            "Missing generated features: "
            + ", ".join(missing_features)
        )

    return data