from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from backend.app.config import settings, validate_runtime_config
from backend.app.database import init_db
from backend.app.schemas import ActivityEvent, ApprovalRequest, PaymentIntentCreate, PaymentIntentOut
from backend.app.security import current_user
from backend.app.service import approve_intent, create_intent, execute_intent, get_owned_intent, list_activity, list_owned_intents, reconcile_intent


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_runtime_config()
    init_db()
    yield


app = FastAPI(title="Proxy API", version="0.1.0", description="Safety-first AI payment agent API", lifespan=lifespan)
allowed_origins = [origin.strip() for origin in settings.cors_allowed_origins.split(",") if origin.strip()]
if allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )


@app.get("/health")
def health():
    return {"status": "ok", "environment": settings.app_env, "payments": "sandbox_only"}


@app.post("/v1/payment-intents", response_model=PaymentIntentOut, status_code=201)
def create_payment_intent(payload: PaymentIntentCreate, user_id: str = Depends(current_user)):
    return create_intent(user_id, payload)


@app.get("/v1/payment-intents", response_model=list[PaymentIntentOut])
def list_payment_intents(limit: int = Query(default=50, ge=1, le=100), user_id: str = Depends(current_user)):
    return list_owned_intents(user_id, limit)


@app.get("/v1/payment-intents/{intent_id}", response_model=PaymentIntentOut)
def read_payment_intent(intent_id: str, user_id: str = Depends(current_user)):
    return get_owned_intent(user_id, intent_id)


@app.post("/v1/payment-intents/{intent_id}/approve", response_model=PaymentIntentOut)
def approve_payment_intent(intent_id: str, payload: ApprovalRequest, user_id: str = Depends(current_user)):
    return approve_intent(user_id, intent_id, payload.confirm_fingerprint)


@app.post("/v1/payment-intents/{intent_id}/execute", response_model=PaymentIntentOut)
def execute_payment_intent(intent_id: str, user_id: str = Depends(current_user)):
    return execute_intent(user_id, intent_id)


@app.post("/v1/payment-intents/{intent_id}/reconcile", response_model=PaymentIntentOut)
def reconcile_payment_intent(intent_id: str, user_id: str = Depends(current_user)):
    """Re-check provider status only; this endpoint never creates a payout."""
    return reconcile_intent(user_id, intent_id)


@app.get("/v1/activity", response_model=list[ActivityEvent])
def activity(limit: int = Query(default=50, ge=1, le=100), user_id: str = Depends(current_user)):
    return list_activity(user_id, limit)
