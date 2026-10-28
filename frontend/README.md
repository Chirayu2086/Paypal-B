# Proxy Operator Dashboard

Next.js dashboard for the Proxy safety-first payment API.

## Requirements

- Node.js 20.9+
- FastAPI backend running locally or at a trusted HTTPS API origin
- JWT issued by a trusted identity provider (claims must include `sub` and `exp`)
- Optional backend AI provider key to enable natural-language draft extraction

## Run locally

From this directory:

```bash
npm install
npm run dev
```

Open http://localhost:3000. The API defaults to `http://localhost:8000`; override it with `NEXT_PUBLIC_PROXY_API_URL` if needed.

The backend expects authenticated requests on `/v1/*`. Paste a valid bearer token into the connection panel. The token is kept only in in-memory React state and is not written to localStorage or cookies. Do not paste PayPal credentials or secrets. Configure backend CORS to allow the frontend origin.

## AI draft flow

Set `AI_API_KEY`, and optionally `AI_BASE_URL` and `AI_MODEL`, in the backend environment. The default endpoint is OpenAI-compatible. The key stays on the backend and is never sent to the browser.

The natural-language draft endpoint extracts explicitly stated fields and returns missing fields and warnings. It does not create an intent, approve a payment, or call PayPal. Review and correct every field before manually creating an intent. User text is sent to the configured AI provider; do not submit information you are not permitted to share with that provider.

## Current capabilities

- Create a structured payment intent.
- Draft recipient, amount, purpose, and context from a natural-language request.
- Review recipient, amount, purpose, context, and approval fingerprint.
- Approve the exact intent snapshot.
- Request execution separately from approval.
- Reconcile an ambiguous outcome against the existing payout batch.
- View payment intents and authenticated audit events.
- Display API liveness separately from payment settlement status.

## Honest limitations

- AI extraction can make mistakes and requires manual review.
- Context is user-provided text, not independently verified evidence.
- Authentication is supplied externally; there is no demo login.
- The UI only supports the backend's current USD schema.
- PayPal Sandbox configuration and a real Sandbox end-to-end validation are still required.
- Before production: add mature auth integration, CSRF/CSP and deployment review, rate limiting, webhook verification, observability, and independent security assessment.
