import pandas as pd


# ============================================================
# REVIVEAI - RECOVERY SCENARIO VALIDATION
# ============================================================

PAYMENT_FILE = "data/raw/payment_events.csv"
SCENARIO_FILE = "data/processed/recovery_scenarios.csv"


print("=" * 75)
print("REVIVEAI - RECOVERY SCENARIO VALIDATION")
print("=" * 75)


# ============================================================
# LOAD DATA
# ============================================================

payments = pd.read_csv(PAYMENT_FILE)
scenarios = pd.read_csv(SCENARIO_FILE)

print("\nLoaded:")
print(f"Payment events      : {len(payments):,}")
print(f"Recovery scenarios  : {len(scenarios):,}")


errors = []


def check(condition, message):
    """
    Register validation failure.
    """
    if not condition:
        errors.append(message)


# ============================================================
# 1. BASIC DATA INTEGRITY
# ============================================================

print("\n" + "-" * 75)
print("1. BASIC DATA INTEGRITY")
print("-" * 75)


check(
    scenarios["scenario_id"].is_unique,
    "Duplicate scenario IDs detected."
)

check(
    scenarios["transaction_id"].is_unique,
    "Duplicate transaction IDs detected in scenarios."
)

check(
    not scenarios.isnull().any().any(),
    "Missing values detected."
)

check(
    len(scenarios) == len(payments),
    "Scenario count does not match payment count."
)

if not errors:
    print("✓ Scenario IDs are unique")
    print("✓ Transaction IDs are unique")
    print("✓ No missing values")
    print("✓ Scenario count matches payment count")


# ============================================================
# 2. VALID ACTIONS
# ============================================================

print("\n" + "-" * 75)
print("2. ACTION VALIDATION")
print("-" * 75)


valid_actions = {
    "RETRY_PAYMENT",
    "PAYMENT_REMINDER",
    "REQUEST_PAYMENT_METHOD_UPDATE",
    "HUMAN_REVIEW",
    "ESCALATE"
}


invalid_actions = set(
    scenarios["allowed_action"]
) - valid_actions


check(
    len(invalid_actions) == 0,
    f"Invalid actions found: {invalid_actions}"
)

if len(invalid_actions) == 0:
    print("✓ All actions are valid")

print("\nAction distribution:")

print(
    scenarios["allowed_action"]
    .value_counts()
)


# ============================================================
# 3. FRAUD PROTECTION
# ============================================================

print("\n" + "-" * 75)
print("3. FRAUD PROTECTION")
print("-" * 75)


fraud = scenarios[
    scenarios["failure_code"] == "FRAUD_SUSPECTED"
]


fraud_not_human = fraud[
    fraud["allowed_action"] != "HUMAN_REVIEW"
]


check(
    len(fraud_not_human) == 0,
    "Fraud cases found without HUMAN_REVIEW."
)


if len(fraud_not_human) == 0:
    print(
        f"✓ All {len(fraud):,} fraud cases require HUMAN_REVIEW"
    )


# ============================================================
# 4. HARD FAILURE PROTECTION
# ============================================================

print("\n" + "-" * 75)
print("4. HARD FAILURE PROTECTION")
print("-" * 75)


hard_failures = scenarios[
    scenarios["failure_type"] == "HARD_FAILURE"
]


hard_failure_retries = hard_failures[
    hard_failures["allowed_action"] == "RETRY_PAYMENT"
]


check(
    len(hard_failure_retries) == 0,
    "Hard failures incorrectly allowed automatic retry."
)


if len(hard_failure_retries) == 0:
    print(
        f"✓ No automatic retries for "
        f"{len(hard_failures):,} hard-failure cases"
    )


# ============================================================
# 5. RETRY LIMIT
# ============================================================

print("\n" + "-" * 75)
print("5. RETRY LIMIT VALIDATION")
print("-" * 75)


retry_limit_violations = scenarios[
    (scenarios["allowed_action"] == "RETRY_PAYMENT")
    &
    (scenarios["initial_attempt_count"] >= 2)
]


check(
    len(retry_limit_violations) == 0,
    "Retry allowed after maximum retry limit."
)


if len(retry_limit_violations) == 0:
    print("✓ Retry limit enforced")


# ============================================================
# 6. ESCALATION CONSISTENCY
# ============================================================

print("\n" + "-" * 75)
print("6. ESCALATION CONSISTENCY")
print("-" * 75)


escalated_without_flag = scenarios[
    (scenarios["final_state"] == "ESCALATED")
    &
    (scenarios["escalation_required"] != 1)
]


check(
    len(escalated_without_flag) == 0,
    "ESCALATED cases without escalation_required = 1."
)


flagged_without_escalation = scenarios[
    (scenarios["escalation_required"] == 1)
    &
    (scenarios["final_state"] != "ESCALATED")
]


check(
    len(flagged_without_escalation) == 0,
    "Escalation flag set but final state is not ESCALATED."
)


if (
    len(escalated_without_flag) == 0
    and
    len(flagged_without_escalation) == 0
):
    print("✓ Escalation states are consistent")


