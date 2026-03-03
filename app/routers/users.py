from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, require_admin
from app.models.user import User
from app.schemas import UserOut, UserUpdate

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=list[UserOut])
async def list_users(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).order_by(User.username))
    return result.scalars().all()


@router.get("/online", response_model=list[UserOut])
async def online_users(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return users currently tracked as online via the WebSocket manager."""
    # This imports the connection manager to check who's connected
    from app.websocket.manager import manager
    online_ids = manager.get_online_user_ids()
    if not online_ids:
        return []
    result = await db.execute(select(User).where(User.id.in_(online_ids)))
    return result.scalars().all()


@router.get("/{user_id}", response_model=UserOut)
async def get_user(
    user_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    return target


@router.patch("/me", response_model=UserOut)
async def update_me(
    req: UserUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if req.display_name is not None:
        user.display_name = req.display_name
    await db.flush()
    return user


@router.patch("/{user_id}/role")
async def set_user_role(
    user_id: UUID,
    role: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    if role not in ("admin", "moderator", "member"):
        raise HTTPException(status_code=400, detail="Invalid role")
    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    target.role = role
    await db.flush()
    return {"status": "ok", "user_id": str(user_id), "new_role": role}
