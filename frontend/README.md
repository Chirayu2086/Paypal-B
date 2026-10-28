# Proxy Operator Dashboard

Next.js dashboard for the Proxy safety-first payment API.

## Requirements

- Node.js 20.9+
- The FastAPI backend running locally or at a trusted HTTPS API origin
- A JWT issued by the configured trusted identity provider (claims must include `sub` and `exp`)

## Run locally

From this directory:

```bash
npm install
npm run dev
```

Open http://localhost:3000. The API defaults to `http://localhost:8000`; override it with `NEXT_PUBLIC_PROXY_API_URL` if needed.

The backend expects authenticated requests on `/v1/*`. Paste a valid bearer token into the connection panel. The token is kept only in in-memory React state and is not written to localStorage or cookies. Do not paste PayPal credentials or secrets. Configure CORS on the backend to allow the frontend origin before using a separate frontend port.

## Current capabilities

- Create a structured payment intent.
- Review recipient, amount, purpose, supporting context, and approval fingerprint.
- Approve the exact intent snapshot.
- Request execution separately from approval.
- Reconcile an ambiguous outcome against the existing payout batch.
- View payment intents and authenticated audit events.
- Display API liveness separately from payment settlement status.

## Honest limitations

- This is an operator dashboard, not an AI chat or autonomous agent yet. Payment creation is a structured form; AI intent extraction and evidence analysis are not implemented in this UI.
- The current API does not expose a list endpoint for payment intents. The dashboard shows the currently selected intent and authenticated audit feed; the table will populate only if the backend later adds a list route. The UI handles an unavailable list route without treating it as a payment failure.
- Authentication is supplied externally; there is no demo login.
- The UI only supports the backend's current USD schema.
- PayPal Sandbox configuration and a real Sandbox end-to-end validation are still required. A healthy API does not mean PayPal is configured or a payout settled.
- Before production: add mature auth integration, CSRF/CSP and deployment review, backend CORS allowlist, rate limiting, webhook verification, observability, and an independent security assessment.
