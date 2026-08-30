import pandas as pd


DATA_FILE = "data/raw/payment_events.csv"


print("=" * 70)
print("REVIVEAI - DATASET VALIDATION")
print("=" * 70)


# ------------------------------------------------------------
# Load dataset
# ------------------------------------------------------------

df = pd.read_csv(DATA_FILE)

print(f"\nDataset shape: {df.shape}")


# ------------------------------------------------------------
# 1. Missing values
# ------------------------------------------------------------

print("\n" + "-" * 70)
print("1. MISSING VALUES")
print("-" * 70)

missing = df.isnull().sum()

print(missing[missing > 0])

if missing.sum() == 0:
    print("✓ No missing values")


# ------------------------------------------------------------
# 2. Duplicate transactions
# ------------------------------------------------------------

print("\n" + "-" * 70)
print("2. DUPLICATE TRANSACTIONS")
print("-" * 70)

duplicates = df["transaction_id"].duplicated().sum()

print(f"Duplicate transaction IDs: {duplicates}")

if duplicates == 0:
    print("✓ No duplicate transactions")


# ------------------------------------------------------------
# 3. Customer statistics
# ------------------------------------------------------------

print("\n" + "-" * 70)
print("3. CUSTOMER STATISTICS")
print("-" * 70)

print(
    f"Unique customers: "
    f"{df['customer_id'].nunique():,}"
)

print("\nCustomer type distribution:")

print(
    df["customer_type"]
    .value_counts()
)


# ------------------------------------------------------------
# 4. Recovery by failure type
# ------------------------------------------------------------

print("\n" + "-" * 70)
print("4. RECOVERY RATE BY FAILURE TYPE")
print("-" * 70)

failure_recovery = (
    df.groupby("failure_type")["actual_recovery"]
    .agg(
        transactions="count",
        recovery_rate="mean"
    )
)

failure_recovery["recovery_rate"] *= 100

print(
    failure_recovery
    .round(2)
    .sort_values("recovery_rate", ascending=False)
)


# ------------------------------------------------------------
# 5. Recovery by failure code
# ------------------------------------------------------------

print("\n" + "-" * 70)
print("5. RECOVERY RATE BY FAILURE CODE")
print("-" * 70)

code_recovery = (
    df.groupby("failure_code")["actual_recovery"]
    .agg(
        transactions="count",
        recovery_rate="mean"
    )
)

code_recovery["recovery_rate"] *= 100

print(
    code_recovery
    .round(2)
    .sort_values("recovery_rate", ascending=False)
)


# ------------------------------------------------------------
# 6. Recovery by retry attempts
# ------------------------------------------------------------

print("\n" + "-" * 70)
print("6. RECOVERY RATE BY ATTEMPT COUNT")
print("-" * 70)

attempt_recovery = (
    df.groupby("attempt_count")["actual_recovery"]
    .agg(
        transactions="count",
        recovery_rate="mean"
    )
)

attempt_recovery["recovery_rate"] *= 100

print(
    attempt_recovery
    .round(2)
)


# ------------------------------------------------------------
# 7. Recovery by customer type
# ------------------------------------------------------------

print("\n" + "-" * 70)
print("7. RECOVERY RATE BY CUSTOMER TYPE")
print("-" * 70)

customer_recovery = (
    df.groupby("customer_type")["actual_recovery"]
    .agg(
        transactions="count",
        recovery_rate="mean"
    )
)

customer_recovery["recovery_rate"] *= 100

print(
    customer_recovery
    .round(2)
    .sort_values("recovery_rate", ascending=False)
)


# ------------------------------------------------------------
# 8. Revenue analysis
# ------------------------------------------------------------

print("\n" + "-" * 70)
print("8. REVENUE ANALYSIS")
print("-" * 70)

total_revenue = df["amount"].sum()

recovered_revenue = df["recovered_amount"].sum()

print(
    f"Total revenue at risk : ₹{total_revenue:,.2f}"
)

print(
    f"Recovered revenue     : ₹{recovered_revenue:,.2f}"
)

print(
    f"Revenue recovery rate : "
    f"{recovered_revenue / total_revenue * 100:.2f}%"
)


# ------------------------------------------------------------
# 9. Probability calibration check
# ------------------------------------------------------------

print("\n" + "-" * 70)
print("9. PROBABILITY CALIBRATION CHECK")
print("-" * 70)

df["probability_bucket"] = pd.cut(
    df["true_recovery_probability"],
    bins=[0, 0.2, 0.4, 0.6, 0.8, 1.0],
    labels=[
        "0-20%",
        "20-40%",
        "40-60%",
        "60-80%",
        "80-100%"
    ],
    include_lowest=True
)

calibration = (
    df.groupby(
        "probability_bucket",
        observed=False
    )["actual_recovery"]
    .agg(
        transactions="count",
        actual_recovery_rate="mean"
    )
)

calibration["actual_recovery_rate"] *= 100

print(
    calibration.round(2)
)


# ------------------------------------------------------------
# Final checks
# ------------------------------------------------------------

print("\n" + "=" * 70)
print("VALIDATION COMPLETE")
print("=" * 70)