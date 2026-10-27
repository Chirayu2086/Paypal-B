# Proxy Architecture (MVP)

```text
Browser / Next.js UI
  | signed bearer token; explicit review + approval action
  v
FastAPI API
  |-- JWT identity validation
  |-- strict request validation
  |-- server-side transaction + daily limits
  |-- immutable request fingerprint / approval gate
  |-- payment state machine + idempotency key
  v
SQLite (MVP)
  |-- payment intents
  |-- append-only-style audit events
  v
Payment provider boundary
  |-- currently fail-closed
  |-- next phase: PayPal Sandbox Payouts adapter + verified webhooks
  v
PayPal Sandbox
```

## State machine

```text
pending_approval --owner approves exact fingerprint--> approved
approved --execution reserved--> processing
processing --provider confirms success--> succeeded
processing --provider outcome ambiguous--> processing (manual reconciliation required)
approved --provider adapter unavailable--> approved (safe to retry after adapter is configured)
```

A model cannot directly transition a payment to `approved` or `succeeded`. Evidence analysis may inform the explanation shown to the user, but it cannot approve a request. The approval fingerprint binds the confirmation to the stored recipient, amount, currency, purpose, condition summary, and owner.

## Security boundaries

- AI output is untrusted input and must be validated as a schema before it can create an intent.
- JWT identity comes from a trusted issuer; there is no insecure demo-login route.
- All payment routes scope database queries to the authenticated owner.
- Limits and approval are enforced in backend code, independently of prompts.
- Unknown provider outcomes stay in `processing` to avoid blind retries that could duplicate a payout.
- Only provider-confirmed transaction IDs and success statuses are represented as successful settlement.

## Next engineering phases

1. Run and expand automated tests.
2. Implement the PayPal Sandbox payout adapter using official API docs and idempotency support.
3. Verify PayPal webhook signatures and reconcile delayed/ambiguous outcomes.
4. Add a real authentication provider and request throttling.
5. Build the Next.js chat, approval confirmation, limits screen, and audit feed.
6. Add AI intent extraction and evidence analysis behind structured, narrow tools.
