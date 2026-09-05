from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from app.database import get_db
from app.schemas.registration import RegisterResponse
from app.services.registration import register_for_session
from app.core.security import get_current_user
from app.models.user import User

router = APIRouter(prefix="/sessions", tags=["registrations"])

@router.post("/{session_id}/register", response_model=RegisterResponse)
async def register(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await register_for_session(session_id, current_user, db)
    return RegisterResponse(**result)
