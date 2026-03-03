from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID
from typing import Optional


# ──────────────────────────── Auth ────────────────────────────

class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[a-zA-Z0-9_]+$")
    password: str = Field(min_length=8, max_length=128)
    display_name: Optional[str] = Field(None, max_length=64)


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


# ──────────────────────────── User ────────────────────────────

class UserOut(BaseModel):
    id: UUID
    username: str
    display_name: Optional[str]
    role: str
    created_at: datetime
    last_seen: Optional[datetime]

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    display_name: Optional[str] = Field(None, max_length=64)


# ──────────────────────────── Channel ─────────────────────────

class ChannelCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    description: Optional[str] = Field(None, max_length=256)
    category: Optional[str] = Field(None, max_length=64)
    is_private: bool = False


class ChannelUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=64)
    description: Optional[str] = Field(None, max_length=256)
    category: Optional[str] = Field(None, max_length=64)
    archived: Optional[bool] = None


class ChannelOut(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    category: Optional[str]
    is_private: bool
    created_by: UUID
    created_at: datetime
    archived: bool
    member_count: Optional[int] = None

    model_config = {"from_attributes": True}


class ChannelMemberOut(BaseModel):
    user_id: UUID
    username: str
    display_name: Optional[str]
    role_override: Optional[str]
    joined_at: datetime

    model_config = {"from_attributes": True}


class AddMemberRequest(BaseModel):
    user_id: UUID


# ──────────────────────────── Message ─────────────────────────

class MessageSend(BaseModel):
    content: str = Field(min_length=1, max_length=4000)
    reply_to: Optional[UUID] = None


class MessageOut(BaseModel):
    id: UUID
    channel_id: UUID
    sender_id: Optional[UUID]
    sender_name: Optional[str]
    sender_role: Optional[str] = None
    content: str
    reply_to: Optional[UUID]
    created_at: datetime
    edited_at: Optional[datetime]

    model_config = {"from_attributes": True}


class MessageEdit(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class SetChannelRoleRequest(BaseModel):
    role: str = Field(pattern=r"^(admin|moderator|member)$")
