# Proxy

**Your AI agent that can actually move money — with a human in control.**

Proxy is a human-approved AI payment assistant being built for the Build What's Next with PayPal and AI Hackathon 2026. It turns natural-language payment requests into reviewable drafts, enforces server-side spending limits, requires explicit approval, and uses PayPal Sandbox for payment execution.

## What exists today

- FastAPI backend with JWT-authenticated, owner-scoped payment routes.
- Optional AI-assisted natural-language extraction into a structured draft, with missing-field reporting and explicit warnings.
- Server-side per-transaction and daily spend limits.
- Approval fingerprint binds approval to the exact stored payment details.
- PayPal Sandbox payout adapter with idempotency, bounded status polling, and read-only reconciliation.
- Next.js operator dashboard for drafting, reviewing, approving, executing, reconciling, and viewing audit activity.
- Automated backend and frontend CI workflows.

## Stack

- Frontend: Next.js + TypeScript + CSS
- Backend: Python + FastAPI
- Persistence: SQLite MVP
- AI: configurable OpenAI-compatible chat completions endpoint
- Payments: PayPal Sandbox Payouts
- Authentication: externally issued signed JWT; no insecure demo-login endpoint

## Run locally

1. Start the backend using [backend/README.md](backend/README.md).
2. Start the dashboard using [frontend/README.md](frontend/README.md).
3. Configure `CORS_ALLOWED_ORIGINS` for the frontend origin.
4. Add a trusted JWT in the dashboard connection panel.
5. Optionally set `AI_API_KEY`, `AI_BASE_URL`, and `AI_MODEL` on the backend to enable natural-language drafts.

## Safety boundary

AI extracts a proposal only. It never creates, approves, or executes a payment. Review every extracted field, then create the intent manually. Approval and execution are separate user actions. Only a provider-verified transaction ID with a successful terminal status is represented as settled. Unknown outcomes remain in `processing` and should be reconciled against the existing provider batch rather than retried blindly.

## Not yet implemented / validated

- Independent evidence verification and invoice/document analysis.
- First-party authentication provider integration.
- Real PayPal Sandbox end-to-end transaction validation.
- Deployment, production-grade monitoring, webhook signature verification, and independent security review.

This is a hackathon MVP, not production financial infrastructure. Use Sandbox credentials only. Never commit secrets or use live payment credentials.
