from backend.app.evidence import EvidenceReviewRequest, review_evidence


def test_no_evidence_is_explicitly_unverified():
    result = review_evidence(EvidenceReviewRequest(claim="Supplier says delivery is complete"))
    assert result.verified is False
    assert result.assessment == "human_review_required"
    assert result.evidence_assessments == []
    assert any("No supporting evidence" in flag for flag in result.risk_flags)


def test_https_link_is_not_mistaken_for_verified_evidence():
    result = review_evidence(EvidenceReviewRequest(
        claim="Supplier says delivery is complete",
        evidence=[{"label": "Delivery receipt", "url": "https://example.com/receipt", "note": "Uploaded by requester"}],
    ))
    item = result.evidence_assessments[0]
    assert item.status == "unverified"
    assert any("not fetched" in observation for observation in item.observations)
    assert result.verified is False
    assert any("not been independently verified" in flag for flag in result.risk_flags)


def test_http_link_is_flagged_as_less_secure():
    result = review_evidence(EvidenceReviewRequest(
        claim="Supplier says delivery is complete",
        evidence=[{"label": "Receipt", "url": "http://example.com/receipt"}],
    ))
    assert any("HTTP rather than HTTPS" in flag for flag in result.risk_flags)
    assert result.evidence_assessments[0].status == "unverified"


def test_unsupported_url_scheme_is_flagged():
    result = review_evidence(EvidenceReviewRequest(
        claim="Supplier says delivery is complete",
        evidence=[{"label": "Local file", "url": "file:///tmp/receipt.pdf"}],
    ))
    assert any("malformed or unsupported URL" in flag for flag in result.risk_flags)


def test_evidence_count_is_bounded():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        EvidenceReviewRequest(
            claim="Supplier says delivery is complete",
            evidence=[{"label": f"Evidence {i}"} for i in range(11)],
        )
