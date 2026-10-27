from decimal import Decimal

import pytest
from fastapi import HTTPException

from backend.app.config import settings
from backend.app.database import connect, init_db
from backend.app.payments import PaymentResult, PaymentProviderNotConfigured, PaymentProviderError
from backend.app.schemas import PaymentIntentCreate
from backend.app.service import approve_intent, create_intent, execute_intent, get_owned_intent, list_activity, reconcile_intent


class SuccessfulProvider:
    def execute_payout(self, *, recipient_email, amount_cents, currency, idempotency_key):
        assert recipient_email == "jordan@example.com"
        assert amount_cents == 8500
        assert currency == "USD"
        assert idempotency_key
        return PaymentResult(transaction_id="SANDBOX-TXN-123", status="COMPLETED")


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "database_path", str(tmp_path / "proxy-test.db"))
    monkeypatch.setattr(settings, "max_transaction_amount", "250.00")
    monkeypatch.setattr(settings, "daily_spend_limit", "500.00")
    init_db()


def payload(amount="85.00"):
    return PaymentIntentCreate(
        recipient_name="Jordan",
        recipient_email="Jordan@example.com",
        amount=Decimal(amount),
        currency="USD",
        purpose="Logo revisions",
        condition_summary="Final source files received and reviewed by the user",
    )


def test_new_intent_requires_approval_and_fingerprint_is_returned():
    created = create_intent("user-1", payload())
    assert created["status"] == "pending_approval"
    assert len(created["approval_fingerprint"]) == 64
    with pytest.raises(HTTPException) as exc:
        execute_intent("user-1", created["id"], provider=SuccessfulProvider())
    assert exc.value.status_code == 409


def test_wrong_fingerprint_cannot_approve():
    created = create_intent("user-1", payload())
    with pytest.raises(HTTPException) as exc:
        approve_intent("user-1", created["id"], "0" * 64)
    assert exc.value.status_code == 409
    assert get_owned_intent("user-1", created["id"])["status"] == "pending_approval"


def test_only_owner_can_approve_or_read():
    created = create_intent("user-1", payload())
    with pytest.raises(HTTPException) as exc:
        approve_intent("user-2", created["id"], created["approval_fingerprint"])
    assert exc.value.status_code == 404
    with pytest.raises(HTTPException) as exc:
        get_owned_intent("user-2", created["id"])
    assert exc.value.status_code == 404


def test_successful_provider_result_is_audited():
    created = create_intent("user-1", payload())
    approved = approve_intent("user-1", created["id"], created["approval_fingerprint"])
    assert approved["status"] == "approved"
    succeeded = execute_intent("user-1", created["id"], provider=SuccessfulProvider())
    assert succeeded["status"] == "succeeded"
    assert succeeded["provider_transaction_id"] == "SANDBOX-TXN-123"
    assert [e["event_type"] for e in list_activity("user-1")] == [
        "payment.execution_succeeded", "payment.execution_started", "payment_intent.approved", "payment_intent.created"
    ]


def test_duplicate_execution_is_rejected():
    created = create_intent("user-1", payload())
    approve_intent("user-1", created["id"], created["approval_fingerprint"])
    execute_intent("user-1", created["id"], provider=SuccessfulProvider())
    with pytest.raises(HTTPException) as exc:
        execute_intent("user-1", created["id"], provider=SuccessfulProvider())
    assert exc.value.status_code == 409


def test_unconfigured_provider_sends_nothing_and_keeps_approval():
    created = create_intent("user-1", payload())
    approve_intent("user-1", created["id"], created["approval_fingerprint"])
    with pytest.raises(HTTPException) as exc:
        execute_intent("user-1", created["id"])
    assert exc.value.status_code == 503
    current = get_owned_intent("user-1", created["id"])
    assert current["status"] == "approved"
    assert current["provider_transaction_id"] is None
    assert current["failure_code"] == "provider_not_configured"


def test_per_transaction_limit_is_enforced_server_side():
    with pytest.raises(HTTPException) as exc:
        create_intent("user-1", payload("250.01"))
    assert exc.value.status_code == 422


def test_daily_limit_includes_approved_commitments():
    first = create_intent("user-1", payload("250.00"))
    approve_intent("user-1", first["id"], first["approval_fingerprint"])
    second = create_intent("user-1", payload("250.00"))
    approve_intent("user-1", second["id"], second["approval_fingerprint"])
    with pytest.raises(HTTPException) as exc:
        create_intent("user-1", payload("1.00"))
    assert exc.value.status_code == 422


