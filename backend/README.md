# Proxy Backend

## Setup

Requires Python 3.11+.

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn backend.app.main:app --reload
```

Run commands from the repository root. Set `JWT_SECRET` to a long random value. The API expects a signed JWT issued by a trusted authentication system; claims must include `sub` and `exp`. There is deliberately no demo login endpoint.

## AI drafting (optional)

Set `AI_API_KEY` in the backend environment to enable `POST /v1/assistant/draft`. `AI_BASE_URL` defaults to `https://api.openai.com/v1`; `AI_MODEL` defaults to `gpt-4o-mini`. The endpoint accepts a natural-language instruction and returns validated draft fields, missing fields, and review warnings. It is authenticated and does not create, approve, or execute a payment. User text is sent to the configured AI provider. Never expose the provider key to the frontend.

## API

- `GET /health` — liveness only; includes whether AI drafting is configured, not whether PayPal is ready.
- `POST /v1/assistant/draft` — extract a human-reviewed draft; no payment intent is created.
- `POST /v1/payment-intents` — create a request in `pending_approval`.
- `GET /v1/payment-intents?limit=50` — list the authenticated owner's most recent intents (limit 1–100).
- `GET /v1/payment-intents/{id}` — read one owned request.
- `POST /v1/payment-intents/{id}/approve` — approve the exact immutable request snapshot using its returned `approval_fingerprint`.
- `POST /v1/payment-intents/{id}/execute` — execute an approved request through the configured Sandbox adapter.
- `POST /v1/payment-intents/{id}/reconcile` — re-read an existing payout batch; never submits a new payout.
- `GET /v1/activity?limit=50` — authenticated user's audit events (limit 1–100).

All `/v1` routes require a signed bearer token. Configure `CORS_ALLOWED_ORIGINS` as a comma-separated allowlist of exact frontend origins.

## Safety properties

- Amounts use Decimal and integer cents.
- Limits are enforced server-side, never by a model prompt alone.
- AI output is only a draft; it cannot authorize a payment or bypass schema and policy validation.
- Only the authenticated owner can list, read, approve, execute, or reconcile their intent.
- Approval is bound to a canonical request fingerprint.
- SQLite `BEGIN IMMEDIATE` reserves state before external execution, preventing concurrent local duplicate attempts.
- Provider timeouts/errors leave ambiguous outcomes in `processing`; reconcile before any retry.
- Only provider-confirmed transaction IDs and success statuses are represented as successful settlement.

## Limitations

This is a hackathon MVP, not production financial infrastructure. Before production use, add mature auth, rate limiting, abuse monitoring, PayPal webhook signature verification, reconciliation monitoring, distributed idempotency, production migrations, and independent security review. SQLite locking is suitable for local single-process development, not multi-instance deployment.
