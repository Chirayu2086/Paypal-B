from datetime import datetime, timezone
from decimal import Decimal
from fastapi import HTTPException
from backend.app.config import settings
from backend.app.security import cents_to_amount


def enforce_creation_limits(amount_cents: int) -> None:
    if amount_cents <= 0:
        raise HTTPException(status_code=422, detail="Amount must be positive")
    max_cents = int(Decimal(settings.max_transaction_amount) * 100)
    if amount_cents > max_cents:
        raise HTTPException(status_code=422, detail=f"Transaction exceeds per-transaction limit of {cents_to_amount(max_cents)} USD")


def enforce_daily_limit(conn, owner_id: str, proposed_cents: int) -> None:
    daily_limit_cents = int(Decimal(settings.daily_spend_limit) * 100)
    today = datetime.now(timezone.utc).date().isoformat()
    rows = conn.execute(
        "SELECT amount_cents FROM payment_intents WHERE owner_id = ? AND status IN ('approved','processing','succeeded') AND substr(created_at,1,10) = ?",
        (owner_id, today),
    ).fetchall()
    committed = sum(int(row[0]) for row in rows)
    if committed + proposed_cents > daily_limit_cents:
        raise HTTPException(status_code=422, detail=f"Daily spending limit of {cents_to_amount(daily_limit_cents)} USD would be exceeded")
