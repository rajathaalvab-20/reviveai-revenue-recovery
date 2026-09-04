from __future__ import annotations

import csv
import json
import sys
from pathlib import Path


# ============================================================
# PROJECT PATH SETUP
# ============================================================

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"

IMPORT_PATHS = [
    ROOT,
    SRC,
    SRC / "actions",
    SRC / "diagnosis",
    SRC / "pipeline",
    SRC / "policy",
    SRC / "risk_model",
    SRC / "simulation",
    SRC / "verification",
]

for path in IMPORT_PATHS:
    path = str(path)

    if path not in sys.path:
        sys.path.insert(0, path)


# ============================================================
# IMPORTS
# ============================================================

from batch_simulator import BatchSimulator

# ============================================================
# CONFIGURATION
# ============================================================

DATASET_PATH = ROOT / "data" / "raw" / "payment_events.csv"

# Number of transactions to simulate.
# Start small so the complete pipeline can be verified safely.
BATCH_SIZE = 100


# ============================================================
# DATA LOADING
# ============================================================

def load_payments(
    csv_path: Path,
    limit: int | None = None
) -> list[dict]:

    if not csv_path.exists():
        raise FileNotFoundError(
            f"Payment dataset not found: {csv_path}"
        )

    payments = []

    with open(
        csv_path,
        "r",
        encoding="utf-8",
        newline=""
    ) as file:

        reader = csv.DictReader(file)

        if not reader.fieldnames:
            raise ValueError(
                "Payment CSV does not contain a header."
            )

        for row in reader:

            payment = dict(row)

            # ------------------------------------------------
            # Convert numeric fields
            # ------------------------------------------------

            numeric_fields = [
                "amount",
                "customer_age_days",
                "previous_transactions",
                "previous_success_rate",
                "attempt_count",
                "time_since_failure_min",
                "hour_of_day",
                "is_weekend",
            ]

            for field in numeric_fields:

                if field not in payment:
                    continue

                value = payment[field]

                if value == "":
                    continue

                try:

                    if field in {
                        "amount",
                        "previous_success_rate",
                    }:
                        payment[field] = float(value)

                    else:
                        payment[field] = int(float(value))

                except ValueError:
                    raise ValueError(
                        f"Invalid value for '{field}': "
                        f"{value!r}"
                    )

            payments.append(payment)

            if limit is not None and len(payments) >= limit:
                break

    if not payments:
        raise ValueError(
            "No payment records were loaded."
        )

    return payments


# ============================================================
# PRINT SUMMARY
# ============================================================

def print_summary(result: dict) -> None:

    summary = result.get("summary", {})

    print()
    print("=" * 70)
    print("SIMULATION SUMMARY")
    print("=" * 70)

    print(
        f"Total transactions      : "
        f"{summary.get('total_transactions', 0)}"
    )

    print(
        f"Recovered transactions  : "
        f"{summary.get('recovered_transactions', 0)}"
    )

    print(
        f"Blocked transactions    : "
        f"{summary.get('blocked_transactions', 0)}"
    )

    print(
        f"Not recovered           : "
        f"{summary.get('not_recovered_transactions', 0)}"
    )

    print(
        f"Failed transactions     : "
        f"{summary.get('failed_transactions', 0)}"
    )

    print(
        f"Revenue at risk         : "
        f"₹{summary.get('revenue_at_risk', 0.0):,.2f}"
    )

    print(
        f"Revenue recovered       : "
        f"₹{summary.get('revenue_recovered', 0.0):,.2f}"
    )

    print(
        f"Revenue not recovered   : "
        f"₹{summary.get('revenue_not_recovered', 0.0):,.2f}"
    )

    print(
        f"Revenue recovery rate   : "
        f"{summary.get('revenue_recovery_rate', 0.0) * 100:.2f}%"
    )

    print(
        f"Transaction recovery    : "
        f"{summary.get('transaction_recovery_rate', 0.0) * 100:.2f}%"
    )


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    print("=" * 70)
    print("REVIVEAI — REVENUE RECOVERY SIMULATION")
    print("=" * 70)

    print()
    print(f"Dataset : {DATASET_PATH}")
    print(f"Batch size : {BATCH_SIZE}")

    # --------------------------------------------------------
    # Load payments
    # --------------------------------------------------------

    print()
    print("[1] Loading payment events...")

    payments = load_payments(
        DATASET_PATH,
        limit=BATCH_SIZE
    )

    print(
        f"[OK] Loaded {len(payments)} payment transactions."
    )

    # --------------------------------------------------------
    # Initialize simulator
    # --------------------------------------------------------

    print()
    print("[2] Initializing batch simulator...")

    simulator = BatchSimulator()

    print("[OK] Batch simulator initialized.")

    # --------------------------------------------------------
    # Run pipeline
    # --------------------------------------------------------

    print()
    print("[3] Running transactions through ReviveAI...")
    print()

    result = simulator.run(payments)

    print("[OK] Batch simulation completed.")

    # --------------------------------------------------------
    # Print summary
    # --------------------------------------------------------

    print_summary(result)

    # --------------------------------------------------------
    # Save result using existing simulator implementation
    # --------------------------------------------------------

    print()
    print("[4] Saving simulation result...")

    output_path = simulator.save_result(result)

    print(f"[OK] Result saved to:")
    print(f"     {output_path}")

    # --------------------------------------------------------
    # Save a copy under project-level results directory
    # --------------------------------------------------------

    project_results = ROOT / "results" / "simulation"
    project_results.mkdir(
        parents=True,
        exist_ok=True
    )

    project_output = (
        project_results
        / Path(output_path).name
    )

    with open(
        project_output,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            result,
            file,
            indent=2,
            default=str
        )

    print()
    print("[OK] Project result copy saved to:")
    print(f"     {project_output}")

    # --------------------------------------------------------
    # Completion
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("SIMULATION FINISHED SUCCESSFULLY")
    print("=" * 70)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()