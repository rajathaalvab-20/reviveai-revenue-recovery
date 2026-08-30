"""
ReviveAI - CSV Batch Runner

Loads payment events from a CSV dataset and executes them
through the existing BatchSimulator.

Design goals:
- reuse tested BatchSimulator
- strict CSV validation
- controlled batch execution
- structured output
- reproducible testing
- no modification to the core pipeline
"""

import csv
import json
import os
from datetime import datetime, timezone

from batch_simulator import BatchSimulator


class CSVBatchRunner:
    """
    Loads payment transactions from CSV and executes them
    through the existing ReviveAI BatchSimulator.
    """

    REQUIRED_COLUMNS = {
        "transaction_id",
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
        "is_weekend",
    }

    INTEGER_FIELDS = {
        "customer_age_days",
        "previous_transactions",
        "attempt_count",
        "time_since_failure_min",
        "hour_of_day",
        "is_weekend",
    }

    FLOAT_FIELDS = {
        "amount",
        "previous_success_rate",
    }

    def __init__(
        self,
        csv_path,
        output_dir=None
    ):
        if not isinstance(csv_path, str):
            raise TypeError(
                "csv_path must be a string."
            )

        if not csv_path.strip():
            raise ValueError(
                "csv_path cannot be empty."
            )

        if not os.path.isfile(csv_path):
            raise FileNotFoundError(
                f"Dataset not found: {csv_path}"
            )

        self.csv_path = csv_path

        if output_dir is None:
            output_dir = os.path.join(
                os.path.dirname(__file__),
                "results"
            )

        self.output_dir = output_dir

        os.makedirs(
            self.output_dir,
            exist_ok=True
        )

    # ---------------------------------------------------------
    # VALUE CONVERSION
    # ---------------------------------------------------------

    @staticmethod
    def _convert_value(field, value):
        if value is None:
            raise ValueError(
                f"{field} cannot be None."
            )

        value = value.strip()

        if not value:
            raise ValueError(
                f"{field} cannot be empty."
            )

        if field in CSVBatchRunner.INTEGER_FIELDS:
            try:
                number = float(value)

                if not number.is_integer():
                    raise ValueError(
                        f"{field} must be an integer."
                    )

                return int(number)

            except ValueError as error:
                raise ValueError(
                    f"Invalid integer value for "
                    f"{field}: {value}"
                ) from error

        if field in CSVBatchRunner.FLOAT_FIELDS:
            try:
                return float(value)

            except ValueError as error:
                raise ValueError(
                    f"Invalid numeric value for "
                    f"{field}: {value}"
                ) from error

        return value

    # ---------------------------------------------------------
    # CSV LOADING
    # ---------------------------------------------------------

    def load_transactions(self, limit=None):
        """
        Load transactions from the CSV file.

        limit:
            Optional positive integer used for controlled
            test runs such as 10, 100, or 1000 transactions.
        """

        if limit is not None:

            if not isinstance(limit, int):
                raise TypeError(
                    "limit must be an integer."
                )

            if limit <= 0:
                raise ValueError(
                    "limit must be greater than zero."
                )

        transactions = []

        with open(
            self.csv_path,
            "r",
            encoding="utf-8",
            newline=""
        ) as file:

            reader = csv.DictReader(file)

            if reader.fieldnames is None:
                raise ValueError(
                    "CSV file does not contain a header."
                )

            csv_columns = set(
                reader.fieldnames
            )

            missing_columns = (
                self.REQUIRED_COLUMNS
                - csv_columns
            )

            if missing_columns:
                raise ValueError(
                    "Missing required CSV columns: "
                    + ", ".join(
                        sorted(missing_columns)
                    )
                )

            for row_number, row in enumerate(
                reader,
                start=2
            ):

                transaction = {}

                for field in self.REQUIRED_COLUMNS:

                    value = row.get(field)

                    try:
                        transaction[field] = (
                            self._convert_value(
                                field,
                                value
                            )
                        )

                    except Exception as error:

                        raise ValueError(
                            f"CSV row "
                            f"{row_number}: "
                            f"{error}"
                        ) from error

                transactions.append(
                    transaction
                )

                if (
                    limit is not None
                    and len(transactions) >= limit
                ):
                    break

        if not transactions:
            raise ValueError(
                "CSV dataset contains no transactions."
            )

        return transactions

    # ---------------------------------------------------------
    # EXECUTION
    # ---------------------------------------------------------

    def run(self, limit=None):
        """
        Load CSV transactions and execute them through
        the existing BatchSimulator.
        """

        started_at = datetime.now(
            timezone.utc
        ).isoformat()

        transactions = self.load_transactions(
            limit=limit
        )

        simulator = BatchSimulator()

        # IMPORTANT:
        # BatchSimulator API is run(payments)
        result = simulator.run(
            transactions
        )

        completed_at = datetime.now(
            timezone.utc
        ).isoformat()

        output = {
            "runner": "CSVBatchRunner",
            "runner_version": "V1",
            "dataset": os.path.abspath(
                self.csv_path
            ),
            "transaction_limit": limit,
            "transactions_loaded": len(
                transactions
            ),
            "started_at": started_at,
            "completed_at": completed_at,
            "simulation": result
        }

        # Use BatchSimulator's existing
        # production-tested result writer.
        simulation_result_file = (
            simulator.save_result(
                output
            )
        )

        output["output_file"] = (
            simulation_result_file
        )

        return output


# -------------------------------------------------------------
# COMMAND-LINE EXECUTION
# -------------------------------------------------------------

if __name__ == "__main__":

    DATASET = os.path.join(
        "data",
        "raw",
        "payment_events.csv"
    )

    runner = CSVBatchRunner(
        DATASET
    )

    # Controlled test:
    # process only 100 transactions first.
    result = runner.run(
        limit=100
    )

    print(
        json.dumps(
            result,
            indent=2
        )
    )
