from dataclasses import dataclass


@dataclass(frozen=True)
class PaymentResult:
    transaction_id: str
    status: str


class PaymentProviderNotConfigured(RuntimeError):
    pass


class PaymentProvider:
    """Provider boundary. Real implementation must use PayPal Sandbox APIs.

    This default deliberately fails closed. It must never fabricate a transaction ID
    or report success before a provider-verified response is received.
    """

    def execute_payout(self, *, recipient_email: str, amount_cents: int, currency: str, idempotency_key: str) -> PaymentResult:
        raise PaymentProviderNotConfigured("PayPal Sandbox payout adapter is not configured yet")
