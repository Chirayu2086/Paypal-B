"""Deterministic evidence triage. This module does not fetch or verify external claims."""
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field


class EvidenceItem(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    label: str = Field(min_length=1, max_length=120)
    url: str | None = Field(default=None, max_length=2048)
    note: str | None = Field(default=None, max_length=1000)


class EvidenceReviewRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    claim: str = Field(min_length=5, max_length=1000)
    evidence: list[EvidenceItem] = Field(default_factory=list, max_length=10)


class EvidenceAssessment(BaseModel):
    label: str
    url: str | None
    status: str = "unverified"
    observations: list[str]


class EvidenceReviewResponse(BaseModel):
    claim: str
    assessment: str = "human_review_required"
    verified: bool = False
    evidence_assessments: list[EvidenceAssessment]
    risk_flags: list[str]
    next_steps: list[str]


def review_evidence(payload: EvidenceReviewRequest) -> EvidenceReviewResponse:
    """Assess submission completeness and URL hygiene without claiming truth verification."""
    assessments: list[EvidenceAssessment] = []
    flags: list[str] = [
        "Claim has not been independently verified.",
        "User-provided links and notes are untrusted input; this service does not open URLs.",
    ]

    if not payload.evidence:
        flags.append("No supporting evidence was supplied.")

    for item in payload.evidence:
        observations: list[str] = []
        if not item.url:
            observations.append("No source URL supplied; evidence cannot be independently inspected.")
            flags.append(f"Evidence item '{item.label}' has no source URL.")
        else:
            parsed = urlparse(item.url)
            if parsed.scheme not in ("http", "https") or not parsed.netloc:
                observations.append("URL format is not a standard HTTP(S) web address.")
                flags.append(f"Evidence item '{item.label}' has a malformed or unsupported URL.")
            elif parsed.scheme != "https":
                observations.append("HTTP link is not encrypted; prefer an HTTPS source.")
                flags.append(f"Evidence item '{item.label}' uses HTTP rather than HTTPS.")
            else:
                observations.append("HTTPS URL syntax looks plausible; destination and content were not fetched.")
        if item.note:
            observations.append("Submitter note recorded as an unverified description.")
        else:
            observations.append("No submitter note supplied.")
        assessments.append(
            EvidenceAssessment(
                label=item.label,
                url=item.url,
                status="unverified",
                observations=observations,
            )
        )

    next_steps = [
        "Open each source manually and confirm the publisher, date, and relevant passage.",
        "Check that the source directly supports the exact claim rather than a related topic.",
        "Record contradictory evidence and unresolved gaps before making a payment decision.",
        "Keep payment approval and execution in the existing separate, human-controlled workflow.",
    ]
    return EvidenceReviewResponse(
        claim=payload.claim,
        evidence_assessments=assessments,
        risk_flags=flags,
        next_steps=next_steps,
    )
