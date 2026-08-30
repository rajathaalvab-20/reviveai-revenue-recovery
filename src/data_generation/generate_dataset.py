import os
import random
import numpy as np
import pandas as pd
from faker import Faker


# ============================================================
# REVIVEAI - SYNTHETIC PAYMENT DATASET GENERATOR
# ============================================================

SEED = 42

random.seed(SEED)
np.random.seed(SEED)

fake = Faker()
Faker.seed(SEED)

# ------------------------------------------------------------
# Configuration
# ------------------------------------------------------------

N_TRANSACTIONS = 50_000
N_CUSTOMERS = 10_000

OUTPUT_DIR = os.path.join("data", "raw")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "payment_events.csv")

os.makedirs(OUTPUT_DIR, exist_ok=True)


# ============================================================
# CUSTOMER GENERATION
# ============================================================

print("=" * 60)
print("REVIVEAI - SYNTHETIC PAYMENT DATA GENERATOR")
print("=" * 60)

print("\nGenerating customers...")

customers = []

for i in range(N_CUSTOMERS):

    customer_id = f"C{i + 1:05d}"

    customer_type = random.choices(
        ["NEW", "RETURNING", "LOYAL"],
        weights=[0.20, 0.50, 0.30]
    )[0]

    if customer_type == "NEW":
        customer_age_days = random.randint(1, 60)
        previous_transactions = random.randint(0, 3)
        previous_success_rate = random.uniform(0.50, 0.90)

    elif customer_type == "RETURNING":
        customer_age_days = random.randint(61, 500)
        previous_transactions = random.randint(4, 30)
        previous_success_rate = random.uniform(0.75, 0.98)

    else:
        customer_age_days = random.randint(501, 2000)
        previous_transactions = random.randint(20, 100)
        previous_success_rate = random.uniform(0.88, 0.995)

    customers.append({
        "customer_id": customer_id,
        "customer_type": customer_type,
        "customer_age_days": customer_age_days,
        "previous_transactions": previous_transactions,
        "previous_success_rate": round(previous_success_rate, 4)
    })


customers_df = pd.DataFrame(customers)


# ============================================================
# PAYMENT GENERATION
# ============================================================

print("Generating payment events...")

payment_methods = [
    "UPI",
    "CREDIT_CARD",
    "DEBIT_CARD",
    "NET_BANKING",
    "WALLET"
]

payment_method_weights = [
    0.40,
    0.25,
    0.20,
    0.10,
    0.05
]


failure_definitions = {

    "BANK_TIMEOUT": {
        "type": "TRANSIENT",
        "base_probability": 0.88
    },

    "NETWORK_ERROR": {
        "type": "TRANSIENT",
        "base_probability": 0.85
    },

    "GATEWAY_TIMEOUT": {
        "type": "TRANSIENT",
        "base_probability": 0.87
    },

    "BANK_SERVER_ERROR": {
        "type": "TRANSIENT",
        "base_probability": 0.82
    },

    "INSUFFICIENT_FUNDS": {
        "type": "CUSTOMER_ACTION_REQUIRED",
        "base_probability": 0.42
    },

    "EXPIRED_CARD": {
        "type": "CUSTOMER_ACTION_REQUIRED",
        "base_probability": 0.35
    },

    "AUTHENTICATION_FAILED": {
        "type": "CUSTOMER_ACTION_REQUIRED",
        "base_probability": 0.45
    },

    "INVALID_CARD": {
        "type": "HARD_FAILURE",
        "base_probability": 0.08
    },

    "CARD_BLOCKED": {
        "type": "HARD_FAILURE",
        "base_probability": 0.04
    },

    "FRAUD_SUSPECTED": {
        "type": "HARD_FAILURE",
        "base_probability": 0.01
    }
}


failure_codes = list(failure_definitions.keys())

failure_weights = [
    0.16,  # BANK_TIMEOUT
    0.13,  # NETWORK_ERROR
    0.10,  # GATEWAY_TIMEOUT
    0.07,  # BANK_SERVER_ERROR
    0.18,  # INSUFFICIENT_FUNDS
    0.10,  # EXPIRED_CARD
    0.08,  # AUTHENTICATION_FAILED
    0.08,  # INVALID_CARD
    0.06,  # CARD_BLOCKED
    0.04   # FRAUD_SUSPECTED
]


records = []


# ============================================================
# GENERATE TRANSACTIONS
# ============================================================

