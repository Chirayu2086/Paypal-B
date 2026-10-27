# Proxy

**Your AI agent that can actually move money.**

Proxy is a human-approved AI payment assistant built for the Build What's Next with PayPal and AI Hackathon 2026. The MVP turns natural-language requests into structured payment intents, enforces server-side spending limits, requires explicit user approval, and uses PayPal Sandbox for payment execution.

## Safety-first MVP

- Server-side policy enforcement; the model cannot override limits.
- Explicit approval bound to an immutable payment-intent snapshot.
- Idempotency and duplicate-execution protection.
- Evidence analysis is advisory and never authorizes a payment.
- Sandbox-only payment execution until separately reviewed.
- Auditable state transitions and payment-provider outcomes.

## Planned stack

- Frontend: Next.js + TypeScript + Tailwind CSS
- Backend: Python + FastAPI
- Persistence: SQLite for the MVP, with PostgreSQL migration path
- Payments: PayPal Sandbox APIs, selected by transaction type
- AI: provider-agnostic agent adapter with validated structured tools

## Project status

The security foundation is being built first. A UI or an AI-generated recommendation is not proof that a payment was executed; the activity feed must show provider-verified status and transaction identifiers.

## Local development

See `backend/README.md` for backend setup once the first implementation phase is complete. Never commit API keys or real payment credentials. Copy `.env.example` to `.env` and use Sandbox credentials only.
