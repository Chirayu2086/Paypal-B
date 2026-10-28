# Proxy Architecture (MVP)

```text
Next.js operator dashboard
  | HTTPS + signed bearer token
  | create intent / review / approve / execute / reconcile
  v
FastAPI API
  |-- JWT identity validation
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

## State machine

```text
pending_approval --owner approves exact fingerprint--> approved
approved --execution reserved--> processing
processing --provider confirms success--> succeeded
processing --provider outcome ambiguous--> processing (reconcile existing batch)
approved --provider adapter unavailable--> approved (no payout sent)
```

A model cannot directly transition a payment to `approved` or `succeeded`. Evidence analysis may inform the explanation shown to the user, but it cannot approve a request. The approval fingerprint binds confirmation to the stored recipient, amount, currency, purpose, condition summary, and owner.

## Security boundaries

- AI output is untrusted input and must be validated as a schema before it can create an intent.
- JWT identity comes from a trusted issuer; there is no insecure demo-login route.
- List and item routes scope database queries to the authenticated owner.
- CORS is restricted to configured exact origins; the frontend token is held in page memory only.
- Limits and approval are enforced in backend code, independently of prompts.
- Unknown provider outcomes stay in `processing` to avoid blind retries that could duplicate a payout.
- Only provider-confirmed transaction IDs and success statuses are represented as successful settlement.
- Reconciliation reads a previously captured payout batch and never submits a second payout.

## Next engineering phases

1. Add an AI intent extraction adapter with strict structured output and explicit confirmation before intent creation.
2. Integrate a first-party authentication provider.
3. Validate the full flow with PayPal Sandbox accounts and capture evidence for the demo.
4. Add webhook signature verification and bounded provider reconciliation monitoring.
5. Add rate limiting, structured observability, deployment hardening, and independent security review.
