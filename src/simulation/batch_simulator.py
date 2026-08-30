"""
ReviveAI - Batch Simulation Engine

Runs multiple payment transactions through the ReviveAI
pipeline and produces aggregate revenue-recovery metrics.

Design goals:
- deterministic execution
- transaction isolation
- failure-safe processing
- measurable revenue recovery
- structured batch results
- no silent transaction failures
"""

import json
import os
from datetime import datetime, timezone

from pipeline.orchestrator import run_pipeline


SIMULATION_RESULT_DIR = os.path.join(
    os.path.dirname(__file__),
    "results"
)

os.makedirs(
    SIMULATION_RESULT_DIR,
    exist_ok=True
)


class BatchSimulator:
    """
    Executes a collection of payment transactions through
    the ReviveAI pipeline.
    """

    def __init__(self):
        self.results = []

    # ---------------------------------------------------------
    # INPUT VALIDATION
    # ---------------------------------------------------------

    @staticmethod
    def _validate_payments(payments):
        if not isinstance(payments, list):
            raise TypeError(
                "payments must be a list."
            )

        if not payments:
            raise ValueError(
                "payments cannot be empty."
            )

        for payment in payments:
            if not isinstance(payment, dict):
                raise TypeError(
                    "Every payment must be a dictionary."
                )

            if not payment.get("transaction_id"):
                raise ValueError(
                    "Every payment requires transaction_id."
                )

    # ---------------------------------------------------------
    # SINGLE TRANSACTION
    # ---------------------------------------------------------

    @staticmethod
    def _extract_revenue(result):
        """
        Extract recovered revenue safely from the pipeline result.
        """

        verification = result.get(
            "verification",
            {}
        )

        value = verification.get(
            "revenue_recovered",
            0
        )

        if value is None:
            return 0.0

        return float(value)

    # ---------------------------------------------------------
    # BATCH EXECUTION
    # ---------------------------------------------------------

    def run(self, payments):
        """
        Run all payments through the ReviveAI pipeline.

        One transaction failing must not terminate the
        complete batch.
        """

        self._validate_payments(payments)

        started_at = datetime.now(
            timezone.utc
        ).isoformat()

        self.results = []

        for payment in payments:

            transaction_id = str(
                payment["transaction_id"]
            )

            try:
                result = run_pipeline(
                    payment
                )

                transaction_result = {
                    "transaction_id": transaction_id,
                    "status": result.get(
                        "status",
                        "unknown"
                    ),
                    "pipeline_result": result,
                    "revenue_at_risk": float(
                        payment.get(
                            "amount",
                            0
                        )
                    ),
                    "revenue_recovered": (
                        self._extract_revenue(
                            result
                        )
                    ),
                    "error": None
                }

            except Exception as error:

                transaction_result = {
                    "transaction_id": transaction_id,
                    "status": "failed",
                    "pipeline_result": None,
                    "revenue_at_risk": float(
                        payment.get(
                            "amount",
                            0
                        )
                    ),
                    "revenue_recovered": 0.0,
                    "error": {
                        "error_type": type(
                            error
                        ).__name__,
                        "error": str(error)
                    }
                }

            self.results.append(
                transaction_result
            )

        completed_at = datetime.now(
            timezone.utc
        ).isoformat()

        summary = self._build_summary(
            started_at,
            completed_at
        )

        output = {
            "status": "completed",
            "started_at": started_at,
            "completed_at": completed_at,
            "summary": summary,
            "transactions": self.results
        }

        return output

    # ---------------------------------------------------------
    # SUMMARY METRICS
    # ---------------------------------------------------------

    def _build_summary(
        self,
        started_at,
        completed_at
    ):
        total_transactions = len(
            self.results
        )

        successful_transactions = sum(
            1
            for result in self.results
            if result["status"] == "recovered"
        )

        blocked_transactions = sum(
            1
            for result in self.results
            if result["status"] == "blocked"
        )

        failed_transactions = sum(
            1
            for result in self.results
            if result["status"] == "failed"
        )

        not_recovered_transactions = sum(
            1
            for result in self.results
            if result["status"] == "not_recovered"
        )

        revenue_at_risk = sum(
            result["revenue_at_risk"]
            for result in self.results
        )

        revenue_recovered = sum(
            result["revenue_recovered"]
            for result in self.results
        )

        if revenue_at_risk > 0:
            recovery_rate = (
                revenue_recovered
                / revenue_at_risk
            )
        else:
            recovery_rate = 0.0

        if total_transactions > 0:
            transaction_recovery_rate = (
                successful_transactions
                / total_transactions
            )
        else:
            transaction_recovery_rate = 0.0

        return {
            "total_transactions": total_transactions,
            "recovered_transactions": (
                successful_transactions
            ),
            "blocked_transactions": (
                blocked_transactions
            ),
            "not_recovered_transactions": (
                not_recovered_transactions
            ),
            "failed_transactions": (
                failed_transactions
            ),
            "revenue_at_risk": revenue_at_risk,
            "revenue_recovered": revenue_recovered,
            "revenue_not_recovered": max(
                revenue_at_risk
                - revenue_recovered,
                0.0
            ),
            "revenue_recovery_rate": (
                recovery_rate
            ),
            "transaction_recovery_rate": (
                transaction_recovery_rate
            ),
            "started_at": started_at,
            "completed_at": completed_at
        }

    # ---------------------------------------------------------
    # SAVE RESULTS
    # ---------------------------------------------------------

    @staticmethod
    def save_result(result):
        """
        Save the complete batch result as JSON.
        """

        timestamp = datetime.now(
            timezone.utc
        ).strftime(
            "%Y%m%d_%H%M%S_%f"
        )

        filename = (
            f"batch_simulation_{timestamp}.json"
        )

        path = os.path.join(
            SIMULATION_RESULT_DIR,
            filename
        )

        with open(
            path,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                result,
                file,
                indent=2
            )

        return path

