import os
import random
import pandas as pd
import numpy as np


# ============================================================
# REVIVEAI - RECOVERY SCENARIO GENERATOR
# ============================================================

SEED = 42

random.seed(SEED)
np.random.seed(SEED)

PAYMENT_FILE = "data/raw/payment_events.csv"
OUTPUT_DIR = "data/processed"
OUTPUT_FILE = os.path.join(
    OUTPUT_DIR,
    "recovery_scenarios.csv"
)

os.makedirs(OUTPUT_DIR, exist_ok=True)


# ============================================================
# LOAD PAYMENT DATA
# ============================================================

print("=" * 70)
print("REVIVEAI - RECOVERY SCENARIO GENERATOR")
print("=" * 70)

print("\nLoading payment dataset...")

df = pd.read_csv(PAYMENT_FILE)

print(f"Payments loaded: {len(df):,}")


# ============================================================
# SCENARIO GENERATION
# ============================================================

scenarios = []


for _, row in df.iterrows():

    failure_code = row["failure_code"]
    failure_type = row["failure_type"]

    transaction_id = row["transaction_id"]
    amount = row["amount"]

    attempt_count = int(row["attempt_count"])

    true_probability = float(
        row["true_recovery_probability"]
    )

    actual_recovery = int(
        row["actual_recovery"]
    )


    # --------------------------------------------------------
    # Determine allowed action
    # --------------------------------------------------------

    if failure_code in [
        "BANK_TIMEOUT",
        "NETWORK_ERROR",
        "GATEWAY_TIMEOUT",
        "BANK_SERVER_ERROR"
    ]:

        if attempt_count < 2:

            allowed_action = "RETRY_PAYMENT"

        else:

            allowed_action = "ESCALATE"


    elif failure_code in [
        "INSUFFICIENT_FUNDS",
        "EXPIRED_CARD",
        "AUTHENTICATION_FAILED"
    ]:

        allowed_action = "PAYMENT_REMINDER"


    elif failure_code in [
        "INVALID_CARD",
        "CARD_BLOCKED"
    ]:

        allowed_action = "REQUEST_PAYMENT_METHOD_UPDATE"


    elif failure_code == "FRAUD_SUSPECTED":

        allowed_action = "HUMAN_REVIEW"


    else:

        allowed_action = "HUMAN_REVIEW"


    # --------------------------------------------------------
    # Generate gateway behavior
    # --------------------------------------------------------

    gateway_random = random.random()


    if allowed_action == "RETRY_PAYMENT":

        # Successful payment
        if actual_recovery == 1:

            gateway_response = random.choice([
                "PAYMENT_SUCCESS",
                "PAYMENT_SUCCESS_CONFIRMED"
            ])

            verification_result = "VERIFIED_SUCCESS"

            final_state = "RECOVERED"


        else:

            # Possible technical failure
            if gateway_random < 0.45:

                gateway_response = "GATEWAY_TIMEOUT"

            elif gateway_random < 0.75:

                gateway_response = "PAYMENT_FAILED"

            elif gateway_random < 0.90:

                gateway_response = "BANK_DECLINED"

            else:

                gateway_response = "UNKNOWN_GATEWAY_ERROR"


            # Verification is performed independently
            verification_random = random.random()

            if verification_random < 0.03:

                # Important edge case:
                # gateway response failed but payment actually
                # succeeded.

                verification_result = "VERIFIED_SUCCESS"

                final_state = "RECOVERED"

            else:

                verification_result = "VERIFIED_FAILURE"

                if attempt_count >= 2:

                    final_state = "ESCALATED"

                else:

                    final_state = "RETRY_ALLOWED"


    elif allowed_action == "PAYMENT_REMINDER":

        gateway_response = "ACTION_REQUIRED"

        verification_result = "NOT_APPLICABLE"

        final_state = "CUSTOMER_ACTION_REQUIRED"


    elif allowed_action == "REQUEST_PAYMENT_METHOD_UPDATE":

        gateway_response = "ACTION_REQUIRED"

        verification_result = "NOT_APPLICABLE"

        final_state = "CUSTOMER_ACTION_REQUIRED"


    elif allowed_action == "HUMAN_REVIEW":

        gateway_response = "BLOCKED_AUTOMATION"

        verification_result = "NOT_APPLICABLE"

        final_state = "ESCALATED"


    elif allowed_action == "ESCALATE":

        gateway_response = "RETRY_LIMIT_REACHED"

        verification_result = "NOT_APPLICABLE"

        final_state = "ESCALATED"


    # --------------------------------------------------------
    # Determine recovered amount
    # --------------------------------------------------------

    if final_state == "RECOVERED":

        recovered_amount = amount

    else:

        recovered_amount = 0.0


    # --------------------------------------------------------
    # Determine escalation
    # --------------------------------------------------------

    if final_state == "ESCALATED":

        escalation_required = 1

    else:

        escalation_required = 0


    # --------------------------------------------------------
    # Scenario ID
    # --------------------------------------------------------

    scenario_id = f"SC{len(scenarios) + 1:07d}"


    scenarios.append({

        "scenario_id": scenario_id,

        "transaction_id": transaction_id,

        "amount": amount,

        "failure_code": failure_code,

        "failure_type": failure_type,

        "initial_attempt_count": attempt_count,

        "recovery_probability": true_probability,

        "actual_recovery": actual_recovery,

        "allowed_action": allowed_action,

        "gateway_response": gateway_response,

        "verification_result": verification_result,

        "final_state": final_state,

        "escalation_required": escalation_required,

        "recovered_amount": round(
            recovered_amount,
            2
        )
    })


# ============================================================
# SAVE
# ============================================================

scenario_df = pd.DataFrame(scenarios)

scenario_df.to_csv(
    OUTPUT_FILE,
    index=False
)


# ============================================================
# REPORT
# ============================================================

print("\n" + "=" * 70)
print("RECOVERY SCENARIOS GENERATED")
print("=" * 70)

print(
    f"\nTotal scenarios: "
    f"{len(scenario_df):,}"
)

print("\nAllowed actions:")
print(
    scenario_df["allowed_action"]
    .value_counts()
    .to_string()
)

print("\nGateway responses:")
print(
    scenario_df["gateway_response"]
    .value_counts()
    .to_string()
)

print("\nVerification results:")
print(
    scenario_df["verification_result"]
    .value_counts()
    .to_string()
)

print("\nFinal states:")
print(
    scenario_df["final_state"]
    .value_counts()
    .to_string()
)

print(
    f"\nTotal revenue recovered: "
    f"₹{scenario_df['recovered_amount'].sum():,.2f}"
)

print(
    f"\nEscalation cases: "
    f"{scenario_df['escalation_required'].sum():,}"
)

print("\nOutput:")
print(OUTPUT_FILE)

print("\nFirst 10 scenarios:")
print(
    scenario_df.head(10).to_string(index=False)
)

print("\n" + "=" * 70)
print("DONE")
print("=" * 70)