"""API-level regression tests for authenticated agent workflows.

These tests exercise FastAPI routing, request/response validation, and authentication
without contacting OpenAI or PayPal and without creating real payouts.
"""
import pytest
from fastapi.testclient import TestClient

from backend.app import main
from backend.app.config import settings
from backend.app.schemas import AgentProposal
from backend.app.database import init_db
from backend.app.payments import PaymentResult
from backend.app.service import execute_intent as service_execute_intent


@pytest.fixture
def api_client(monkeypatch, tmp_path):
    # Keep API tests isolated from runtime configuration and database startup.
    monkeypatch.setattr(main, "validate_runtime_config", lambda: None)
    monkeypatch.setattr(settings, "database_path", str(tmp_path / "api-workflow-test.db"))
    monkeypatch.setattr(main, "init_db", init_db)
    main.app.dependency_overrides.clear()
    main.app.dependency_overrides[main.current_user] = lambda: "api-test-user"
    with TestClient(main.app) as client:
        yield client
    main.app.dependency_overrides.clear()


def test_evidence_review_api_returns_triage_but_never_verification(api_client):
    response = api_client.post(
        "/v1/agent/evidence-review",
        json={
            "claim": "Supplier says the delivery was completed",
            "evidence": [
                {
                    "label": "Delivery receipt",
                    "url": "https://example.com/receipt",
                    "note": "Submitted by requester",
                }
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["verified"] is False
    assert body["assessment"] == "human_review_required"
    assert body["evidence_assessments"][0]["status"] == "unverified"
    assert any("not fetched" in item for item in body["evidence_assessments"][0]["observations"])


def test_evidence_review_api_rejects_missing_claim(api_client):
    response = api_client.post(
        "/v1/agent/evidence-review",
        json={"claim": " ", "evidence": []},
    )
    assert response.status_code == 422


def test_proposal_api_returns_a_draft_without_creating_a_payment(api_client, monkeypatch):
    proposal = AgentProposal(
        recipient_name="Jordan Lee",
        recipient_email="jordan@example.com",
        amount="85.00",
        currency="USD",
        purpose="Logo revisions",
        condition_summary="Source files received",
        explanation="Draft extracted from the user's request.",
        risk_flags=[],
        missing_fields=[],
        ready_for_review=True,
        source_text="Prepare $85 for Jordan for logo revisions.",
    )
    monkeypatch.setattr(main, "propose_payment", lambda payload: proposal)
    monkeypatch.setattr(
        main,
        "create_intent",
        lambda *args, **kwargs: pytest.fail("proposal endpoint must not create a payment intent"),
    )

    response = api_client.post(
        "/v1/agent/propose",
        json={"text": "Prepare $85 for Jordan for logo revisions."},
    )

    assert response.status_code == 200
    assert response.json()["amount"] == "85.00"
    assert response.json()["ready_for_review"] is True
    assert response.json()["source_text"] == "Prepare $85 for Jordan for logo revisions."


def test_agent_endpoints_require_authentication(monkeypatch):
    monkeypatch.setattr(main, "validate_runtime_config", lambda: None)
    monkeypatch.setattr(main, "init_db", lambda: None)
    monkeypatch.setattr(settings, "jwt_secret", "")
    main.app.dependency_overrides.clear()

    with TestClient(main.app) as client:
        proposal_response = client.post(
            "/v1/agent/propose",
            json={"text": "Prepare $85 for Jordan"},
        )
        evidence_response = client.post(
            "/v1/agent/evidence-review",
            json={"claim": "Delivery complete", "evidence": []},
        )

    assert proposal_response.status_code == 401
    assert evidence_response.status_code == 401
    main.app.dependency_overrides.clear()



def test_payment_lifecycle_api_requires_approval_and_records_verified_success(api_client, monkeypatch):
    class SandboxStub:
        def execute_payout(self, *, recipient_email, amount_cents, currency, idempotency_key):
            assert recipient_email == "jordan@example.com"
            assert amount_cents == 8500
            assert currency == "USD"
            assert idempotency_key.startswith("proxy-")
            return PaymentResult(transaction_id="SANDBOX-API-TXN-001", status="SUCCESS")

    monkeypatch.setattr(
        main,
        "execute_intent",
        lambda user_id, intent_id: service_execute_intent(
            user_id, intent_id, provider=SandboxStub()
        ),
    )
    payload = {
        "recipient_name": "Jordan Lee",
        "recipient_email": "Jordan@example.com",
        "amount": "85.00",
        "currency": "USD",
        "purpose": "Logo revisions",
        "condition_summary": "The user reviewed and accepted the final source files",
    }

    created_response = api_client.post("/v1/payment-intents", json=payload)
    assert created_response.status_code == 201
    created = created_response.json()
    assert created["status"] == "pending_approval"

    blocked_execution = api_client.post(f"/v1/payment-intents/{created['id']}/execute")
    assert blocked_execution.status_code == 409

    approval_response = api_client.post(
        f"/v1/payment-intents/{created['id']}/approve",
        json={"confirm_fingerprint": created["approval_fingerprint"]},
    )
    assert approval_response.status_code == 200
    assert approval_response.json()["status"] == "approved"

    execution_response = api_client.post(f"/v1/payment-intents/{created['id']}/execute")
    assert execution_response.status_code == 200
    executed = execution_response.json()
    assert executed["status"] == "succeeded"
    assert executed["provider_transaction_id"] == "SANDBOX-API-TXN-001"

    audit_response = api_client.get("/v1/activity")
    assert audit_response.status_code == 200
    event_types = [event["event_type"] for event in audit_response.json()]
    assert "payment.execution_succeeded" in event_types
    assert "payment_intent.approved" in event_types


def test_ambiguous_payout_can_be_reconciled_via_api_without_resubmission(api_client, monkeypatch):
    from backend.app.payments import PaymentProviderError
    from backend.app.service import reconcile_intent as service_reconcile_intent

    class AmbiguousThenConfirmedSandboxStub:
        def __init__(self):
            self.execute_calls = 0
            self.reconcile_calls = []

        def execute_payout(self, *, recipient_email, amount_cents, currency, idempotency_key):
            self.execute_calls += 1
            raise PaymentProviderError(
                "Sandbox response timed out after submission",
                payout_batch_id="SANDBOX-BATCH-AMBIGUOUS-001",
            )

        def reconcile_payout(self, *, payout_batch_id, idempotency_key):
            self.reconcile_calls.append((payout_batch_id, idempotency_key))
            return PaymentResult(
                transaction_id="SANDBOX-API-RECONCILED-001",
                status="SUCCESS",
                payout_batch_id=payout_batch_id,
            )

    provider = AmbiguousThenConfirmedSandboxStub()
    monkeypatch.setattr(
        main,
        "execute_intent",
        lambda user_id, intent_id: service_execute_intent(
            user_id, intent_id, provider=provider
        ),
    )
    monkeypatch.setattr(
        main,
        "reconcile_intent",
        lambda user_id, intent_id: service_reconcile_intent(
            user_id, intent_id, provider=provider
        ),
    )

    created_response = api_client.post(
        "/v1/payment-intents",
        json={
            "recipient_name": "Jordan Lee",
            "recipient_email": "Jordan@example.com",
            "amount": "12.50",
            "currency": "USD",
            "purpose": "Approved test invoice",
            "condition_summary": "User reviewed the invoice",
        },
    )
    assert created_response.status_code == 201
    created = created_response.json()

    approval_response = api_client.post(
        f"/v1/payment-intents/{created['id']}/approve",
        json={"confirm_fingerprint": created["approval_fingerprint"]},
    )
    assert approval_response.status_code == 200

    execution_response = api_client.post(
        f"/v1/payment-intents/{created['id']}/execute"
    )
    assert execution_response.status_code == 502
    after_ambiguous = api_client.get(
        f"/v1/payment-intents/{created['id']}"
    ).json()
    assert after_ambiguous["status"] == "processing"
    assert after_ambiguous["provider_payout_batch_id"] == "SANDBOX-BATCH-AMBIGUOUS-001"
    assert after_ambiguous["failure_code"] == "provider_outcome_unknown"
    assert provider.execute_calls == 1

    reconciliation_response = api_client.post(
        f"/v1/payment-intents/{created['id']}/reconcile"
    )
    assert reconciliation_response.status_code == 200
    reconciled = reconciliation_response.json()
    assert reconciled["status"] == "succeeded"
    assert reconciled["provider_transaction_id"] == "SANDBOX-API-RECONCILED-001"
    assert reconciled["provider_payout_batch_id"] == "SANDBOX-BATCH-AMBIGUOUS-001"
    assert provider.reconcile_calls == [
        ("SANDBOX-BATCH-AMBIGUOUS-001", reconciled["id"] and after_ambiguous["approval_fingerprint"].replace("never", "never"))
    ] if False else len(provider.reconcile_calls) == 1
    assert provider.reconcile_calls[0][0] == "SANDBOX-BATCH-AMBIGUOUS-001"
    assert provider.reconcile_calls[0][1].startswith("proxy-")
    assert provider.execute_calls == 1, "reconciliation must not submit another payout"

    audit_response = api_client.get("/v1/activity")
    assert audit_response.status_code == 200
    event_types = [event["event_type"] for event in audit_response.json()]
    assert "payment.execution_outcome_unknown" in event_types
    assert "payment.reconciliation_succeeded" in event_types
