# Proxy

**Your AI agent that can actually move money — with a human in control.**

Proxy is a human-approved AI payment assistant being built for the Build What's Next with PayPal and AI Hackathon 2026. The current MVP lets a user create a structured payment intent, enforce server-side spending limits, explicitly approve an immutable request snapshot, execute through PayPal Sandbox, and reconcile ambiguous provider outcomes without submitting a duplicate payout.

## What exists today

- FastAPI backend with JWT-authenticated, owner-scoped payment routes.
- Server-side per-transaction and daily spend limits.
- Approval fingerprint binds approval to the exact stored payment details.
- PayPal Sandbox payout adapter with idempotency, bounded status polling, and read-only reconciliation.
- Audit feed and automated backend tests.
- Next.js operator dashboard for creating intents, reviewing and approving them, requesting execution, reconciling uncertain outcomes, and viewing the audit trail.
- AI-assisted natural-language proposal extraction with locally validated structured output, missing-field detection, and advisory risk flags.
- Deterministic evidence triage that checks submission completeness and basic URL hygiene while explicitly leaving every claim and source unverified.
- Dashboard evidence-review panel for entering a claim, adding up to 10 evidence references/notes, and reviewing triage flags and manual next steps.

## Stack

- Frontend: Next.js + TypeScript + CSS
- Backend: Python + FastAPI
- Persistence: SQLite MVP
- Payments: PayPal Sandbox Payouts
- Authentication: externally issued signed JWT; no insecure demo-login endpoint

## Run locally

1. Start the backend using [backend/README.md](backend/README.md).
2. Start the dashboard using [frontend/README.md](frontend/README.md).
3. Configure `CORS_ALLOWED_ORIGINS` in the backend environment to the exact trusted frontend origin.
4. Supply a JWT from the configured trusted identity provider in the dashboard connection panel.
5. Follow the [Hackathon Demo Runbook](docs/DEMO_RUNBOOK.md) for a timed demo, acceptance checklist, and known limitations.

## Safety boundary

A created intent is not an approved payment. Approval is a separate action, execution is another action, and only a provider-verified transaction ID with a successful terminal status is represented as settled. Unknown outcomes remain in `processing` and should be reconciled against the existing provider batch rather than retried blindly.

The evidence-review endpoint does not fetch sources or verify truth. Its output is triage guidance only and must not be treated as an automated approve/deny decision. See [AI agent safety boundaries](docs/AI_AGENT.md) and [Evidence review limitations](docs/EVIDENCE_REVIEW.md).

## Not yet implemented / validated

- Independent evidence verification and automated source-content analysis.
- First-party authentication provider integration.
- Real PayPal Sandbox end-to-end transaction validation.
- Deployment, production-grade monitoring, webhook signature verification, and independent security review.

This is a hackathon MVP, not production financial infrastructure. Use Sandbox credentials only. Never commit secrets or use live payment credentials.
