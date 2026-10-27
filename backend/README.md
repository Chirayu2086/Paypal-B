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

Run commands from the repository root. Set `JWT_SECRET` to a long random value. The API expects a signed JWT issued by a trusted authentication system; there is deliberately no demo login endpoint. JWT claims must include `sub` (user ID) and `exp`.

## API

- `GET /health` — liveness; does not imply PayPal is configured.
- `POST /v1/payment-intents` — create a request in `pending_approval`.
- `GET /v1/payment-intents/{id}` — read an owned request.
- `POST /v1/payment-intents/{id}/approve` — approve the exact immutable request snapshot using its returned `approval_fingerprint`.
- `POST /v1/payment-intents/{id}/execute` — execute an approved request through a configured provider adapter.
- `GET /v1/activity` — authenticated user's audit events.

All `/v1` routes require a signed bearer token. This branch is sandbox-only. The provider adapter intentionally fails closed until the PayPal Sandbox integration is completed. No endpoint should claim a payment succeeded unless a provider response confirms it.

## Safety properties

- Amounts use `Decimal` and integer cents.
- Limits are enforced server-side, never by the model prompt alone.
- Only the authenticated owner can approve or execute their intent.
- Approval is bound to a canonical request fingerprint.
- SQLite `BEGIN IMMEDIATE` reserves state before external execution, preventing concurrent local duplicate attempts.
- Provider timeouts/errors leave an ambiguous outcome in `processing` for reconciliation; they must not be retried blindly.
- Provider-not-configured errors send no payment and return the request to `approved`.
- Evidence and model output are advisory, never payment authorization.

## Limitations

This is a hackathon MVP foundation, not production financial infrastructure. Before production use, add mature auth, migrations, rate limiting, abuse monitoring, PayPal webhook signature verification, provider reconciliation, distributed idempotency, and an independent security review. SQLite locking is suitable for local single-process development, not multi-instance deployment.