# ============================================================
# 7. RECOVERY VERIFICATION
# ============================================================

print("\n" + "-" * 75)
print("7. RECOVERY VERIFICATION")
print("-" * 75)


recovered_without_verification = scenarios[
    (scenarios["final_state"] == "RECOVERED")
    &
    (scenarios["verification_result"] != "VERIFIED_SUCCESS")
]


check(
    len(recovered_without_verification) == 0,
    "Recovered cases without VERIFIED_SUCCESS."
)


if len(recovered_without_verification) == 0:
    print(
        "✓ Every RECOVERED case has VERIFIED_SUCCESS"
    )


# ============================================================
# 8. RECOVERED AMOUNT VALIDATION
# ============================================================

print("\n" + "-" * 75)
print("8. RECOVERED AMOUNT VALIDATION")
print("-" * 75)


invalid_amounts = scenarios[
    (scenarios["recovered_amount"] < 0)
    |
    (scenarios["recovered_amount"] > scenarios["amount"])
]


check(
    len(invalid_amounts) == 0,
    "Invalid recovered amounts detected."
)


recovered_zero = scenarios[
    (scenarios["final_state"] == "RECOVERED")
    &
    (scenarios["recovered_amount"] <= 0)
]


check(
    len(recovered_zero) == 0,
    "RECOVERED cases have zero recovered amount."
)


if len(invalid_amounts) == 0:
    print("✓ Recovered amounts are valid")

if len(recovered_zero) == 0:
    print("✓ Every recovered case has positive recovered revenue")


# ============================================================
# 9. CUSTOMER ACTION CASES
# ============================================================

print("\n" + "-" * 75)
print("9. CUSTOMER-ACTION VALIDATION")
print("-" * 75)


customer_action_codes = {
    "INSUFFICIENT_FUNDS",
    "EXPIRED_CARD",
    "AUTHENTICATION_FAILED"
}


customer_action_cases = scenarios[
    scenarios["failure_code"].isin(customer_action_codes)
]


invalid_customer_actions = customer_action_cases[
    ~customer_action_cases["allowed_action"].isin([
        "PAYMENT_REMINDER"
    ])
]


check(
    len(invalid_customer_actions) == 0,
    "Customer-action failures have invalid automated actions."
)


if len(invalid_customer_actions) == 0:
    print(
        f"✓ Customer-action failures handled correctly "
        f"({len(customer_action_cases):,} cases)"
    )


# ============================================================
# 10. REVENUE CONSISTENCY
# ============================================================

print("\n" + "-" * 75)
print("10. REVENUE CONSISTENCY")
print("-" * 75)


recovered_states_revenue = scenarios.loc[
    scenarios["final_state"] == "RECOVERED",
    "recovered_amount"
].sum()


non_recovered_revenue = scenarios.loc[
    scenarios["final_state"] != "RECOVERED",
    "recovered_amount"
].sum()


check(
    non_recovered_revenue == 0,
    "Non-recovered states contain recovered revenue."
)


if non_recovered_revenue == 0:
    print("✓ Non-recovered cases contain ₹0 recovered revenue")

print(
    f"Verified recovered revenue: "
    f"₹{recovered_states_revenue:,.2f}"
)


# ============================================================
# 11. CROSS-CHECK WITH PAYMENT DATA
# ============================================================

print("\n" + "-" * 75)
print("11. PAYMENT / SCENARIO CONSISTENCY")
print("-" * 75)


merged = scenarios.merge(
    payments[
        [
            "transaction_id",
            "amount",
            "failure_code",
            "failure_type",
            "actual_recovery"
        ]
    ],
    on="transaction_id",
    suffixes=("_scenario", "_payment")
)


check(
    len(merged) == len(scenarios),
    "Scenario/payment merge mismatch."
)


amount_mismatch = merged[
    merged["amount_scenario"] != merged["amount_payment"]
]


failure_mismatch = merged[
    merged["failure_code_scenario"]
    !=
    merged["failure_code_payment"]
]


check(
    len(amount_mismatch) == 0,
    "Transaction amount mismatch between datasets."
)


check(
    len(failure_mismatch) == 0,
    "Failure code mismatch between datasets."
)


if len(amount_mismatch) == 0:
    print("✓ Transaction amounts match")

if len(failure_mismatch) == 0:
    print("✓ Failure codes match")


# ============================================================
# FINAL RESULT
# ============================================================

print("\n" + "=" * 75)
print("FINAL VALIDATION RESULT")
print("=" * 75)


if len(errors) == 0:

    print("\n✓ ALL VALIDATION CHECKS PASSED")
    print("\nThe recovery scenario dataset is structurally consistent.")
    print("Ready for the next implementation stage.")

else:

    print(
        f"\n✗ VALIDATION FAILED "
        f"({len(errors)} issue(s))"
    )

    print("\nProblems:")

    for i, error in enumerate(errors, 1):

        print(
            f"{i}. {error}"
        )


print("\n" + "=" * 75)