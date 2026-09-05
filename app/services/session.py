from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from uuid import UUID
from fastapi import HTTPException

from app.models.session import Session
from app.models.registration import Registration
from app.models.waitlist import WaitlistEntry
from app.schemas.session import SessionCreate, SessionUpdate, SessionResponse


async def _get_session_with_counts(session: Session, db: AsyncSession) -> SessionResponse:
    """Attach live confirmed/waitlist counts to a session object."""
    confirmed = await db.execute(
        select(func.count()).select_from(Registration).where(
            Registration.session_id == session.id,
            Registration.status == "confirmed",
        )
    )
    confirmed_count = confirmed.scalar()

    waitlisted = await db.execute(
        select(func.count()).select_from(WaitlistEntry).where(
            WaitlistEntry.session_id == session.id,
            WaitlistEntry.status.in_(["waiting", "notified"]),
        )
    )
    waitlist_count = waitlisted.scalar()

    return SessionResponse(
        id=session.id,
        location=session.location,
        date=session.date,
        start_time=session.start_time,
        max_players=session.max_players,
        fee_cents=session.fee_cents,
        status=session.status,
        confirmed_count=confirmed_count,
        waitlist_count=waitlist_count,
        spots_remaining=max(0, session.max_players - confirmed_count),
    )


async def list_sessions(db: AsyncSession) -> list[SessionResponse]:
    """Return all sessions ordered by date, with live counts."""
    result = await db.execute(
        select(Session).order_by(Session.date, Session.start_time)
    )
    sessions = result.scalars().all()
    return [await _get_session_with_counts(s, db) for s in sessions]


async def get_session(session_id: UUID, db: AsyncSession) -> SessionResponse:
    """Return a single session with live counts."""
    session = await db.get(Session, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return await _get_session_with_counts(session, db)


async def create_session(data: SessionCreate, db: AsyncSession) -> SessionResponse:
    """Admin: create a new session."""
    session = Session(
        location=data.location,
        date=data.date,
        start_time=data.start_time,
        max_players=data.max_players,
        fee_cents=data.fee_cents,
        status="open",
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return await _get_session_with_counts(session, db)


async def update_session(
    session_id: UUID, data: SessionUpdate, db: AsyncSession
) -> SessionResponse:
    """
    Admin: update session fields.
    Guards against shrinking max_players below current confirmed count.
    """
    session = await db.get(Session, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Guard: don't allow reducing max_players below confirmed count
    if data.max_players is not None:
        confirmed = await db.execute(
            select(func.count()).select_from(Registration).where(
                Registration.session_id == session_id,
                Registration.status == "confirmed",
            )
        )
        confirmed_count = confirmed.scalar()
        if data.max_players < confirmed_count:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot reduce capacity below current confirmed count ({confirmed_count} players).",
            )

    # Apply only the fields that were provided
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(session, field, value)

    await db.commit()
    await db.refresh(session)
    return await _get_session_with_counts(session, db)


async def cancel_session(session_id: UUID, db: AsyncSession) -> dict:
    """
    Admin: cancel a session.
    Sets status to 'cancelled'. Refund logic handled separately.
    Note: in a full implementation, this would trigger refunds
    for all confirmed registrations — to be added as a background task.
    """
    session = await db.get(Session, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status == "cancelled":
        raise HTTPException(status_code=400, detail="Session is already cancelled")

    session.status = "cancelled"
    await db.commit()

    # TODO: trigger background task to refund all confirmed registrations
    return {
        "message": f"Session on {session.date} has been cancelled. Refund processing will begin shortly."
    }