for i in range(N_TRANSACTIONS):

    customer = customers[random.randrange(N_CUSTOMERS)]

    transaction_id = f"TX{i + 1:07d}"

    amount = round(
        np.random.lognormal(
            mean=np.log(2500),
            sigma=1.0
        ),
        2
    )

    # Keep amounts realistic
    amount = min(max(amount, 100), 100000)

    payment_method = random.choices(
        payment_methods,
        weights=payment_method_weights
    )[0]

    # Transaction time
    hour = random.randint(0, 23)

    is_weekend = random.choice([0, 1])

    time_since_failure = random.randint(1, 1440)

    # Previous retry attempts
    attempt_count = random.choices(
        [0, 1, 2, 3],
        weights=[0.60, 0.25, 0.10, 0.05]
    )[0]

    # Failure
    failure_code = random.choices(
        failure_codes,
        weights=failure_weights
    )[0]

    failure_type = failure_definitions[
        failure_code
    ]["type"]

    base_probability = failure_definitions[
        failure_code
    ]["base_probability"]

    # --------------------------------------------------------
    # Recovery probability calculation
    # --------------------------------------------------------

    probability = base_probability

    # Customer loyalty effect
    if customer["customer_type"] == "LOYAL":
        probability += 0.08

    elif customer["customer_type"] == "RETURNING":
        probability += 0.04

    else:
        probability -= 0.03

    # Historical success effect
    probability += (
        customer["previous_success_rate"] - 0.80
    ) * 0.25

    # Retry penalty
    probability -= attempt_count * 0.10

    # Very high-value payments are slightly harder
    if amount > 50000:
        probability -= 0.08

    elif amount > 20000:
        probability -= 0.03

    # Timing effects
    if hour >= 0 and hour <= 5:
        probability -= 0.03

    # Weekend effect
    if is_weekend:
        probability -= 0.01

    # Small random noise
    probability += np.random.normal(0, 0.025)

    # Keep probability within realistic bounds
    probability = float(
        np.clip(probability, 0.01, 0.98)
    )

    # --------------------------------------------------------
    # Ground truth outcome
    # --------------------------------------------------------

    actual_recovery = int(
        np.random.random() < probability
    )

    if actual_recovery == 1:

        recovered_amount = amount

        final_status = "RECOVERED"

        recovery_attempts = max(
            1,
            attempt_count + 1
        )

    else:

        recovered_amount = 0.0

        recovery_attempts = min(
            attempt_count + 1,
            3
        )

        if recovery_attempts >= 3:

            final_status = "ESCALATED"

        else:

            final_status = "UNRECOVERED"

    records.append({

        "transaction_id": transaction_id,

        "customer_id": customer["customer_id"],

        "amount": amount,

        "payment_method": payment_method,

        "customer_type": customer["customer_type"],

        "customer_age_days": customer["customer_age_days"],

        "previous_transactions": customer["previous_transactions"],

        "previous_success_rate": customer["previous_success_rate"],

        "failure_code": failure_code,

        "failure_type": failure_type,

        "attempt_count": attempt_count,

        "time_since_failure_min": time_since_failure,

        "hour_of_day": hour,

        "is_weekend": is_weekend,

        # This is ground truth.
        # It will NOT be used as an input feature
        # when training the ML model.
        "true_recovery_probability": round(
            probability,
            4
        ),

        "actual_recovery": actual_recovery,

        "recovered_amount": round(
            recovered_amount,
            2
        ),

        "recovery_attempts": recovery_attempts,

        "final_status": final_status
    })


# ============================================================
# CREATE DATAFRAME
# ============================================================

df = pd.DataFrame(records)


# ============================================================
# SAVE DATASET
# ============================================================

df.to_csv(
    OUTPUT_FILE,
    index=False
)


# ============================================================
# REPORT
# ============================================================

print("\n" + "=" * 60)
print("DATASET GENERATED SUCCESSFULLY")
print("=" * 60)

print(f"\nRows              : {len(df):,}")
print(f"Columns           : {len(df.columns)}")

print(f"\nOutput:")
print(f"  {OUTPUT_FILE}")

print("\nFailure distribution:")
print(
    df["failure_code"]
    .value_counts()
    .to_string()
)

print("\nFailure type distribution:")
print(
    df["failure_type"]
    .value_counts()
    .to_string()
)

print("\nFinal status distribution:")
print(
    df["final_status"]
    .value_counts()
    .to_string()
)

print(
    f"\nOverall recovery rate: "
    f"{df['actual_recovery'].mean() * 100:.2f}%"
)

print(
    f"Revenue at risk: "
    f"₹{df['amount'].sum():,.2f}"
)

print(
    f"Revenue recovered: "
    f"₹{df['recovered_amount'].sum():,.2f}"
)

print("\nFirst 5 records:")
print(df.head().to_string())

print("\n" + "=" * 60)
print("DONE")
print("=" * 60)