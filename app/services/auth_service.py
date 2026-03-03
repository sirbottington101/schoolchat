import uuid
from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.user import User, UserRole

settings = get_settings()
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(user_id: uuid.UUID) -> str:
    payload = {
        "sub": str(user_id),
        "type": "access",
        "exp": datetime.now(timezone.utc)
        + timedelta(minutes=settings.jwt_access_expire_minutes),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def create_refresh_token(user_id: uuid.UUID) -> str:
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "exp": datetime.now(timezone.utc)
        + timedelta(days=settings.jwt_refresh_expire_days),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_token(token: str) -> dict:
    """Decode and validate a JWT. Raises jwt.PyJWTError on failure."""
    return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])


async def register_user(
    db: AsyncSession,
    username: str,
    password: str,
    display_name: str | None = None,
) -> User:
    # Check uniqueness
    existing = await db.execute(select(User).where(User.username == username))
    if existing.scalar_one_or_none():
        raise ValueError("Username already taken")

    # First user becomes admin
    count = await db.execute(select(User))
    is_first = count.scalars().first() is None

    user = User(
        username=username,
        password_hash=hash_password(password),
        display_name=display_name or username,
        role=UserRole.admin if is_first else UserRole.member,
    )
    db.add(user)
    await db.flush()
    return user


async def authenticate_user(
    db: AsyncSession, username: str, password: str
) -> User | None:
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(password, user.password_hash):
        return None
    # Update last seen
    user.last_seen = datetime.now(timezone.utc)
    await db.flush()
    return user


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()
