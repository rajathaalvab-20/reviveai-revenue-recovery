from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


# ============================================================
# PATH CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

RESULTS_DIR = (
    PROJECT_ROOT
    / "results"
    / "simulation"
)


# ============================================================
# CONSTANTS
# ============================================================

ESCALATION_ACTIONS = {
    "ESCALATE",
    "HUMAN_REVIEW",
}


# ============================================================
# HELPERS
# ============================================================

def safe_float(value: Any) -> float:
    """
    Safely convert a value to float.

    Invalid or missing values are treated as 0.0.
    """

    try:
        return float(value)

    except (
        TypeError,
        ValueError,
    ):
        return 0.0


def load_latest_simulation() -> dict[str, Any]:
    """
    Load the most recently generated batch simulation result.

    Simulation files are expected to follow:

        batch_simulation_*.json
    """

    if not RESULTS_DIR.exists():
        raise FileNotFoundError(
            f"Simulation results directory does not exist: "
            f"{RESULTS_DIR}"
        )

    files = sorted(
        RESULTS_DIR.glob(
            "batch_simulation_*.json"
        ),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )

    if not files:
        raise FileNotFoundError(
            f"No simulation result files found in: "
            f"{RESULTS_DIR}"
        )

    latest_file = files[0]

    print(
        "Loading simulation result:"
    )

    print(
        f"  {latest_file}"
    )

    with latest_file.open(
        "r",
        encoding="utf-8",
    ) as file:

        data = json.load(file)

    if not isinstance(
        data,
        dict,
    ):
        raise ValueError(
            "Simulation result must contain a JSON object."
        )

    return data


# ============================================================
# TRANSACTION AMOUNT EXTRACTION
# ============================================================

def extract_transaction_amount(
    transaction: dict[str, Any],
    pipeline: dict[str, Any],
) -> float:
    """
    Extract the transaction amount from the simulation result.

    The ReviveAI simulation stores the amount inside the
    pipeline action result in the current output format.

    Fallback locations are also supported so the evaluator
    remains robust if the result structure changes slightly.
    """

    # --------------------------------------------------------
    # 1. Direct transaction amount
    # --------------------------------------------------------

    if "amount" in transaction:
        return safe_float(
            transaction.get(
                "amount"
            )
        )

    # --------------------------------------------------------
    # 2. Pipeline-level amount
    # --------------------------------------------------------

    if "amount" in pipeline:
        return safe_float(
            pipeline.get(
                "amount"
            )
        )

    # --------------------------------------------------------
    # 3. Action result amount
    # --------------------------------------------------------

    action_result = pipeline.get(
        "action",
        {},
    )

    if isinstance(
        action_result,
        dict,
    ):

        if "amount" in action_result:

            return safe_float(
                action_result.get(
                    "amount"
                )
            )

    # --------------------------------------------------------
    # 4. Verification amount at risk
    # --------------------------------------------------------

    verification = pipeline.get(
        "verification",
        {},
    )

    if isinstance(
        verification,
        dict,
    ):

        if "amount_at_risk" in verification:

            return safe_float(
                verification.get(
                    "amount_at_risk"
                )
            )

    return 0.0


# ============================================================
# RECOVERED REVENUE EXTRACTION
# ============================================================

def extract_actual_recovered_amount(
    transaction: dict[str, Any],
    pipeline: dict[str, Any],
) -> float:
    """
    Extract actual recovered revenue from ground truth.
    """

    verification = pipeline.get(
        "verification",
        {},
    )

    if not isinstance(
        verification,
        dict,
    ):
        return 0.0

    return safe_float(
        verification.get(
            "actual_recovered_amount",
            0.0,
        )
    )


def extract_automated_recovered_amount(
    transaction: dict[str, Any],
) -> float:
    """
    Extract revenue recovered automatically by ReviveAI.
    """

    return safe_float(
        transaction.get(
            "revenue_recovered",
            0.0,
        )
    )


# ============================================================
# EVALUATION
# ============================================================

