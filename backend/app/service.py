from datetime import datetime, timezone
from uuid import uuid4
from fastapi import HTTPException
from backend.app.database import connect
from backend.app.policy import enforce_creation_limits, enforce_daily_limit
from backend.app.schemas import PaymentIntentCreate
from backend.app.security import amount_to_cents, cents_to_amount, fingerprint
from backend.app.payments import PaymentProvider, PaymentProviderNotConfigured, PaymentProviderError


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def serialize_intent(row) -> dict:
    return {
        "id": row["id"], "owner_id": row["owner_id"], "recipient_name": row["recipient_name"],
        "recipient_email": row["recipient_email"], "amount": cents_to_amount(row["amount_cents"]),
        "currency": row["currency"], "purpose": row["purpose"], "condition_summary": row["condition_summary"],
        "approval_fingerprint": row["request_fingerprint"], "status": row["status"], "created_at": row["created_at"], "approved_at": row["approved_at"],
        "executed_at": row["executed_at"], "provider_transaction_id": row["provider_transaction_id"],
        "failure_code": row["failure_code"], "provider_payout_batch_id": row["provider_payout_batch_id"],
    }


def audit(conn, intent_id: str, event_type: str, actor_id: str | None, details: str) -> None:
    conn.execute("INSERT INTO audit_events(payment_intent_id,event_type,actor_id,details,created_at) VALUES(?,?,?,?,?)",
                 (intent_id, event_type, actor_id, details[:1000], now_iso()))


def create_intent(owner_id: str, payload: PaymentIntentCreate) -> dict:
    cents = amount_to_cents(payload.amount)
    enforce_creation_limits(cents)
    intent_id = str(uuid4())
    created = now_iso()
    request_data = {
        "owner_id": owner_id, "recipient_name": payload.recipient_name,
        "recipient_email": payload.recipient_email.lower(), "amount_cents": cents,
        "currency": payload.currency, "purpose": payload.purpose,
        "condition_summary": payload.condition_summary,
    }
    fp = fingerprint(request_data)
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        enforce_daily_limit(conn, owner_id, cents)
        conn.execute(
            "INSERT INTO payment_intents(id,owner_id,recipient_name,recipient_email,amount_cents,currency,purpose,condition_summary,status,request_fingerprint,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (intent_id, owner_id, payload.recipient_name, payload.recipient_email.lower(), cents, payload.currency,
             payload.purpose, payload.condition_summary, "pending_approval", fp, created),
        )
        audit(conn, intent_id, "payment_intent.created", owner_id, "Created; awaiting explicit human approval")
        row = conn.execute("SELECT * FROM payment_intents WHERE id=?", (intent_id,)).fetchone()
        conn.commit()
    return serialize_intent(row)


