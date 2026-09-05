import stripe
from app.core.config import settings

stripe.api_key = settings.STRIPE_SECRET_KEY

async def create_payment_intent(amount_cents: int, metadata: dict) -> stripe.PaymentIntent:
    """建立 Stripe PaymentIntent，回傳給前端完成付款"""
    return stripe.PaymentIntent.create(
        amount=amount_cents,
        currency="cad",
        metadata=metadata,
        automatic_payment_methods={"enabled": True},
    )

async def refund_to_credit(payment_intent_id: str) -> None:
    """退款：直接退回信用卡（這裡我們不退卡，改存 credit，所以只是記錄用）"""
    # 實際上我們不呼叫 stripe.Refund，而是在 DB 加 credit
    # 若未來要退回信用卡再打開這段
    pass

def verify_webhook(payload: bytes, sig_header: str) -> stripe.Event:
    """驗證 Stripe webhook 簽名，防止偽造請求"""
    return stripe.Webhook.construct_event(
        payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
    )
