"""
ReviveAI - Failure Injector

Provides deterministic failure scenarios for the payment simulation.

Supported outcomes:
    SUCCESS
    DECLINED
    TIMEOUT
    NETWORK_ERROR

The injector supports both:
1. Default outcome for all transactions
2. Transaction-specific outcome sequences

Example:
    injector = FailureInjector()

    injector.set_transaction_outcomes(
        "TXN001",
        ["TIMEOUT", "SUCCESS"]
    )

    injector.process_payment("TXN001", 5000)

    # Attempt 1 -> TIMEOUT
    # Attempt 2 -> SUCCESS
"""

from datetime import datetime, timezone


VALID_OUTCOMES = {
    "SUCCESS",
    "DECLINED",
    "TIMEOUT",
    "NETWORK_ERROR",
}


class FailureInjector:
    """
    Deterministic failure injection component.

    This component does not use randomness.
    The same configured transaction sequence
    produces the same result every time.
    """

    def __init__(self, default_outcome="SUCCESS"):
        self._validate_outcome(default_outcome)

        self.default_outcome = default_outcome

        # Transaction-specific configured outcomes
        self.transaction_outcomes = {}

        # Number of attempts made for each transaction
        self.attempt_counts = {}

    # ---------------------------------------------------------
    # VALIDATION
    # ---------------------------------------------------------

    @staticmethod
    def _validate_transaction_id(transaction_id):
        if not isinstance(transaction_id, str):
            raise TypeError("transaction_id must be a string.")

        if not transaction_id.strip():
            raise ValueError("transaction_id cannot be empty.")

    @staticmethod
    def _validate_amount(amount):
        if not isinstance(amount, (int, float)):
            raise TypeError("amount must be numeric.")

        if amount < 0:
            raise ValueError("amount cannot be negative.")

    @staticmethod
    def _validate_outcome(outcome):
        if not isinstance(outcome, str):
            raise TypeError("outcome must be a string.")

        if outcome not in VALID_OUTCOMES:
            raise ValueError(
                f"Invalid outcome: {outcome}. "
                f"Valid outcomes: {sorted(VALID_OUTCOMES)}"
            )

    # ---------------------------------------------------------
    # CONFIGURATION
    # ---------------------------------------------------------

    def set_default_outcome(self, outcome):
        """
        Set the outcome used when a transaction does not have
        a transaction-specific failure sequence.
        """

        self._validate_outcome(outcome)

        self.default_outcome = outcome

    def set_transaction_outcome(
        self,
        transaction_id,
        outcome
    ):
        """
        Configure one fixed outcome for a transaction.
        """

        self._validate_transaction_id(transaction_id)
        self._validate_outcome(outcome)

        self.transaction_outcomes[transaction_id] = [
            outcome
        ]

        self.attempt_counts[transaction_id] = 0

    def set_transaction_outcomes(
        self,
        transaction_id,
        outcomes
    ):
        """
        Configure a deterministic sequence of outcomes.

        Example:
            ["TIMEOUT", "NETWORK_ERROR", "SUCCESS"]
        """

        self._validate_transaction_id(transaction_id)

        if not isinstance(outcomes, list):
            raise TypeError("outcomes must be a list.")

        if not outcomes:
            raise ValueError("outcomes cannot be empty.")

        for outcome in outcomes:
            self._validate_outcome(outcome)

        self.transaction_outcomes[transaction_id] = list(
            outcomes
        )

        self.attempt_counts[transaction_id] = 0

    # ---------------------------------------------------------
    # PAYMENT PROCESSING
    # ---------------------------------------------------------

    def process_payment(
        self,
        transaction_id,
        amount
    ):
        """
        Process one simulated payment attempt.

        The configured transaction sequence determines
        the outcome for the current attempt.

        Once the configured sequence is exhausted,
        the final configured outcome is reused.
        """

        self._validate_transaction_id(transaction_id)
        self._validate_amount(amount)

        current_attempt = self.attempt_counts.get(
            transaction_id,
            0
        ) + 1

        self.attempt_counts[transaction_id] = current_attempt

        outcomes = self.transaction_outcomes.get(
            transaction_id
        )

        if outcomes is None:
            outcome = self.default_outcome
        else:
            index = current_attempt - 1

            if index < len(outcomes):
                outcome = outcomes[index]
            else:
                # After the configured sequence ends,
                # continue using its final outcome.
                outcome = outcomes[-1]

        successful = outcome == "SUCCESS"

        return {
            "transaction_id": transaction_id,
            "amount": float(amount),
            "attempt_count": current_attempt,
            "outcome": outcome,
            "successful": successful,
            "gateway_reference": (
                f"SIM-{transaction_id}-{current_attempt}"
            ),
            "timestamp": datetime.now(
                timezone.utc
            ).isoformat(),
        }

    # ---------------------------------------------------------
    # STATE / INSPECTION
    # ---------------------------------------------------------

    def get_attempt_count(self, transaction_id):
        """
        Return the number of attempts made for a transaction.
        """

        self._validate_transaction_id(transaction_id)

        return self.attempt_counts.get(
            transaction_id,
            0
        )

    def clear_transaction(self, transaction_id):
        """
        Remove configured outcome and attempt state
        for one transaction.
        """

        self._validate_transaction_id(transaction_id)

        self.transaction_outcomes.pop(
            transaction_id,
            None
        )

        self.attempt_counts.pop(
            transaction_id,
            None
        )

    def reset(self):
        """
        Reset the entire simulator state.
        """

        self.transaction_outcomes.clear()
        self.attempt_counts.clear()