def evaluate_simulation(
    data: dict[str, Any],
) -> dict[str, Any]:
    """
    Evaluate ReviveAI simulation performance.

    The evaluator distinguishes between:

    1. Automatic recovery
       Recovery performed directly by ReviveAI.

    2. Recovery after escalation
       Recovery that occurred according to ground truth
       after the system escalated the transaction.

    3. Eventual recovery
       Automatic recovery + recovery after escalation.

    Safety metric:

        unsafe automatic recovery

    means ReviveAI reported an automatic recovery even though
    ground truth says the transaction was not actually recovered.
    """

    transactions = data.get(
        "transactions",
        [],
    )

    if not isinstance(
        transactions,
        list,
    ):
        raise ValueError(
            "Simulation result contains invalid transactions."
        )

    # ========================================================
    # INITIALIZE METRICS
    # ========================================================

    total_transactions = len(
        transactions
    )

    total_revenue_at_risk = 0.0

    actual_recoverable_transactions = []

    automated_recoveries = []

    escalation_recoveries = []

    unsafe_automatic_recoveries = []

    # ========================================================
    # PROCESS TRANSACTIONS
    # ========================================================

    for transaction in transactions:

        if not isinstance(
            transaction,
            dict,
        ):
            continue

        pipeline = transaction.get(
            "pipeline_result",
            {},
        )

        if not isinstance(
            pipeline,
            dict,
        ):
            continue

        # ----------------------------------------------------
        # Extract action
        # ----------------------------------------------------

        action_result = pipeline.get(
            "action",
            {},
        )

        if not isinstance(
            action_result,
            dict,
        ):
            action_result = {}

        action = str(
            action_result.get(
                "action",
                "",
            )
        ).strip()

        executed = bool(
            action_result.get(
                "executed",
                False,
            )
        )

        # ----------------------------------------------------
        # Extract verification
        # ----------------------------------------------------

        verification = pipeline.get(
            "verification",
            {},
        )

        if not isinstance(
            verification,
            dict,
        ):
            verification = {}

        # ----------------------------------------------------
        # Extract transaction amount
        # ----------------------------------------------------

        amount = extract_transaction_amount(
            transaction,
            pipeline,
        )

        total_revenue_at_risk += amount

        # ----------------------------------------------------
        # Ground truth
        # ----------------------------------------------------

        actual_recovery = bool(
            verification.get(
                "actual_recovery",
                False,
            )
        )

        actual_recovered_amount = (
            extract_actual_recovered_amount(
                transaction,
                pipeline,
            )
        )

        # ----------------------------------------------------
        # ReviveAI automatic recovery result
        # ----------------------------------------------------

        automated_recovery = bool(
            verification.get(
                "recovered",
                False,
            )
        )

        # ====================================================
        # GROUND-TRUTH RECOVERABLE TRANSACTION
        # ====================================================

        if actual_recovery:

            actual_recoverable_transactions.append(
                transaction
            )

            # ------------------------------------------------
            # Automatic recovery
            # ------------------------------------------------

            if automated_recovery:

                automated_recoveries.append(
                    transaction
                )

            # ------------------------------------------------
            # Recovery after escalation
            # ------------------------------------------------

            elif action in ESCALATION_ACTIONS:

                escalation_recoveries.append(
                    transaction
                )

        # ====================================================
        # SAFETY CHECK
        # ====================================================

        # An unsafe automatic recovery occurs when:
        #
        #   ReviveAI says recovered
        #              AND
        #   ground truth says NOT recovered
        #
        if (
            executed
            and automated_recovery
            and not actual_recovery
        ):

            unsafe_automatic_recoveries.append(
                transaction
            )

    # ========================================================
    # TRANSACTION COUNTS
    # ========================================================

    recoverable_count = len(
        actual_recoverable_transactions
    )

    automated_count = len(
        automated_recoveries
    )

    escalation_count = len(
        escalation_recoveries
    )

    # ========================================================
    # RECOVERABLE REVENUE
    # ========================================================

    actual_recoverable_revenue = sum(
        extract_actual_recovered_amount(
            transaction,
            transaction.get(
                "pipeline_result",
                {},
            ),
        )
        for transaction
        in actual_recoverable_transactions
    )

    # ========================================================
    # AUTOMATED RECOVERED REVENUE
    # ========================================================

    automated_recovered_revenue = sum(
        extract_automated_recovered_amount(
            transaction
        )
        for transaction
        in automated_recoveries
    )

    # ========================================================
    # ESCALATION RECOVERED REVENUE
    # ========================================================

    escalation_recovered_revenue = sum(
        extract_actual_recovered_amount(
            transaction,
            transaction.get(
                "pipeline_result",
                {},
            ),
        )
        for transaction
        in escalation_recoveries
    )

    # ========================================================
    # EVENTUAL RECOVERY
    # ========================================================

    eventual_recovered_revenue = (
        automated_recovered_revenue
        + escalation_recovered_revenue
    )

    eventual_recovered_transactions = (
        automated_count
        + escalation_count
    )

    # ========================================================
    # AUTOMATIC TRANSACTION CAPTURE
    # ========================================================

    if recoverable_count > 0:

        automatic_transaction_capture = (
            automated_count
            / recoverable_count
            * 100
        )

    else:

        automatic_transaction_capture = 0.0

    # ========================================================
    # AUTOMATIC REVENUE CAPTURE
    # ========================================================

    if actual_recoverable_revenue > 0:

        automatic_revenue_capture = (
            automated_recovered_revenue
            / actual_recoverable_revenue
            * 100
        )

    else:

        automatic_revenue_capture = 0.0

    # ========================================================
    # EVENTUAL TRANSACTION RECOVERY
    # ========================================================

    if recoverable_count > 0:

        eventual_transaction_recovery = (
            eventual_recovered_transactions
            / recoverable_count
            * 100
        )

    else:

        eventual_transaction_recovery = 0.0

    # ========================================================
    # EVENTUAL REVENUE RECOVERY
    # ========================================================

    if actual_recoverable_revenue > 0:

        eventual_revenue_recovery = (
            eventual_recovered_revenue
            / actual_recoverable_revenue
            * 100
        )

    else:

        eventual_revenue_recovery = 0.0

    # ========================================================
    # RETURN METRICS
    # ========================================================

    return {

        "total_transactions":
            total_transactions,

        "total_revenue_at_risk":
            round(
                total_revenue_at_risk,
                2,
            ),

        "actual_recoverable_transactions":
            recoverable_count,

        "automated_recoveries":
            automated_count,

        "escalation_recoveries":
            escalation_count,

        "actual_recoverable_revenue":
            round(
                actual_recoverable_revenue,
                2,
            ),

        "automated_recovered_revenue":
            round(
                automated_recovered_revenue,
                2,
            ),

        "escalation_recovered_revenue":
            round(
                escalation_recovered_revenue,
                2,
            ),

        "eventual_recovered_revenue":
            round(
                eventual_recovered_revenue,
                2,
            ),

        "automatic_transaction_capture_percent":
            round(
                automatic_transaction_capture,
                2,
            ),

        "automatic_revenue_capture_percent":
            round(
                automatic_revenue_capture,
                2,
            ),

        "eventual_transaction_recovery_percent":
            round(
                eventual_transaction_recovery,
                2,
            ),

        "eventual_revenue_recovery_percent":
            round(
                eventual_revenue_recovery,
                2,
            ),

        "unsafe_automatic_recoveries":
            len(
                unsafe_automatic_recoveries
            ),
    }


