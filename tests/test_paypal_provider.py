import json
import httpx
import pytest

from backend.app.config import settings
from backend.app.payments import PayPalSandboxProvider, PaymentProviderNotConfigured, PaymentProviderError


def make_client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_provider_fails_closed_without_sandbox_credentials(monkeypatch):
    monkeypatch.setattr(settings, "paypal_mode", "sandbox")
    monkeypatch.setattr(settings, "paypal_client_id", "")
    monkeypatch.setattr(settings, "paypal_client_secret", "")
    provider = PayPalSandboxProvider(client=make_client(lambda request: pytest.fail("network should not be called")))
    with pytest.raises(PaymentProviderNotConfigured):
        provider.execute_payout(
            recipient_email="jordan@example.com",
            amount_cents=8500,
            currency="USD",
            idempotency_key="proxy-intent-123",
        )


def test_provider_only_reports_success_after_item_level_success(monkeypatch):
    monkeypatch.setattr(settings, "paypal_mode", "sandbox")
    monkeypatch.setattr(settings, "paypal_client_id", "sandbox-id")
    monkeypatch.setattr(settings, "paypal_client_secret", "sandbox-secret")
    seen = []

    def handler(request):
        seen.append(request)
        if request.url.path == "/v1/oauth2/token":
            assert request.headers.get("authorization", "").startswith("Basic ")
            return httpx.Response(200, json={"access_token": "sandbox-token"})
        if request.method == "POST" and request.url.path == "/v1/payments/payouts":
            body = json.loads(request.content)
            assert body["sender_batch_header"]["sender_batch_id"] == "proxy-intent-123"
            assert body["items"][0]["amount"] == {"value": "85.00", "currency": "USD"}
            assert request.headers["PayPal-Request-Id"] == "proxy-intent-123"
            return httpx.Response(201, json={"batch_header": {"payout_batch_id": "BATCH-1", "batch_status": "PENDING"}})
        if request.method == "GET" and request.url.path == "/v1/payments/payouts/BATCH-1":
            return httpx.Response(200, json={"items": [{
                "transaction_status": "SUCCESS",
                "transaction_id": "TXN-123",
                "payout_item": {"sender_item_id": "proxy-intent-123"},
            }]})
        return httpx.Response(404, json={"name": "NOT_FOUND"})

    provider = PayPalSandboxProvider(client=make_client(handler), sleep=lambda _: None)
    result = provider.execute_payout(
        recipient_email="jordan@example.com",
        amount_cents=8500,
        currency="USD",
        idempotency_key="proxy-intent-123",
    )
    assert result.transaction_id == "TXN-123"
    assert result.status == "SUCCESS"
    assert len(seen) == 3


def test_provider_does_not_treat_pending_item_as_success(monkeypatch):
    monkeypatch.setattr(settings, "paypal_mode", "sandbox")
    monkeypatch.setattr(settings, "paypal_client_id", "sandbox-id")
    monkeypatch.setattr(settings, "paypal_client_secret", "sandbox-secret")

    def handler(request):
        if request.url.path == "/v1/oauth2/token":
            return httpx.Response(200, json={"access_token": "sandbox-token"})
        if request.method == "POST" and request.url.path == "/v1/payments/payouts":
            return httpx.Response(201, json={"batch_header": {"payout_batch_id": "BATCH-2", "batch_status": "PENDING"}})
        if request.method == "GET" and request.url.path == "/v1/payments/payouts/BATCH-2":
            return httpx.Response(200, json={"items": [{
                "transaction_status": "PENDING",
                "transaction_id": "NOT-SETTLED",
                "payout_item": {"sender_item_id": "proxy-intent-456"},
            }]})
        return httpx.Response(404)

    provider = PayPalSandboxProvider(client=make_client(handler), sleep=lambda _: None)
    with pytest.raises(PaymentProviderError):
        provider.execute_payout(
            recipient_email="jordan@example.com",
            amount_cents=8500,
            currency="USD",
            idempotency_key="proxy-intent-456",
        )

def test_provider_polls_pending_until_success(monkeypatch):
    monkeypatch.setattr(settings, "paypal_mode", "sandbox")
    monkeypatch.setattr(settings, "paypal_client_id", "sandbox-id")
    monkeypatch.setattr(settings, "paypal_client_secret", "sandbox-secret")
    detail_calls = 0
    sleeps = []

    def handler(request):
        nonlocal detail_calls
        if request.url.path == "/v1/oauth2/token":
            return httpx.Response(200, json={"access_token": "sandbox-token"})
        if request.method == "POST" and request.url.path == "/v1/payments/payouts":
            return httpx.Response(201, json={"batch_header": {"payout_batch_id": "BATCH-POLL", "batch_status": "PENDING"}})
        if request.method == "GET" and request.url.path == "/v1/payments/payouts/BATCH-POLL":
            detail_calls += 1
            status = "PENDING" if detail_calls == 1 else "SUCCESS"
            return httpx.Response(200, json={"items": [{
                "transaction_status": status,
                "transaction_id": "TXN-POLL" if status == "SUCCESS" else None,
                "payout_item": {"sender_item_id": "proxy-intent-poll"},
            }]})
        return httpx.Response(404)

    provider = PayPalSandboxProvider(
        client=make_client(handler),
        max_status_checks=3,
        poll_interval_seconds=0.25,
        sleep=sleeps.append,
    )
    result = provider.execute_payout(
        recipient_email="jordan@example.com",
        amount_cents=8500,
        currency="USD",
        idempotency_key="proxy-intent-poll",
    )
    assert result.transaction_id == "TXN-POLL"
    assert detail_calls == 2
    assert sleeps == [0.25]
