from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.database import get_db
from app.core.security import get_current_user, require_admin
from app.models.user import User
from app.schemas.session import SessionCreate, SessionUpdate, SessionResponse
from app.services.session import (
    list_sessions,
    get_session,
    create_session,
    update_session,
    cancel_session,
)

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("", response_model=list[SessionResponse])
async def get_all_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all sessions with live confirmed/waitlist counts."""
    return await list_sessions(db)


@router.get("/{session_id}", response_model=SessionResponse)
async def get_one_session(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single session's details and current player counts."""
    return await get_session(session_id, db)


@router.post("", response_model=SessionResponse, status_code=201)
async def create_new_session(
    data: SessionCreate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Admin only: create a new session."""
    return await create_session(data, db)


@router.patch("/{session_id}", response_model=SessionResponse)
async def update_existing_session(
    session_id: UUID,
    data: SessionUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Admin only: update session details. Cannot reduce capacity below confirmed count."""
    return await update_session(session_id, data, db)


@router.delete("/{session_id}")
async def cancel_existing_session(
    session_id: UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Admin only: cancel a session."""
    return await cancel_session(session_id, db)
