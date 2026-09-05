from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.registration import Registration
from app.models.transaction import Transaction
from app.models.session import Session
from app.schemas.user import UserResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Return the current user's profile and credit balance."""
    return UserResponse.model_validate(current_user)


@router.get("/me/registrations")
async def get_my_registrations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return all of the current user's registrations with session details."""
    result = await db.execute(
        select(Registration, Session)
        .join(Session, Registration.session_id == Session.id)
        .where(Registration.user_id == current_user.id)
        .order_by(Session.date.desc())
    )
    rows = result.all()
    return [
        {
            "registration_id": reg.id,
            "status": reg.status,
            "registered_at": reg.registered_at,
            "session": {
                "id": session.id,
                "location": session.location,
                "date": session.date,
                "start_time": session.start_time,
                "fee_cents": session.fee_cents,
                "status": session.status,
            },
        }
        for reg, session in rows
    ]


@router.get("/me/transactions")
async def get_my_transactions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the current user's full transaction history."""
    result = await db.execute(
        select(Transaction)
        .where(Transaction.user_id == current_user.id)
        .order_by(Transaction.created_at.desc())
    )
    transactions = result.scalars().all()
    return [
        {
            "id": t.id,
            "type": t.type,
            "amount_cents": t.amount_cents,
            "stripe_id": t.stripe_id,
            "created_at": t.created_at,
        }
        for t in transactions
    ]
