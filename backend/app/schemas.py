from datetime import datetime
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


Currency = Literal["USD"]


class PaymentIntentCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    recipient_name: str = Field(min_length=1, max_length=120)
    recipient_email: str = Field(min_length=3, max_length=254)
    amount: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    currency: Currency = "USD"
    purpose: str = Field(min_length=3, max_length=500)
    condition_summary: str | None = Field(default=None, max_length=1000)

    @field_validator("amount")
    @classmethod
    def amount_must_be_finite(cls, value: Decimal) -> Decimal:
        if not value.is_finite():
            raise ValueError("amount must be finite")
        return value


class PaymentIntentOut(BaseModel):
    id: str
    owner_id: str
    recipient_name: str
    recipient_email: str
    amount: str
    currency: str
    purpose: str
    condition_summary: str | None
    status: str
    created_at: datetime
    approved_at: datetime | None
    executed_at: datetime | None
    provider_transaction_id: str | None
    failure_code: str | None


class ApprovalRequest(BaseModel):
    confirm_fingerprint: str = Field(min_length=64, max_length=64)


class ActivityEvent(BaseModel):
    id: int
    payment_intent_id: str
    event_type: str
    actor_id: str | None
    details: str
    created_at: datetime
