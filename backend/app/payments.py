from dataclasses import dataclass
from decimal import Decimal
import httpx

from backend.app.config import settings


@dataclass(frozen=True)
class PaymentResult:
    transaction_id: str
    status: str


class PaymentProviderNotConfigured(RuntimeError):
    pass


class PaymentProviderError(RuntimeError):
    """Provider did not yield a verified terminal success."""


class PayPalSandboxProvider:
    """Single-recipient PayPal Payouts adapter. Sandbox only.

    It never treats an acknowledged/pending batch as settled. If a response is
    ambiguous, the caller must reconcile using the stable sender_batch_id before
    attempting another payout.
    """

    def __init__(self, *, client: httpx.Client | None = None):
        self._client = client or httpx.Client(timeout=httpx.Timeout(15.0, connect=5.0))
        self._base_url = "https://api-m.sandbox.paypal.com"

    def _credentials(self) -> tuple[str, str]:
        client_id = settings.paypal_client_id.strip()
        client_secret = settings.paypal_client_secret.strip()
        if settings.paypal_mode.lower() != "sandbox" or not client_id or not client_secret:
            raise PaymentProviderNotConfigured("PayPal Sandbox credentials are missing or mode is not sandbox")
        return client_id, client_secret

    def _access_token(self) -> str:
        client_id, client_secret = self._credentials()
        response = self._client.post(
            f"{self._base_url}/v1/oauth2/token",
            auth=(client_id, client_secret),
            headers={"Accept": "application/json", "Accept-Language": "en_US"},
            data={"grant_type": "client_credentials"},
        )
        response.raise_for_status()
        token = response.json().get("access_token")
        if not isinstance(token, str) or not token:
            raise PaymentProviderError("PayPal OAuth response did not contain an access token")
        return token

    def execute_payout(self, *, recipient_email: str, amount_cents: int, currency: str, idempotency_key: str) -> PaymentResult:
        token = self._access_token()
        amount = f"{Decimal(amount_cents) / Decimal(100):.2f}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            # PayPal documents sender_batch_id duplicate protection for 30 days.
            "PayPal-Request-Id": idempotency_key,
        }
        payload = {
            "sender_batch_header": {
                "sender_batch_id": idempotency_key,
                "email_subject": "You have a payment from Proxy Sandbox",
                "email_message": "A payment was initiated through the Proxy hackathon sandbox demo.",
            },
            "items": [{
                "recipient_type": "EMAIL",
                "receiver": recipient_email,
                "amount": {"value": amount, "currency": currency},
                "note": "Proxy Sandbox demo payment",
                "sender_item_id": idempotency_key[:63],
            }],
        }
        response = self._client.post(
            f"{self._base_url}/v1/payments/payouts",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        created = response.json()
        batch_id = created.get("batch_header", {}).get("payout_batch_id")
        if not isinstance(batch_id, str) or not batch_id:
            raise PaymentProviderError("PayPal accepted no identifiable payout batch; reconcile before retrying")

        # A create response is usually ACKNOWLEDGED/PENDING, not proof of settlement.
        detail_response = self._client.get(
            f"{self._base_url}/v1/payments/payouts/{batch_id}",
            headers=headers,
        )
        detail_response.raise_for_status()
        detail = detail_response.json()
        items = detail.get("items") or []
        for item in items:
            payout_item = item.get("payout_item") or {}
            if payout_item.get("sender_item_id") != idempotency_key[:63]:
                continue
            status = item.get("transaction_status", "")
            transaction_id = item.get("transaction_id")
            if status == "SUCCESS" and isinstance(transaction_id, str) and transaction_id:
                return PaymentResult(transaction_id=transaction_id, status="SUCCESS")
            raise PaymentProviderError(f"PayPal payout item is not settled successfully (status={status or 'unknown'})")
        raise PaymentProviderError("PayPal batch does not contain the expected payout item; reconcile before retrying")


class PaymentProvider(PayPalSandboxProvider):
    """Default provider used by the API. Fails closed without Sandbox credentials."""
    pass