# ============================================================
# REPORT
# ============================================================

def print_report(
    metrics: dict[str, Any],
) -> None:
    """
    Print a human-readable ReviveAI evaluation report.
    """

    print()

    print(
        "=" * 70
    )

    print(
        "REVIVEAI — RECOVERY EVALUATION REPORT"
    )

    print(
        "=" * 70
    )

    # ========================================================
    # TRANSACTION SUMMARY
    # ========================================================

    print()

    print(
        "TRANSACTION SUMMARY"
    )

    print(
        "-" * 70
    )

    print(
        f"Total transactions           : "
        f"{metrics['total_transactions']}"
    )

    print(
        f"Total revenue at risk        : "
        f"₹{metrics['total_revenue_at_risk']:,.2f}"
    )

    # ========================================================
    # RECOVERY PERFORMANCE
    # ========================================================

    print()

    print(
        "RECOVERY PERFORMANCE"
    )

    print(
        "-" * 70
    )

    print(
        f"Actual recoverable transactions : "
        f"{metrics['actual_recoverable_transactions']}"
    )

    print(
        f"Automatically recovered         : "
        f"{metrics['automated_recoveries']}"
    )

    print(
        f"Recovered after escalation      : "
        f"{metrics['escalation_recoveries']}"
    )

    print()

    print(
        f"Automatic transaction capture   : "
        f"{metrics['automatic_transaction_capture_percent']:.2f}%"
    )

    print()

    print(
        f"Actual recoverable revenue      : "
        f"₹{metrics['actual_recoverable_revenue']:,.2f}"
    )

    print(
        f"Automatically recovered revenue : "
        f"₹{metrics['automated_recovered_revenue']:,.2f}"
    )

    print(
        f"Escalation recovered revenue    : "
        f"₹{metrics['escalation_recovered_revenue']:,.2f}"
    )

    print(
        f"Automatic revenue capture       : "
        f"{metrics['automatic_revenue_capture_percent']:.2f}%"
    )

    # ========================================================
    # EVENTUAL RECOVERY
    # ========================================================

    print()

    print(
        "EVENTUAL RECOVERY"
    )

    print(
        "-" * 70
    )

    print(
        f"Eventual transaction recovery   : "
        f"{metrics['eventual_transaction_recovery_percent']:.2f}%"
    )

    print(
        f"Eventual revenue recovery       : "
        f"{metrics['eventual_revenue_recovery_percent']:.2f}%"
    )

    print(
        f"Eventual recovered revenue      : "
        f"₹{metrics['eventual_recovered_revenue']:,.2f}"
    )

    # ========================================================
    # SAFETY
    # ========================================================

    print()

    print(
        "SAFETY"
    )

    print(
        "-" * 70
    )

    print(
        f"Unsafe automatic recoveries     : "
        f"{metrics['unsafe_automatic_recoveries']}"
    )

    print()

    print(
        "=" * 70
    )


# ============================================================
# MAIN
# ============================================================

def main() -> int:
    """
    Main evaluation entry point.
    """

    try:

        data = load_latest_simulation()

        metrics = evaluate_simulation(
            data
        )

        print_report(
            metrics
        )

        return 0

    except Exception as error:

        print(
            f"[ERROR] Evaluation failed: "
            f"{type(error).__name__}: {error}",
            file=sys.stderr,
        )

        return 1


# ============================================================
# SCRIPT ENTRY POINT
# ============================================================

if __name__ == "__main__":

    raise SystemExit(
        main()
    )
