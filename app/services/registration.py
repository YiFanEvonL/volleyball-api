from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from uuid import UUID
from fastapi import HTTPException
from app.models.registration import Registration
from app.models.session import Session
from app.models.transaction import Transaction
from app.models.user import User
from app.services.stripe import create_payment_intent

async def register_for_session(
    session_id: UUID,
    user: User,
    db: AsyncSession,
) -> dict:
    """
    報名流程：
    1. 檢查時段存在且狀態為 open
    2. 檢查用戶未重複報名
    3. 檢查人數未達上限
    4. 建立 pending Registration
    5. 建立 Stripe PaymentIntent
    6. 回傳 client_secret 給前端
    """
    # 1. 取得時段
    session = await db.get(Session, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status != "open":
        raise HTTPException(status_code=400, detail="Session is not open for registration")

    # 2. 檢查是否已報名
    existing = await db.execute(
        select(Registration).where(
            Registration.user_id == user.id,
            Registration.session_id == session_id,
            Registration.status == "confirmed",
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Already registered")

    # 3. 計算目前確認人數
    count_result = await db.execute(
        select(func.count()).select_from(Registration).where(
            Registration.session_id == session_id,
            Registration.status == "confirmed",
        )
    )
    confirmed_count = count_result.scalar()
    if confirmed_count >= session.max_players:
        raise HTTPException(status_code=400, detail="Session is full, please join waitlist")

    # 4. 建立 pending Registration
    registration = Registration(
        user_id=user.id,
        session_id=session_id,
        status="pending",
    )
    db.add(registration)
    await db.flush()  # 取得 registration.id 但還不 commit

    # 5. 建立 Stripe PaymentIntent
    payment_intent = await create_payment_intent(
        amount_cents=session.fee_cents,
        metadata={
            "registration_id": str(registration.id),
            "user_id": str(user.id),
            "session_id": str(session_id),
        },
    )
    registration.stripe_payment_intent_id = payment_intent.id
    await db.commit()

    return {
        "registration_id": registration.id,
        "client_secret": payment_intent.client_secret,
        "amount_cents": session.fee_cents,
    }


async def confirm_registration(payment_intent_id: str, db: AsyncSession) -> None:
    """
    Stripe webhook 付款成功後呼叫：
    1. 找到對應的 pending Registration
    2. 改為 confirmed
    3. 寫入 Transaction
    4. 若人數達上限，將 Session 改為 full
    """
    # 1. 找 Registration
    result = await db.execute(
        select(Registration).where(
            Registration.stripe_payment_intent_id == payment_intent_id,
            Registration.status == "pending",
        )
    )
    registration = result.scalar_one_or_none()
    if not registration:
        return  # 可能已處理過，忽略

    # 2. 確認報名
    registration.status = "confirmed"

    # 3. 寫入交易紀錄
    session = await db.get(Session, registration.session_id)
    transaction = Transaction(
        user_id=registration.user_id,
        registration_id=registration.id,
        type="payment",
        amount_cents=session.fee_cents,
        stripe_id=payment_intent_id,
    )
    db.add(transaction)

    # 4. 檢查是否達到人數上限
    count_result = await db.execute(
        select(func.count()).select_from(Registration).where(
            Registration.session_id == registration.session_id,
            Registration.status == "confirmed",
        )
    )
    confirmed_count = count_result.scalar()
    if confirmed_count >= session.max_players:
        session.status = "full"

    await db.commit()
