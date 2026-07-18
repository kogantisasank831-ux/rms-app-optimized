"""Auth request/response schemas (Pydantic v2)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    # plain str (not EmailStr): login must not reject on email deliverability, and demo
    # accounts use the reserved .local domain. Lookup is case-insensitive in the repo.
    email: str = Field(min_length=3)
    password: str = Field(min_length=1)


class UserPublic(BaseModel):
    user_id: str
    full_name: str
    email: str
    role: str
    designation: str | None = None
    # profile-photo urls (presigned); null => the UI shows the person's initials
    photo_icon_url: str | None = None  # small avatar used throughout the app
    photo_url: str | None = None       # larger picture for the profile page


class LoginData(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserPublic


class LoginResponse(BaseModel):
    success: bool = True
    data: LoginData


class MeResponse(BaseModel):
    success: bool = True
    data: UserPublic
