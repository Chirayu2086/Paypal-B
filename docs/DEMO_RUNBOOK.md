# Proxy Demo Runbook

This runbook is for a controlled hackathon demonstration. Use PayPal Sandbox only. Do not use live credentials or real recipients/funds.

## Demo narrative (4–6 minutes)

1. **Safety first:** show that the dashboard requires an externally issued bearer JWT and that no demo-login endpoint exists.
2. **AI proposal:** enter a natural-language payment request. Explain that the model returns a draft with missing fields and advisory risk flags; it does not create, approve, or execute a payment.
3. **Evidence triage:** submit a claim with evidence labels/URLs/notes. Show the completeness and URL-hygiene observations. State explicitly that Proxy does not fetch these URLs or verify source authenticity or claim truth.
4. **Human approval:** create/review a payment intent and show the exact approval fingerprint. Attempting execution before approval should be rejected.
5. **Sandbox execution:** approve the immutable request snapshot, then execute only when PayPal Sandbox is configured and the operator is ready.
6. **Ambiguous outcome recovery:** explain that an uncertain provider response stays `processing`; reconcile the stored batch instead of blindly submitting another payout.
7. **Auditability:** show the authenticated activity feed and the final provider transaction identifier only when PayPal returns a verified successful terminal result.

## Local setup

Prerequisites: Python 3.11+, Node.js 20.9+, a valid JWT from a trusted identity provider, and optional PayPal Sandbox credentials with Payouts enabled.

1. Copy the root `.env.example` to `backend/.env` only if that matches your local config setup; otherwise configure the backend environment variables in your shell. Set a strong `JWT_SECRET`, `PAYPAL_MODE=sandbox`, and exact `CORS_ALLOWED_ORIGINS=http://localhost:3000`.
2. From the repository root, install backend dependencies and start the API:
   ```bash
   python -m venv .venv
   # Windows: .venv\\Scripts\\activate
   # macOS/Linux: source .venv/bin/activate
   pip install -r requirements.txt
   uvicorn backend.app.main:app --reload
   ```
3. In a second terminal:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
4. Open `http://localhost:3000`, configure the API origin if needed with `NEXT_PUBLIC_PROXY_API_URL=http://localhost:8000`, and provide the externally issued JWT in the connection panel.
5. Confirm `GET http://localhost:8000/health` reports API liveness. This does **not** prove PayPal is configured or that any payment settled.

Never paste PayPal client secrets into the browser. Keep `PAYPAL_CLIENT_SECRET` backend-only and do not commit `.env` files.

## Automated checks

From the repository root:

```bash
python -m pytest -q
```

Frontend build check:

```bash
cd frontend
npm ci
npm run build
```

The automated payment tests use fake providers and synthetic transaction IDs. They do not contact PayPal or move money. A real Sandbox end-to-end check is a separate manual acceptance step and has not been claimed by these tests.

## Acceptance checklist

- [ ] Backend test workflow passes on the final PR head.
- [ ] Frontend build workflow passes on the final PR head.
- [ ] JWT authentication works with the intended identity provider.
- [ ] CORS is restricted to the exact dashboard origin.
- [ ] AI proposal and evidence triage do not create payment intents or trigger provider calls.
- [ ] Execution is blocked before explicit approval and with a mismatched fingerprint.
- [ ] Sandbox payout is only called after approval.
- [ ] Verified success requires an item-level terminal success and transaction ID.
- [ ] An ambiguous result preserves `processing` and the known batch ID.
- [ ] Reconciliation reads the existing batch and never calls payout creation.
- [ ] Audit feed reflects approval, execution outcome, and reconciliation.
- [ ] No secrets are committed; demo uses Sandbox only.
- [ ] Real Sandbox payout flow is manually validated, or clearly disclosed as not yet validated.

## Known limitations

- Evidence triage is not evidence verification, fraud detection, or a payment decision.
- AI proposal output is untrusted input and requires human review.
- Authentication is externally supplied; there is no first-party sign-in flow.
- Reconciliation is owner-triggered, not a scheduled worker or webhook-driven process.
- SQLite is intended for a local/single-process MVP, not horizontally scaled production.
- Production use requires independent security review, monitoring, rate limiting, webhook signature verification, robust identity integration, operational recovery procedures, and deployment hardening.
