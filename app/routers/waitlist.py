from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.waitlist import WaitlistJoinResponse, ClaimSpotResponse
from app.services.waitlist import join_waitlist, claim_waitlist_spot

router = APIRouter(tags=["waitlist"])

@router.post("/sessions/{session_id}/waitlist", response_model=WaitlistJoinResponse)
async def join_session_waitlist(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    entry = await join_waitlist(session_id, current_user, db)
    return WaitlistJoinResponse(
        waitlist_id=entry.id,
        position=entry.position,
        message=f"You're #{entry.position} on the waitlist. We'll notify you if a spot opens.",
    )


@router.post("/waitlist/{waitlist_id}/claim", response_model=ClaimSpotResponse)
async def claim_spot(
    waitlist_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await claim_waitlist_spot(waitlist_id, current_user, db)
    return ClaimSpotResponse(**result)


@router.delete("/registrations/{registration_id}")
async def cancel_registration_endpoint(
    registration_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.services.waitlist import cancel_registration
    await cancel_registration(registration_id, current_user, db)
    return {"message": "Registration cancelled. Your credit has been added to your account balance."}
