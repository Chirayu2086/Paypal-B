import json

import pytest

from backend.app.ai_agent import extract_payment_draft
from backend.app.config import settings


class FakeResponse:
    def __init__(self, content):
        self.content = content

    def raise_for_status(self):
        return None

    def json(self):
        return {"choices": [{"message": {"content": json.dumps(self.content)}}]}


class FakeClient:
    content = {}

    def __init__(self, *args, **kwargs):
        self.args = args

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def post(self, url, headers, json):
        assert url.endswith("/chat/completions")
        assert headers["Authorization"] == "Bearer test-ai-key"
        assert json["temperature"] == 0
        assert json["response_format"] == {"type": "json_object"}
        return FakeResponse(self.content)


def setup_ai(monkeypatch, content):
    monkeypatch.setattr(settings, "ai_api_key", "test-ai-key")
    monkeypatch.setattr(settings, "ai_base_url", "https://ai.example/v1/")
    monkeypatch.setattr(settings, "ai_model", "test-model")
    monkeypatch.setattr(settings, "max_transaction_amount", "250.00")
    monkeypatch.setattr("backend.app.ai_agent.httpx.Client", FakeClient)
    FakeClient.content = content


def test_extracts_only_draft_and_never_creates_payment(monkeypatch):
    setup_ai(monkeypatch, {
        "recipient_name": "Jordan Lee",
        "recipient_email": "jordan@example.com",
        "amount": "85",
        "currency": "USD",
        "purpose": "Logo revisions",
        "condition_summary": "Files reviewed by user",
    })
    result = extract_payment_draft("Pay Jordan Lee jordan@example.com $85 for logo revisions; files reviewed.")
    assert result.draft.amount == "85.00"
    assert result.draft.recipient_email == "jordan@example.com"
    assert result.missing_fields == []
    assert result.requires_human_review is True
    assert result.created_payment_intent is False
    assert any("not independently verified" in warning for warning in result.warnings)


def test_missing_fields_are_returned_instead_of_guessed(monkeypatch):
    setup_ai(monkeypatch, {
        "recipient_name": "Jordan",
        "recipient_email": None,
        "amount": None,
        "currency": None,
        "purpose": "Design work",
        "condition_summary": None,
    })
    result = extract_payment_draft("Pay Jordan for design work.")
    assert result.missing_fields == ["recipient_email", "amount", "currency"]
    assert result.draft.amount is None
    assert result.created_payment_intent is False


def test_unconfigured_ai_fails_closed(monkeypatch):
    monkeypatch.setattr(settings, "ai_api_key", "")
    with pytest.raises(RuntimeError, match="not configured"):
        extract_payment_draft("Pay Jordan $20")


@pytest.mark.parametrize("amount", ["0", "-1", "NaN", "1.239", "Infinity"])
def test_invalid_amount_from_model_is_rejected(monkeypatch, amount):
    setup_ai(monkeypatch, {
        "recipient_name": "Jordan",
        "recipient_email": "jordan@example.com",
        "amount": amount,
        "currency": "USD",
        "purpose": "Design work",
        "condition_summary": None,
    })
    with pytest.raises(RuntimeError, match="invalid structured response"):
        extract_payment_draft("Pay Jordan.")
