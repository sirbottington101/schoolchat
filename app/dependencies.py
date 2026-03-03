import uuid
from fastapi import Depends, HTTPException, status, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.auth_service import decode_token, get_user_by_id
from app.models.user import User


async def get_current_user(
    authorization: str = Header(..., description="Bearer <token>"),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extract and validate the JWT from the Authorization header."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header",
        )

    token = authorization.removeprefix("Bearer ").strip()

    try:
        payload = decode_token(token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    user_id = uuid.UUID(payload["sub"])
    user = await get_user_by_id(db, user_id)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role.value != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


async def require_moderator(user: User = Depends(get_current_user)) -> User:
    if user.role.value not in ("admin", "moderator"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Moderator access required",
        )
    return user
