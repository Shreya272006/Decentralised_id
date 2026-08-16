import re
import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.rbac import Role

PASSWORD_RE = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^\w\s]).{10,}$")


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=10, max_length=128)
    full_name: str = Field(..., min_length=1, max_length=200)
    role: Role = Role.USER

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not PASSWORD_RE.match(v):
            raise ValueError(
                "Password must be at least 10 characters and include an uppercase letter, "
                "a lowercase letter, a digit, and a special character."
            )
        return v

    @field_validator("role")
    @classmethod
    def restrict_self_registerable_roles(cls, v: Role) -> Role:
        # Admins are never created via public registration.
        if v == Role.ADMIN:
            raise ValueError("Role not permitted for self-registration.")
        return v


class RegisterResponse(BaseModel):
    user_id: uuid.UUID
    email: EmailStr
    role: Role
    mfa_setup_required: bool


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)


class LoginResponse(BaseModel):
    otp_required: bool
    otp_challenge_token: str | None = None
    access_token: str | None = None
    refresh_token: str | None = None
    token_type: str = "bearer"


class VerifyOtpRequest(BaseModel):
    otp_challenge_token: str
    otp_code: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")


class TokenResponse(BaseModel):
    access_token: str | None = None
    refresh_token: str | None = None
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    refresh_token: str | None = None


class LogoutRequest(BaseModel):
    refresh_token: str | None = None
