# Evidence review and risk triage

Proxy's evidence-review endpoint is a **triage checklist**, not a verification engine.

## Endpoint

Authenticated request:

```http
POST /v1/agent/evidence-review
Authorization: Bearer <trusted JWT>
Content-Type: application/json
```

Example body:

```json
{
  "claim": "Supplier says delivery is complete",
  "evidence": [
    {
      "label": "Delivery receipt",
      "url": "https://example.com/receipt",
      "note": "Receipt supplied by requester"
    }
  ]
}
```

The response always sets `verified: false` and each supplied item to `status: "unverified"`. It checks only basic URL syntax and whether HTTPS is used. It does not open URLs, authenticate a publisher, inspect documents, establish that a claim is true, or assess fraud. Submitter notes are untrusted descriptions, not corroboration.

## Safe operating model

1. Treat all claims, links, and notes as untrusted input.
2. Manually inspect source provenance, date, and the exact passage supporting the claim.
3. Record contradictory evidence and unresolved gaps.
4. Keep payment creation, fingerprint-bound approval, execution, and reconciliation in their existing separate workflow.

Do not use the response as an automated approve/deny decision or as a substitute for due diligence. No payment action is performed by this endpoint.
