"""
ReviveAI - Batch Analytics Engine

Analyzes completed batch simulation results and produces
financial, operational, action-level, and failure-level
recovery metrics.

Design goals:
- deterministic calculations
- no modification of source results
- defensive validation
- zero-division protection
- structured evaluation output
- explainable metrics
"""

import json
import os
from collections import defaultdict
from datetime import datetime, timezone


ANALYTICS_RESULT_DIR = os.path.join(
    os.path.dirname(__file__),
    "results"
)

os.makedirs(
    ANALYTICS_RESULT_DIR,
    exist_ok=True
)


class BatchAnalytics:
    """
    Calculates evaluation metrics from a completed
    ReviveAI batch simulation.
    """

    REQUIRED_TOP_LEVEL_FIELDS = {
        "status",
        "transactions"
    }

    # ---------------------------------------------------------
    # VALIDATION
    # ---------------------------------------------------------

    @staticmethod
    def _validate_batch_result(batch_result):
        if not isinstance(batch_result, dict):
            raise TypeError(
                "batch_result must be a dictionary."
            )

        missing = (
            BatchAnalytics.REQUIRED_TOP_LEVEL_FIELDS
            - set(batch_result.keys())
        )

        if missing:
            raise ValueError(
                f"Missing required batch fields: {sorted(missing)}"
            )

        transactions = batch_result["transactions"]

        if not isinstance(transactions, list):
            raise TypeError(
                "transactions must be a list."
            )

        for transaction in transactions:
            if not isinstance(transaction, dict):
                raise TypeError(
                    "Every transaction must be a dictionary."
                )

            if not transaction.get("transaction_id"):
                raise ValueError(
                    "Every transaction requires transaction_id."
                )

            amount = transaction.get(
                "revenue_at_risk",
                0
            )

            recovered = transaction.get(
                "revenue_recovered",
                0
            )

            if not isinstance(
                amount,
                (int, float)
            ):
                raise TypeError(
                    "revenue_at_risk must be numeric."
                )

            if not isinstance(
                recovered,
                (int, float)
            ):
                raise TypeError(
                    "revenue_recovered must be numeric."
                )

            if amount < 0:
                raise ValueError(
                    "revenue_at_risk cannot be negative."
                )

            if recovered < 0:
                raise ValueError(
                    "revenue_recovered cannot be negative."
                )

            if recovered > amount:
                raise ValueError(
                    "revenue_recovered cannot exceed revenue_at_risk."
                )

    # ---------------------------------------------------------
    # SAFE RATE
    # ---------------------------------------------------------

    @staticmethod
    def _rate(numerator, denominator):
        if denominator <= 0:
            return 0.0

        return numerator / denominator

    # ---------------------------------------------------------
    # MAIN ANALYSIS
    # ---------------------------------------------------------

    def analyze(self, batch_result):
        """
        Analyze a completed batch result.
        """

        self._validate_batch_result(
            batch_result
        )

        transactions = batch_result["transactions"]

        analyzed_at = datetime.now(
            timezone.utc
        ).isoformat()

        total_transactions = len(
            transactions
        )

        revenue_at_risk = sum(
            float(
                transaction.get(
                    "revenue_at_risk",
                    0
                )
            )
            for transaction in transactions
        )

        revenue_recovered = sum(
            float(
                transaction.get(
                    "revenue_recovered",
                    0
                )
            )
            for transaction in transactions
        )

        revenue_not_recovered = max(
            revenue_at_risk
            - revenue_recovered,
            0.0
        )

        recovered_transactions = sum(
            1
            for transaction in transactions
            if transaction.get("status")
            == "recovered"
        )

        blocked_transactions = sum(
            1
            for transaction in transactions
            if transaction.get("status")
            == "blocked"
        )

        not_recovered_transactions = sum(
            1
            for transaction in transactions
            if transaction.get("status")
            == "not_recovered"
        )

        failed_transactions = sum(
            1
            for transaction in transactions
            if transaction.get("status")
            == "failed"
        )

        recovery_rate = self._rate(
            revenue_recovered,
            revenue_at_risk
        )

        transaction_recovery_rate = self._rate(
            recovered_transactions,
            total_transactions
        )

        return {
            "analytics_version": "V1",

            "status": "success",

            "analyzed_at": analyzed_at,

            "summary": {
                "total_transactions": total_transactions,

                "recovered_transactions":
                    recovered_transactions,

                "blocked_transactions":
                    blocked_transactions,

                "not_recovered_transactions":
                    not_recovered_transactions,

                "failed_transactions":
                    failed_transactions,

                "revenue_at_risk":
                    round(revenue_at_risk, 2),

                "revenue_recovered":
                    round(revenue_recovered, 2),

                "revenue_not_recovered":
                    round(revenue_not_recovered, 2),

                "revenue_recovery_rate":
                    round(recovery_rate, 6),

                "transaction_recovery_rate":
                    round(
                        transaction_recovery_rate,
                        6
                    )
            },

            "action_analysis":
                self._analyze_actions(
                    transactions
                ),

            "failure_analysis":
                self._analyze_failures(
                    transactions
                ),

            "status_analysis":
                self._analyze_statuses(
                    transactions
                )
        }

    # ---------------------------------------------------------
    # ACTION ANALYSIS
    # ---------------------------------------------------------

    def _analyze_actions(self, transactions):

        groups = defaultdict(
            lambda: {
                "transactions": 0,
                "recovered_transactions": 0,
                "revenue_at_risk": 0.0,
                "revenue_recovered": 0.0
            }
        )

        for transaction in transactions:

            pipeline = transaction.get(
                "pipeline_result"
            ) or {}

            action_data = pipeline.get(
                "action"
            ) or {}

            action = action_data.get(
                "action",
                "UNKNOWN"
            )

            group = groups[action]

            group["transactions"] += 1

            if transaction.get(
                "status"
            ) == "recovered":
                group[
                    "recovered_transactions"
                ] += 1

            group["revenue_at_risk"] += float(
                transaction.get(
                    "revenue_at_risk",
                    0
                )
            )

            group["revenue_recovered"] += float(
                transaction.get(
                    "revenue_recovered",
                    0
                )
            )

        result = {}

        for action, data in groups.items():

            result[action] = {
                "transactions":
                    data["transactions"],

                "recovered_transactions":
                    data[
                        "recovered_transactions"
                    ],

                "revenue_at_risk":
                    round(
                        data["revenue_at_risk"],
                        2
                    ),

                "revenue_recovered":
                    round(
                        data["revenue_recovered"],
                        2
                    ),

                "recovery_rate":
                    round(
                        self._rate(
                            data[
                                "revenue_recovered"
                            ],
                            data[
                                "revenue_at_risk"
                            ]
                        ),
                        6
                    ),

                "transaction_recovery_rate":
                    round(
                        self._rate(
                            data[
                                "recovered_transactions"
                            ],
                            data[
                                "transactions"
                            ]
                        ),
                        6
                    )
            }

        return result

    # ---------------------------------------------------------
    # FAILURE ANALYSIS
    # ---------------------------------------------------------

    def _analyze_failures(self, transactions):

        groups = defaultdict(
            lambda: {
                "transactions": 0,
                "recovered_transactions": 0,
                "revenue_at_risk": 0.0,
                "revenue_recovered": 0.0
            }
        )

        for transaction in transactions:

            pipeline = transaction.get(
                "pipeline_result"
            ) or {}

            diagnosis = pipeline.get(
                "diagnosis"
            ) or {}

            failure_code = diagnosis.get(
                "failure_code",
                "UNKNOWN"
            )

            failure_type = diagnosis.get(
                "failure_type",
                "UNKNOWN"
            )

            key = (
                f"{failure_type}:"
                f"{failure_code}"
            )

            group = groups[key]

            group["transactions"] += 1

            if transaction.get(
                "status"
            ) == "recovered":
                group[
                    "recovered_transactions"
                ] += 1

            group["revenue_at_risk"] += float(
                transaction.get(
                    "revenue_at_risk",
                    0
                )
            )

            group["revenue_recovered"] += float(
                transaction.get(
                    "revenue_recovered",
                    0
                )
            )

        result = {}

        for failure, data in groups.items():

            result[failure] = {
                "transactions":
                    data["transactions"],

                "recovered_transactions":
                    data[
                        "recovered_transactions"
                    ],

                "revenue_at_risk":
                    round(
                        data["revenue_at_risk"],
                        2
                    ),

                "revenue_recovered":
                    round(
                        data["revenue_recovered"],
                        2
                    ),

                "recovery_rate":
                    round(
                        self._rate(
                            data[
                                "revenue_recovered"
                            ],
                            data[
                                "revenue_at_risk"
                            ]
                        ),
                        6
                    ),

                "transaction_recovery_rate":
                    round(
                        self._rate(
                            data[
                                "recovered_transactions"
                            ],
                            data[
                                "transactions"
                            ]
                        ),
                        6
                    )
            }

        return result

    # ---------------------------------------------------------
    # STATUS ANALYSIS
    # ---------------------------------------------------------

    def _analyze_statuses(self, transactions):

        result = defaultdict(int)

        for transaction in transactions:

            status = transaction.get(
                "status",
                "unknown"
            )

            result[status] += 1

        return dict(result)

    # ---------------------------------------------------------
    # FILE ANALYSIS
    # ---------------------------------------------------------

    def analyze_file(self, input_file):
        """
        Load a batch result JSON file and analyze it.
        """

        if not os.path.isfile(input_file):
            raise FileNotFoundError(
                f"Batch result file not found: {input_file}"
            )

        with open(
            input_file,
            "r",
            encoding="utf-8"
        ) as file:

            batch_result = json.load(
                file
            )

        return self.analyze(
            batch_result
        )

    # ---------------------------------------------------------
    # SAVE
    # ---------------------------------------------------------

    @staticmethod
    def save_result(result):

        timestamp = datetime.now(
            timezone.utc
        ).strftime(
            "%Y%m%d_%H%M%S_%f"
        )

        filename = (
            f"batch_analytics_{timestamp}.json"
        )

        path = os.path.join(
            ANALYTICS_RESULT_DIR,
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