def test_audit_feed_is_scoped_to_owner():
    create_intent("user-1", payload())
    create_intent("user-2", payload())
    events = list_activity("user-1")
    assert len(events) == 1
    assert events[0]["actor_id"] == "user-1"


class UnknownOutcomeProvider:
    def execute_payout(self, *, recipient_email, amount_cents, currency, idempotency_key):
        raise PaymentProviderError("provider response was ambiguous", payout_batch_id="BATCH-UNKNOWN")


class ReconciliationProvider:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.reconcile_calls = []
        self.execute_calls = 0

    def execute_payout(self, **kwargs):
        self.execute_calls += 1
        raise AssertionError("reconciliation must never create another payout")

    def reconcile_payout(self, *, payout_batch_id, idempotency_key):
        self.reconcile_calls.append((payout_batch_id, idempotency_key))
        if self.error:
            raise self.error
        return self.result


def test_unknown_execution_persists_batch_for_later_reconciliation():
    created = create_intent("user-1", payload())
    approved = approve_intent("user-1", created["id"], created["approval_fingerprint"])
    with pytest.raises(HTTPException) as exc:
        execute_intent("user-1", created["id"], provider=UnknownOutcomeProvider())
    assert exc.value.status_code == 502
    current = get_owned_intent("user-1", created["id"])
    assert current["status"] == "processing"
    assert current["provider_payout_batch_id"] == "BATCH-UNKNOWN"


def test_reconciliation_marks_success_only_after_provider_confirmation():
    created = create_intent("user-1", payload())
    approve_intent("user-1", created["id"], created["approval_fingerprint"])
    with pytest.raises(HTTPException):
        execute_intent("user-1", created["id"], provider=UnknownOutcomeProvider())

    provider = ReconciliationProvider(
        result=PaymentResult(
            transaction_id="SANDBOX-RECONCILED-TXN",
            status="SUCCESS",
            payout_batch_id="BATCH-UNKNOWN",
        )
    )
    reconciled = reconcile_intent("user-1", created["id"], provider=provider)
    assert reconciled["status"] == "succeeded"
    assert reconciled["provider_transaction_id"] == "SANDBOX-RECONCILED-TXN"
    assert reconciled["provider_payout_batch_id"] == "BATCH-UNKNOWN"
    assert len(provider.reconcile_calls) == 1
    assert provider.reconcile_calls[0][0] == "BATCH-UNKNOWN"
    assert provider.reconcile_calls[0][1].startswith("proxy-")
    assert provider.execute_calls == 0
    assert "payment.reconciliation_succeeded" in [e["event_type"] for e in list_activity("user-1")]


def test_reconciliation_is_owner_scoped_and_requires_processing_batch():
    created = create_intent("user-1", payload())
    with pytest.raises(HTTPException) as wrong_owner:
        reconcile_intent("user-2", created["id"], provider=ReconciliationProvider())
    assert wrong_owner.value.status_code == 404

    approved = approve_intent("user-1", created["id"], created["approval_fingerprint"])
    with pytest.raises(HTTPException) as not_processing:
        reconcile_intent("user-1", created["id"], provider=ReconciliationProvider())
    assert not_processing.value.status_code == 409

    # Simulate an ambiguous provider outcome where no batch identifier was captured.
    with connect() as conn:
        conn.execute("UPDATE payment_intents SET status='processing', failure_code='provider_outcome_unknown' WHERE id=?", (created["id"],))
    provider = ReconciliationProvider()
    with pytest.raises(HTTPException) as missing_batch:
        reconcile_intent("user-1", created["id"], provider=provider)
    assert missing_batch.value.status_code == 409
    assert provider.reconcile_calls == []
    assert provider.execute_calls == 0



def test_reconciliation_does_not_accept_unverified_provider_result():
    created = create_intent("user-1", payload())
    approve_intent("user-1", created["id"], created["approval_fingerprint"])
    with pytest.raises(HTTPException):
        execute_intent("user-1", created["id"], provider=UnknownOutcomeProvider())

    provider = ReconciliationProvider(
        result=PaymentResult(
            transaction_id="",
            status="PENDING",
            payout_batch_id="BATCH-UNKNOWN",
        )
    )
    reconciled = reconcile_intent("user-1", created["id"], provider=provider)
    assert reconciled["status"] == "processing"
    assert reconciled["provider_transaction_id"] is None
    assert reconciled["failure_code"] == "provider_outcome_unknown"
    assert "payment.reconciliation_unresolved" in [e["event_type"] for e in list_activity("user-1")]
    assert provider.execute_calls == 0
