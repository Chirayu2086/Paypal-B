"""API-level regression tests for authenticated agent workflows.

These tests exercise FastAPI routing, request/response validation, and authentication
without contacting OpenAI or PayPal and without creating real payouts.
"""
import pytest
from fastapi.testclient import TestClient

from backend.app import main
from backend.app.config import settings
from backend.app.schemas import AgentProposal


@pytest.fixture
def api_client(monkeypatch):
    # Keep API tests isolated from runtime configuration and database startup.
    monkeypatch.setattr(main, "validate_runtime_config", lambda: None)
    monkeypatch.setattr(main, "init_db", lambda: None)
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
