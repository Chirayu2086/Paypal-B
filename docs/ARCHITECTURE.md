# Proxy Architecture (MVP)

```text
Next.js operator dashboard
  | HTTPS + signed bearer token
  | natural-language draft / create / review / approve / execute / reconcile
  v
FastAPI API
  |-- JWT identity validation
  |-- optional AI extraction endpoint (draft only)
  |-- strict request validation
  |-- owner-scoped list/read/action routes
  |-- server-side transaction + daily limits
  |-- immutable request fingerprint / approval gate
  |-- payment state machine + idempotency key
  v
SQLite (MVP)
  |-- payment intents
  |-- provider payout batch IDs
  |-- audit events
  v
PayPal Sandbox Payouts API
  |-- bounded status polling
  |-- item-level success verification
  |-- read-only reconciliation of existing batch
```

## AI boundary

The optional AI adapter receives natural-language text and returns a strict structured draft. It does not receive payment tools, provider credentials, or authorization to mutate payment state. The API validates output, flags missing fields, and tells the operator to review the extraction. Text is sent to the configured AI provider. User-provided context is not treated as verified evidence.

## State machine

```text
pending_approval --owner approves exact fingerprint--> approved
approved --execution reserved--> processing
processing --provider confirms success--> succeeded
processing --provider outcome ambiguous--> processing (reconcile existing batch)
approved --provider adapter unavailable--> approved (no payout sent)
```

A model cannot directly transition a payment to `approved` or `succeeded`. Limits and approval are enforced by backend code, independently of prompts. The approval fingerprint binds confirmation to the stored recipient, amount, currency, purpose, condition summary, and owner.

## Security boundaries

- JWT identity comes from a trusted issuer; there is no insecure demo-login route.
- AI extraction is advisory and cannot create, approve, or execute payments.
- List and item routes scope database queries to the authenticated owner.
- CORS is restricted to configured exact origins; the frontend token is held in page memory only.
- Unknown provider outcomes stay in `processing` to avoid blind retries.
- Only provider-confirmed transaction IDs and success statuses are represented as successful settlement.
- Reconciliation reads a previously captured payout batch and never submits a second payout.

## Next engineering phases

1. Add independent evidence verification and invoice/document analysis.
2. Integrate a first-party authentication provider.
3. Validate the full flow with PayPal Sandbox accounts and capture evidence for the demo.
4. Add webhook signature verification and bounded provider reconciliation monitoring.
5. Add rate limiting, structured observability, deployment hardening, and independent security review.
