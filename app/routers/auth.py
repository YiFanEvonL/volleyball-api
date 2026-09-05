from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import httpx

from app.database import get_db
from app.models.user import User
from app.schemas.user import AuthResponse, UserResponse
from app.core.security import create_access_token
from app.core.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])


async def _upsert_user(
    db: AsyncSession,
    oauth_provider: str,
    oauth_id: str,
    email: str,
    name: str,
) -> User:
    """Find existing user by oauth_id, or create a new one."""
    result = await db.execute(
        select(User).where(
            User.oauth_provider == oauth_provider,
            User.oauth_id == oauth_id,
        )
    )
    user = result.scalar_one_or_none()
    if not user:
        user = User(
            name=name,
            email=email,
            oauth_provider=oauth_provider,
            oauth_id=oauth_id,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    return user


@router.post("/google", response_model=AuthResponse)
async def google_login(
    payload: dict,  # {"id_token": "..."}
    db: AsyncSession = Depends(get_db),
):
    """
    Verify a Google ID token from the frontend (Expo Google Auth),
    then upsert the user and return a JWT.
    """
    id_token = payload.get("id_token")
    if not id_token:
        raise HTTPException(status_code=400, detail="id_token is required")

    # Verify with Google's tokeninfo endpoint
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://oauth2.googleapis.com/tokeninfo",
            params={"id_token": id_token},
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid Google token")

    data = resp.json()
    if data.get("aud") != settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=401, detail="Token audience mismatch")

    user = await _upsert_user(
        db,
        oauth_provider="google",
        oauth_id=data["sub"],
        email=data["email"],
        name=data.get("name", data["email"]),
    )
    token = create_access_token(str(user.id))
    return AuthResponse(access_token=token, user=UserResponse.model_validate(user))


@router.post("/apple", response_model=AuthResponse)
async def apple_login(
    payload: dict,  # {"identity_token": "...", "full_name": {"givenName": "...", "familyName": "..."}}
    db: AsyncSession = Depends(get_db),
):
    """
    Verify an Apple identity token from the frontend (Expo Apple Auth),
    then upsert the user and return a JWT.
    Note: Apple only sends the user's name on the FIRST login.
    """
    identity_token = payload.get("identity_token")
    if not identity_token:
        raise HTTPException(status_code=400, detail="identity_token is required")

    # Fetch Apple's public keys
    async with httpx.AsyncClient() as client:
        keys_resp = await client.get("https://appleid.apple.com/auth/keys")
    apple_keys = keys_resp.json()

    # Decode and verify (jose handles key selection from the JWKS)
    from jose import jwt as jose_jwt
    try:
        claims = jose_jwt.decode(
            identity_token,
            apple_keys,
            algorithms=["RS256"],
            audience=settings.APPLE_CLIENT_ID,
        )
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid Apple token")

    # Apple only provides name on first sign-in; fall back to email prefix
    full_name_data = payload.get("full_name", {})
    given = full_name_data.get("givenName") or ""
    family = full_name_data.get("familyName") or ""
    name = f"{given} {family}".strip() or claims.get("email", "Player")

    user = await _upsert_user(
        db,
        oauth_provider="apple",
        oauth_id=claims["sub"],
        email=claims["email"],
        name=name,
    )
    token = create_access_token(str(user.id))
    return AuthResponse(access_token=token, user=UserResponse.model_validate(user))


@router.post("/logout")
async def logout():
    """
    Stateless JWT — logout is handled client-side by deleting the token.
    This endpoint exists for future token blocklist support.
    """
    return {"message": "Logged out successfully. Please delete your token on the client."}