def get_owned_intent(owner_id: str, intent_id: str) -> dict:
    with connect() as conn:
        row = conn.execute("SELECT * FROM payment_intents WHERE id=? AND owner_id=?", (intent_id, owner_id)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Payment intent not found")
    return serialize_intent(row)


def approve_intent(owner_id: str, intent_id: str, confirm_fingerprint: str) -> dict:
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM payment_intents WHERE id=? AND owner_id=?", (intent_id, owner_id)).fetchone()
        if row is None:
            conn.rollback()
            raise HTTPException(status_code=404, detail="Payment intent not found")
        if row["status"] != "pending_approval":
            conn.rollback()
            raise HTTPException(status_code=409, detail=f"Cannot approve payment in state '{row['status']}'")
        if confirm_fingerprint != row["request_fingerprint"]:
            conn.rollback()
            raise HTTPException(status_code=409, detail="Payment details changed or confirmation fingerprint is invalid; review the request again")
        enforce_daily_limit(conn, owner_id, int(row["amount_cents"]))
        approved = now_iso()
        conn.execute("UPDATE payment_intents SET status='approved', approved_at=?, idempotency_key=? WHERE id=? AND status='pending_approval'",
                     (approved, f"proxy-{intent_id.replace('-', '')}", intent_id))
        audit(conn, intent_id, "payment_intent.approved", owner_id, "Owner explicitly approved the current immutable request snapshot")
        updated = conn.execute("SELECT * FROM payment_intents WHERE id=?", (intent_id,)).fetchone()
        conn.commit()
    return serialize_intent(updated)


def execute_intent(owner_id: str, intent_id: str, provider: PaymentProvider | None = None) -> dict:
    provider = provider or PaymentProvider()
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM payment_intents WHERE id=? AND owner_id=?", (intent_id, owner_id)).fetchone()
        if row is None:
            conn.rollback()
            raise HTTPException(status_code=404, detail="Payment intent not found")
        if row["status"] != "approved":
            conn.rollback()
            raise HTTPException(status_code=409, detail="Explicit approval is required before execution; request must be in approved state")
        # Reserve the state before making an external call so concurrent calls cannot both execute.
        conn.execute("UPDATE payment_intents SET status='processing' WHERE id=? AND status='approved'", (intent_id,))
        audit(conn, intent_id, "payment.execution_started", owner_id, "Execution reserved; provider result pending")
        conn.commit()
        recipient_email, amount_cents, currency, idempotency_key = row["recipient_email"], int(row["amount_cents"]), row["currency"], row["idempotency_key"]
    try:
        result = provider.execute_payout(recipient_email=recipient_email, amount_cents=amount_cents, currency=currency, idempotency_key=idempotency_key)
        if not result.transaction_id or result.status.lower() not in {"success", "succeeded", "completed"}:
            raise RuntimeError("Provider did not confirm a successful payout")
    except PaymentProviderNotConfigured:
        with connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("UPDATE payment_intents SET status='approved', failure_code='provider_not_configured' WHERE id=? AND status='processing'", (intent_id,))
            audit(conn, intent_id, "payment.execution_blocked", owner_id, "Provider not configured; no payment was sent")
            row = conn.execute("SELECT * FROM payment_intents WHERE id=?", (intent_id,)).fetchone()
            conn.commit()
        raise HTTPException(status_code=503, detail="PayPal Sandbox adapter is not configured; no payment was sent")
    except Exception as exc:
        with connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            batch_id = getattr(exc, "payout_batch_id", None)
            conn.execute("UPDATE payment_intents SET failure_code='provider_outcome_unknown', provider_payout_batch_id=COALESCE(?, provider_payout_batch_id) WHERE id=? AND status='processing'", (batch_id, intent_id))
            audit(conn, intent_id, "payment.execution_outcome_unknown", owner_id, "Provider call failed without a definitive outcome; left in processing to prevent duplicate payout. Reconcile with PayPal before any retry.")
            conn.commit()
        raise HTTPException(status_code=502, detail="Payment provider did not confirm success; check provider status before retrying") from None
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("UPDATE payment_intents SET status='succeeded', executed_at=?, provider_transaction_id=?, provider_payout_batch_id=COALESCE(?, provider_payout_batch_id), failure_code=NULL WHERE id=? AND status='processing'",
                     (now_iso(), result.transaction_id, getattr(result, 'payout_batch_id', None), intent_id))
        audit(conn, intent_id, "payment.execution_succeeded", owner_id, f"Provider-confirmed status={result.status}; transaction_id={result.transaction_id}")
        row = conn.execute("SELECT * FROM payment_intents WHERE id=?", (intent_id,)).fetchone()
        conn.commit()
    return serialize_intent(row)



def reconcile_intent(owner_id: str, intent_id: str, provider: PaymentProvider | None = None) -> dict:
    """Re-check a known PayPal batch. This path must never create or retry a payout."""
    provider = provider or PaymentProvider()
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT * FROM payment_intents WHERE id=? AND owner_id=?",
            (intent_id, owner_id),
        ).fetchone()
        if row is None:
            conn.rollback()
            raise HTTPException(status_code=404, detail="Payment intent not found")
        if row["status"] != "processing":
            conn.rollback()
            raise HTTPException(status_code=409, detail="Only processing intents can be reconciled")
        batch_id = row["provider_payout_batch_id"]
        idempotency_key = row["idempotency_key"]
        if not batch_id:
            conn.rollback()
            raise HTTPException(
                status_code=409,
                detail="No PayPal batch ID was captured. The outcome remains unknown; do not retry automatically.",
            )
        conn.commit()

    try:
        result = provider.reconcile_payout(
            payout_batch_id=batch_id,
            idempotency_key=idempotency_key,
        )
    except PaymentProviderNotConfigured:
        raise HTTPException(status_code=503, detail="PayPal Sandbox adapter is not configured") from None
    except Exception as exc:
        with connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "UPDATE payment_intents SET failure_code='provider_outcome_unknown' WHERE id=? AND status='processing'",
                (intent_id,),
            )
            audit(
                conn, intent_id, "payment.reconciliation_unresolved", owner_id,
                f"Reconciliation did not confirm settlement: {type(exc).__name__}. Intent remains processing; no new payout submitted.",
            )
            row = conn.execute("SELECT * FROM payment_intents WHERE id=?", (intent_id,)).fetchone()
            conn.commit()
        return serialize_intent(row)

    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "UPDATE payment_intents SET status='succeeded', executed_at=?, provider_transaction_id=?, failure_code=NULL WHERE id=? AND status='processing'",
            (now_iso(), result.transaction_id, intent_id),
        )
        audit(
            conn, intent_id, "payment.reconciliation_succeeded", owner_id,
            f"Existing PayPal batch reconciled to SUCCESS; transaction_id={result.transaction_id}",
        )
        row = conn.execute("SELECT * FROM payment_intents WHERE id=?", (intent_id,)).fetchone()
        conn.commit()
    return serialize_intent(row)


def list_activity(owner_id: str, limit: int = 50) -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT e.id,e.payment_intent_id,e.event_type,e.actor_id,e.details,e.created_at FROM audit_events e JOIN payment_intents p ON p.id=e.payment_intent_id WHERE p.owner_id=? ORDER BY e.id DESC LIMIT ?", (owner_id, min(max(limit, 1), 100))).fetchall()
    return [dict(row) for row in rows]
