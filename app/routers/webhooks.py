from fastapi import APIRouter, Request, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import AsyncSessionLocal
from app.services.stripe import verify_webhook
from app.services.registration import confirm_registration
import stripe

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None),
):
    payload = await request.body()

    # 驗證簽名（防止偽造請求）
    try:
        event = verify_webhook(payload, stripe_signature)
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    # 處理付款成功事件
    if event["type"] == "payment_intent.succeeded":
        payment_intent_id = event["data"]["object"]["id"]
        async with AsyncSessionLocal() as db:
            await confirm_registration(payment_intent_id, db)

    # 其他事件（payment_intent.payment_failed 等）之後再加
    return {"status": "ok"}
