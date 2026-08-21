import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import (
    InvalidTokenError,
    TokenType,
    create_email_verify_token,
    create_password_reset_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.notification import NotificationType
from app.models.user import Address, User, UserRole
from app.modules.notifications.service import notify
from app.schemas.auth import RegisterRequest

settings = get_settings()


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    return (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()


async def register_user(db: AsyncSession, data: RegisterRequest) -> User:
    if await get_user_by_email(db, data.email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    existing_phone = (
        await db.execute(select(User).where(User.phone_number == data.phone_number))
    ).scalar_one_or_none()
    if existing_phone:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Phone number already registered")

    user = User(
        full_name=data.full_name,
        phone_number=data.phone_number,
        email=data.email,
        password_hash=hash_password(data.password),
        role=UserRole.CUSTOMER,
        business_name=data.business_name,
        business_type=data.business_type,
    )
    db.add(user)
    await db.flush()

    address = Address(
        user_id=user.id,
        label="Home",
        street=data.street,
        city=data.city,
        state=data.state,
        phone_number=data.phone_number,
        is_default=True,
    )
    db.add(address)
    await db.flush()

    verify_token = create_email_verify_token(str(user.id))
    verify_url = f"{settings.frontend_url}/verify?token={verify_token}"
    await notify(
        db,
        user=user,
        notification_type=NotificationType.ACCOUNT_VERIFICATION,
        payload={"verify_url": verify_url},
    )

    await db.commit()
    await db.refresh(user)
    return user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User:
    user = await get_user_by_email(db, email)
    if user is None or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated")
    return user


async def verify_user(db: AsyncSession, token: str) -> User:
    try:
        payload = decode_token(token, TokenType.EMAIL_VERIFY)
    except InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired token") from exc

    user = (await db.execute(select(User).where(User.id == uuid.UUID(payload["sub"])))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.is_verified = True
    await db.commit()
    await db.refresh(user)
    return user


async def request_password_reset(db: AsyncSession, email: str) -> None:
    user = await get_user_by_email(db, email)
    if user is None:
        return  # do not reveal whether an account exists
    reset_token = create_password_reset_token(str(user.id))
    reset_url = f"{settings.frontend_url}/reset-password?token={reset_token}"
    await notify(
        db,
        user=user,
        notification_type=NotificationType.PASSWORD_RESET,
        payload={"reset_url": reset_url},
    )
    await db.commit()


async def confirm_password_reset(db: AsyncSession, token: str, new_password: str) -> None:
    try:
        payload = decode_token(token, TokenType.PASSWORD_RESET)
    except InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired token") from exc

    user = (await db.execute(select(User).where(User.id == uuid.UUID(payload["sub"])))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.password_hash = hash_password(new_password)
    await db.commit()
