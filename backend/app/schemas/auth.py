import uuid

from pydantic import BaseModel, EmailStr, Field

from app.models.user import UserRole


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=255)
    phone_number: str = Field(min_length=7, max_length=32)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    street: str
    city: str
    state: str
    business_name: str | None = None
    business_type: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: uuid.UUID
    full_name: str
    phone_number: str
    email: str
    role: UserRole
    business_name: str | None
    business_type: str | None
    is_verified: bool
    is_active: bool

    model_config = {"from_attributes": True}


class VerifyRequest(BaseModel):
    token: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)
