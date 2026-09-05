from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from uuid import UUID
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException

from app.models.registration import Registration
from app.models.waitlist import WaitlistEntry
from app.models.session import Session
from app.models.user import User
from app.models.transaction import Transaction
from app.services.notification import notify_waitlist_spot_available
from app.services.stripe import create_payment_intent


async def join_waitlist(session_id: UUID, user: User, db: AsyncSession) -> WaitlistEntry:
    """
    Add a player to the waitlist for a full session.
    Assigns the next available position.
    """
    session = await db.get(Session, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status not in ("full",):
        raise HTTPException(status_code=400, detail="Session is not full — register directly instead")

    # Check player isn't already on the waitlist
    existing = await db.execute(
        select(WaitlistEntry).where(
            WaitlistEntry.user_id == user.id,
            WaitlistEntry.session_id == session_id,
            WaitlistEntry.status == "waiting",
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Already on the waitlist")

    # Get next position
    pos_result = await db.execute(
        select(func.coalesce(func.max(WaitlistEntry.position), 0)).where(
            WaitlistEntry.session_id == session_id,
            WaitlistEntry.status.in_(["waiting", "notified"]),
        )
    )
    next_position = pos_result.scalar() + 1

    entry = WaitlistEntry(
        user_id=user.id,
        session_id=session_id,
        position=next_position,
        status="waiting",
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


async def cancel_registration(registration_id: UUID, user: User, db: AsyncSession) -> None:
    """
    Cancel a confirmed registration:
    1. Mark registration as cancelled
    2. Add fee to user's credit balance
    3. Record a credit_add transaction
    4. Reopen session status to 'open'
    5. Notify the first waiting player on the waitlist
    """
    # 1. Fetch and validate registration
    registration = await db.get(Registration, registration_id)
    if not registration:
        raise HTTPException(status_code=404, detail="Registration not found")
    if registration.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not your registration")
    if registration.status != "confirmed":
        raise HTTPException(status_code=400, detail="Registration is not active")

    session = await db.get(Session, registration.session_id)

    # 2. Mark as cancelled
    registration.status = "cancelled"

    # 3. Credit the fee back to user's balance
    user.credit_balance += session.fee_cents

    # 4. Record transaction
    transaction = Transaction(
        user_id=user.id,
        registration_id=registration.id,
        type="credit_add",
        amount_cents=session.fee_cents,
    )
    db.add(transaction)

    # 5. Reopen session
    session.status = "open"

    await db.commit()

    # 6. Notify first waitlisted player
    await _notify_next_in_waitlist(session, db)


async def _notify_next_in_waitlist(session: Session, db: AsyncSession) -> None:
    """Find the first waiting player and send them a push notification."""
    result = await db.execute(
        select(WaitlistEntry)
        .where(
            WaitlistEntry.session_id == session.id,
            WaitlistEntry.status == "waiting",
        )
        .order_by(WaitlistEntry.position)
        .limit(1)
    )
    entry = result.scalar_one_or_none()
    if not entry:
        return  # No one waiting, nothing to do

    # Mark as notified and set 2-hour expiry
    entry.status = "notified"
    entry.notified_at = datetime.now(timezone.utc)
    entry.expires_at = datetime.now(timezone.utc) + timedelta(hours=2)
    await db.commit()

    # Send push notification
    user = await db.get(User, entry.user_id)
    session_date = session.date.strftime("%a, %b %d")

    # expo_push_token will be added to User model in a later step
    if hasattr(user, "expo_push_token") and user.expo_push_token:
        await notify_waitlist_spot_available(
            expo_token=user.expo_push_token,
            session_date=session_date,
            session_location=session.location,
            waitlist_id=entry.id,
        )


async def claim_waitlist_spot(waitlist_id: UUID, user: User, db: AsyncSession) -> dict:
    """
    Called when a notified waitlist player taps 'Claim Spot':
    1. Validate entry is theirs, notified, and not expired
    2. Deduct fee: use credit balance first, charge Stripe for remainder
    3. Create a new confirmed Registration
    4. Mark waitlist entry as converted
    5. Check if session is full again
    """
    entry = await db.get(WaitlistEntry, waitlist_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Waitlist entry not found")
    if entry.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not your waitlist entry")
    if entry.status != "notified":
        raise HTTPException(status_code=400, detail="Spot is no longer available")
    if datetime.now(timezone.utc) > entry.expires_at:
        # Expired — mark it and notify the next person
        entry.status = "expired"
        await db.commit()
        session = await db.get(Session, entry.session_id)
        await _notify_next_in_waitlist(session, db)
        raise HTTPException(status_code=400, detail="Your claim window has expired")

    session = await db.get(Session, entry.session_id)
    fee = session.fee_cents

    # 2a. Use credit balance first
    credit_used = min(user.credit_balance, fee)
    stripe_amount = fee - credit_used

    client_secret = None

    if credit_used > 0:
        user.credit_balance -= credit_used
        db.add(Transaction(
            user_id=user.id,
            type="credit_use",
            amount_cents=credit_used,
        ))

    # 2b. Charge remaining via Stripe if needed
    if stripe_amount > 0:
        payment_intent = await create_payment_intent(
            amount_cents=stripe_amount,
            metadata={
                "waitlist_id": str(waitlist_id),
                "user_id": str(user.id),
                "session_id": str(entry.session_id),
            },
        )
        client_secret = payment_intent.client_secret
        # Registration will be confirmed by webhook after payment
        entry.status = "converted"
        await db.commit()
        return {"requires_payment": True, "client_secret": client_secret, "amount_cents": stripe_amount}

    # Fully covered by credit — confirm immediately
    registration = Registration(
        user_id=user.id,
        session_id=entry.session_id,
        status="confirmed",
    )
    db.add(registration)
    entry.status = "converted"

    # Check if session is now full again
    count_result = await db.execute(
        select(func.count()).select_from(Registration).where(
            Registration.session_id == session.id,
            Registration.status == "confirmed",
        )
    )
    if count_result.scalar() >= session.max_players:
        session.status = "full"

    await db.commit()
    return {"requires_payment": False, "registration_id": str(registration.id)}
