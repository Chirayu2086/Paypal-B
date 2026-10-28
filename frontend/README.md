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

- Create and list the authenticated user's payment intents.
- Use AI-assisted natural-language extraction to draft a payment proposal, inspect missing fields and advisory risk flags, and transfer the draft to the payment form for manual review.
- Run evidence triage for a claim with up to 10 evidence references/notes; inspect completeness and URL-hygiene observations and suggested manual checks.
- Review recipient, amount, purpose, supporting context, and the immutable approval fingerprint.
- Approve the exact intent snapshot and request execution as a separate action.
- Reconcile an ambiguous outcome against the existing payout batch without submitting a new payout.
- View the authenticated audit feed and distinguish API liveness from payment settlement status.

## Safety and limitations

- AI proposals are drafts only. They do not create, approve, or execute payment intents automatically.
- Evidence triage does not fetch submitted URLs, verify source authenticity, establish claim truth, or produce a calibrated fraud score. Its result is advisory and requires human review.
- Authentication is supplied externally; there is no demo login or first-party sign-in flow.
- The UI supports the backend's current USD schema.
- PayPal Sandbox configuration and a real Sandbox end-to-end validation are still required. A healthy API does not mean PayPal is configured or a payout settled.
- The token is kept in in-memory React state, not localStorage or cookies. Do not paste PayPal credentials or secrets into the browser.
- Before production: add mature auth integration, CSP/CSRF and deployment review, rate limiting, webhook verification, observability, robust operational recovery, and an independent security assessment.

See the [Demo Runbook](../docs/DEMO_RUNBOOK.md) for the end-to-end presentation sequence and acceptance checklist.
