from dataclasses import dataclass
from decimal import Decimal
import time
from collections.abc import Callable
import httpx

from backend.app.config import settings


@dataclass(frozen=True)
class PaymentResult:
    transaction_id: str
    status: str
    payout_batch_id: str | None = None


class PaymentProviderNotConfigured(RuntimeError):
    pass


class PaymentProviderError(RuntimeError):
    """Provider did not yield a verified terminal success."""

    def __init__(self, message: str, *, payout_batch_id: str | None = None):
        super().__init__(message)
        self.payout_batch_id = payout_batch_id


class PayPalSandboxProvider:
    """Single-recipient PayPal Payouts adapter. Sandbox only.

    It never treats an acknowledged/pending batch as settled. If a response is
    ambiguous, the caller must reconcile using the stable sender_batch_id before
    attempting another payout.
    """

    def __init__(self, *, client: httpx.Client | None = None, max_status_checks: int = 3, poll_interval_seconds: float = 1.0, sleep: Callable[[float], None] = time.sleep):
        if max_status_checks < 1:
            raise ValueError("max_status_checks must be at least 1")
        if poll_interval_seconds < 0:
            raise ValueError("poll_interval_seconds cannot be negative")
        self._client = client or httpx.Client(timeout=httpx.Timeout(15.0, connect=5.0))
        self._base_url = "https://api-m.sandbox.paypal.com"
        self._max_status_checks = max_status_checks
        self._poll_interval_seconds = poll_interval_seconds
        self._sleep = sleep

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
        # Poll only a bounded number of times. If still ambiguous, the service keeps
        # the intent in processing; callers must not blindly submit a new payout.
        last_status = "unknown"
        for attempt in range(self._max_status_checks):
            detail_response = self._client.get(
                f"{self._base_url}/v1/payments/payouts/{batch_id}",
                headers=headers,
            )
            try:
                detail_response.raise_for_status()
                detail = detail_response.json()
            except (httpx.HTTPError, ValueError) as exc:
                raise PaymentProviderError(
                    "Could not verify the existing PayPal payout batch; reconcile before any retry",
                    payout_batch_id=batch_id,
                ) from exc
            items = detail.get("items") or []
            matching_item = next(
                (
                    item for item in items
                    if (item.get("payout_item") or {}).get("sender_item_id") == idempotency_key[:63]
                ),
                None,
            )
            if matching_item is None:
                raise PaymentProviderError("PayPal batch does not contain the expected payout item; reconcile before retrying")

            last_status = str(matching_item.get("transaction_status") or "unknown").upper()
            transaction_id = matching_item.get("transaction_id")
            if last_status == "SUCCESS" and isinstance(transaction_id, str) and transaction_id:
                return PaymentResult(transaction_id=transaction_id, status="SUCCESS", payout_batch_id=batch_id)
            if last_status in {"FAILED", "RETURNED", "BLOCKED", "DENIED", "CANCELED", "CANCELLED", "REFUNDED", "REVERSED"}:
                raise PaymentProviderError(f"PayPal payout item reached terminal status={last_status}", payout_batch_id=batch_id)
            if attempt + 1 < self._max_status_checks:
                self._sleep(self._poll_interval_seconds)

        raise PaymentProviderError(
            f"PayPal payout item did not reach verified success after {self._max_status_checks} checks (status={last_status}); reconcile before retrying",
            payout_batch_id=batch_id,
        )

 
    def reconcile_payout(self, *, payout_batch_id: str, idempotency_key: str) -> PaymentResult:
        """Read an existing payout batch; this method never creates a payout."""
        token = self._access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }
        response = self._client.get(
            f"{self._base_url}/v1/payments/payouts/{payout_batch_id}",
            headers=headers,
        )
        try:
            response.raise_for_status()
            detail = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise PaymentProviderError(
                "Could not read the existing PayPal payout batch",
                payout_batch_id=payout_batch_id,
            ) from exc
        items = detail.get("items") or []
        matching_item = next(
            (
                item for item in items
                if (item.get("payout_item") or {}).get("sender_item_id") == idempotency_key[:63]
            ),
            None,
        )
        if matching_item is None:
            raise PaymentProviderError(
                "PayPal batch does not contain the expected payout item",
                payout_batch_id=payout_batch_id,
            )
        status = str(matching_item.get("transaction_status") or "unknown").upper()
        transaction_id = matching_item.get("transaction_id")
        if status == "SUCCESS" and isinstance(transaction_id, str) and transaction_id:
            return PaymentResult(transaction_id=transaction_id, status="SUCCESS", payout_batch_id=payout_batch_id)
        raise PaymentProviderError(
            f"PayPal payout item is not verified successful (status={status})",
            payout_batch_id=payout_batch_id,
        )


class PaymentProvider(PayPalSandboxProvider):
    """Default provider used by the API. Fails closed without Sandbox credentials."""
    pass
