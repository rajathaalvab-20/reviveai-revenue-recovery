import os
import pandas as pd
from sklearn.model_selection import train_test_split


# ============================================================
# REVIVEAI - CUSTOMER LEVEL DATA SPLIT
# ============================================================

DATA_FILE = "data/raw/payment_events.csv"
OUTPUT_DIR = "data/splits"

os.makedirs(OUTPUT_DIR, exist_ok=True)


print("=" * 70)
print("REVIVEAI - CUSTOMER LEVEL DATA SPLIT")
print("=" * 70)


# ------------------------------------------------------------
# Load
# ------------------------------------------------------------

df = pd.read_csv(DATA_FILE)

print(f"\nTotal transactions : {len(df):,}")
print(
    f"Unique customers   : "
    f"{df['customer_id'].nunique():,}"
)


# ------------------------------------------------------------
# Unique customers
# ------------------------------------------------------------

customers = df["customer_id"].unique()


# ------------------------------------------------------------
# 70% Train / 30% Temporary
# ------------------------------------------------------------

train_customers, temp_customers = train_test_split(
    customers,
    test_size=0.30,
    random_state=42
)


# ------------------------------------------------------------
# 15% Validation / 15% Test
# ------------------------------------------------------------

val_customers, test_customers = train_test_split(
    temp_customers,
    test_size=0.50,
    random_state=42
)


# ------------------------------------------------------------
# Create datasets
# ------------------------------------------------------------

train_df = df[
    df["customer_id"].isin(train_customers)
].copy()

val_df = df[
    df["customer_id"].isin(val_customers)
].copy()

test_df = df[
    df["customer_id"].isin(test_customers)
].copy()


# ------------------------------------------------------------
# Save
# ------------------------------------------------------------

train_file = os.path.join(
    OUTPUT_DIR,
    "train.csv"
)

val_file = os.path.join(
    OUTPUT_DIR,
    "validation.csv"
)

test_file = os.path.join(
    OUTPUT_DIR,
    "test.csv"
)


train_df.to_csv(
    train_file,
    index=False
)

val_df.to_csv(
    val_file,
    index=False
)

test_df.to_csv(
    test_file,
    index=False
)


# ------------------------------------------------------------
# Verify customer separation
# ------------------------------------------------------------

train_ids = set(train_df["customer_id"])
val_ids = set(val_df["customer_id"])
test_ids = set(test_df["customer_id"])


train_val_overlap = train_ids & val_ids
train_test_overlap = train_ids & test_ids
val_test_overlap = val_ids & test_ids


print("\n" + "-" * 70)
print("SPLIT RESULTS")
print("-" * 70)

print(
    f"Train customers      : {len(train_ids):,}"
)

print(
    f"Validation customers : {len(val_ids):,}"
)

print(
    f"Test customers       : {len(test_ids):,}"
)

print()

print(
    f"Train transactions      : {len(train_df):,}"
)

print(
    f"Validation transactions : {len(val_df):,}"
)

print(
    f"Test transactions       : {len(test_df):,}"
)


print("\n" + "-" * 70)
print("LEAKAGE CHECK")
print("-" * 70)

print(
    f"Train/Validation overlap : "
    f"{len(train_val_overlap)}"
)

print(
    f"Train/Test overlap       : "
    f"{len(train_test_overlap)}"
)

print(
    f"Validation/Test overlap  : "
    f"{len(val_test_overlap)}"
)


# ------------------------------------------------------------
# Final check
# ------------------------------------------------------------

if (
    len(train_val_overlap) == 0
    and
    len(train_test_overlap) == 0
    and
    len(val_test_overlap) == 0
):

    print("\n✓ CUSTOMER LEVEL SPLIT PASSED")

else:

    print("\n✗ DATA LEAKAGE DETECTED")


print("\nFiles created:")

print(f"  {train_file}")
print(f"  {val_file}")
print(f"  {test_file}")

print("\n" + "=" * 70)