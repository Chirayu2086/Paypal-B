from decimal import Decimal

import pytest
from fastapi import HTTPException

from backend.app.schemas import AgentProposalRequest
from backend.app.agent import propose_payment


def valid_model_output(**overrides):
    data = {
        "recipient_name": "Jordan Lee",
        "recipient_email": "jordan@example.com",
        "amount": "85",
        "currency": "USD",
        "purpose": "Logo revisions",
        "condition_summary": "User says final source files are expected",
        "explanation": "Extracted recipient, amount and purpose from the request.",
        "risk_flags": [],
    }
    data.update(overrides)
    return data


def test_proposal_extracts_and_normalizes_amount_without_creating_payment():
    proposal = propose_payment(
        AgentProposalRequest(text="Prepare $85 for Jordan for logo revisions."),
        model_call=lambda _: valid_model_output(),
    )
    assert proposal.amount == "85.00"
    assert proposal.ready_for_review is True
    assert proposal.missing_fields == []
    assert proposal.source_text == "Prepare $85 for Jordan for logo revisions."
    assert proposal.recipient_email == "jordan@example.com"


@pytest.mark.parametrize("amount", ["NaN", "Infinity", "-1", "0", "12.345", "not-money"])
def test_invalid_model_amount_is_never_marked_ready(amount):
    proposal = propose_payment(
        AgentProposalRequest(text="Pay someone"),
        model_call=lambda _: valid_model_output(amount=amount),
    )
    assert proposal.amount is None
    assert proposal.ready_for_review is False
    assert "valid amount" in proposal.missing_fields
    assert any("Amount could not be validated" in flag for flag in proposal.risk_flags)


def test_missing_fields_remain_missing_and_explanation_is_returned():
    proposal = propose_payment(
        AgentProposalRequest(text="Prepare a payment for a design task."),
        model_call=lambda _: valid_model_output(
            recipient_name=None, recipient_email=None, amount=None, purpose=None,
            condition_summary=None, explanation="The request lacks key details.",
            risk_flags=["Missing recipient email"],
        ),
    )
    assert proposal.ready_for_review is False
    assert set(proposal.missing_fields) == {"recipient name", "recipient email", "valid amount", "purpose"}
    assert proposal.recipient_email is None
    assert proposal.condition_summary is None


def test_unexpected_model_fields_are_rejected():
    with pytest.raises(HTTPException) as exc:
        propose_payment(
            AgentProposalRequest(text="Pay Jordan"),
            model_call=lambda _: valid_model_output(approved=True),
        )
    assert exc.value.status_code == 502


def test_empty_source_is_rejected():
    with pytest.raises(HTTPException) as exc:
        propose_payment(
            AgentProposalRequest(text=" "),
            model_call=lambda _: valid_model_output(),
        )
    assert exc.value.status_code == 422
