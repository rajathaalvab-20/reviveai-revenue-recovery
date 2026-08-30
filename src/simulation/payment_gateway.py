from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
import uuid


@dataclass(frozen=True)
class GatewayResponse:
    transaction_id: str
    success: bool
    status: str
    message: str
    gateway_reference: Optional[str]
    timestamp: str


class PaymentGatewaySimulator:
    """
    Deterministic payment-gateway simulator.

    This component does NOT make real payments.
    It provides a controlled environment for testing
    ReviveAI recovery actions.
    """

    SUPPORTED_OUTCOMES = {
        "SUCCESS",
        "DECLINED",
        "TIMEOUT",
        "NETWORK_ERROR",
    }

    def __init__(self, default_outcome: str = "SUCCESS"):
        self._validate_outcome(default_outcome)

        self.default_outcome = default_outcome

        # Transaction-level outcomes allow deterministic testing.
        self._transaction_outcomes: dict[str, str] = {}

        # Track every gateway attempt.
        self._attempts: dict[str, int] = {}

    # ---------------------------------------------------------
    # VALIDATION
    # ---------------------------------------------------------

    @classmethod
    def _validate_transaction_id(cls, transaction_id: str) -> None:
        if not isinstance(transaction_id, str):
            raise TypeError("transaction_id must be a string.")

        if not transaction_id.strip():
            raise ValueError("transaction_id cannot be empty.")

    @classmethod
    def _validate_outcome(cls, outcome: str) -> None:
        if not isinstance(outcome, str):
            raise TypeError("outcome must be a string.")

        outcome = outcome.upper()

        if outcome not in cls.SUPPORTED_OUTCOMES:
            raise ValueError(
                f"Unsupported gateway outcome: {outcome}"
            )

    # ---------------------------------------------------------
    # CONFIGURATION
    # ---------------------------------------------------------

    def set_transaction_outcome(
        self,
        transaction_id: str,
        outcome: str,
    ) -> None:
        """
        Configure a deterministic outcome for a transaction.
        """

        self._validate_transaction_id(transaction_id)
        self._validate_outcome(outcome)

        self._transaction_outcomes[transaction_id] = outcome.upper()

    def clear_transaction_outcome(
        self,
        transaction_id: str,
    ) -> None:
        """
        Remove a transaction-specific outcome.
        """

        self._validate_transaction_id(transaction_id)

        self._transaction_outcomes.pop(
            transaction_id,
            None,
        )

    # ---------------------------------------------------------
    # PAYMENT ATTEMPT
    # ---------------------------------------------------------

    def charge(
        self,
        transaction_id: str,
        amount: float,
    ) -> GatewayResponse:
        """
        Simulate a payment attempt.

        No real financial transaction is performed.
        """

        self._validate_transaction_id(transaction_id)

        if not isinstance(amount, (int, float)):
            raise TypeError("amount must be numeric.")

        if amount < 0:
            raise ValueError("amount cannot be negative.")

        # Track attempts.
        self._attempts[transaction_id] = (
            self._attempts.get(transaction_id, 0) + 1
        )

        outcome = self._transaction_outcomes.get(
            transaction_id,
            self.default_outcome,
        )

        timestamp = datetime.now(
            timezone.utc
        ).isoformat()

        if outcome == "SUCCESS":
            return GatewayResponse(
                transaction_id=transaction_id,
                success=True,
                status="succeeded",
                message="Payment successfully processed.",
                gateway_reference=self._generate_reference(),
                timestamp=timestamp,
            )

        if outcome == "DECLINED":
            return GatewayResponse(
                transaction_id=transaction_id,
                success=False,
                status="declined",
                message="Payment was declined by the simulated gateway.",
                gateway_reference=None,
                timestamp=timestamp,
            )

        if outcome == "TIMEOUT":
            return GatewayResponse(
                transaction_id=transaction_id,
                success=False,
                status="timeout",
                message="Gateway request timed out.",
                gateway_reference=None,
                timestamp=timestamp,
            )

        if outcome == "NETWORK_ERROR":
            return GatewayResponse(
                transaction_id=transaction_id,
                success=False,
                status="network_error",
                message="Network communication failed.",
                gateway_reference=None,
                timestamp=timestamp,
            )

        # Defensive guard. This should be unreachable because
        # outcomes are validated before reaching this point.
        raise RuntimeError(
            f"Unhandled gateway outcome: {outcome}"
        )

    # ---------------------------------------------------------
    # INSPECTION
    # ---------------------------------------------------------

    def get_attempt_count(
        self,
        transaction_id: str,
    ) -> int:
        """
        Return the number of simulated gateway attempts.
        """

        self._validate_transaction_id(transaction_id)

        return self._attempts.get(
            transaction_id,
            0,
        )

    # ---------------------------------------------------------
    # INTERNAL
    # ---------------------------------------------------------

    @staticmethod
    def _generate_reference() -> str:
        return f"GW-{uuid.uuid4().hex.upper()}"