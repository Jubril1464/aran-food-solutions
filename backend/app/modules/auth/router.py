from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.rate_limit import limiter
from app.core.security import (
    InvalidTokenError,
    TokenType,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.models.user import User
from app.modules.auth import service
from app.schemas.auth import (
    LoginRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
    VerifyRequest,
)
from fastapi import HTTPException, status

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()

REFRESH_COOKIE = "refresh_token"
REFRESH_COOKIE_PATH = f"{settings.api_prefix}/auth"

# SameSite=None is only honoured on a Secure cookie, and browsers silently drop
# the whole Set-Cookie otherwise - so the two settings are resolved together
# rather than left to be configured inconsistently. On AWS the frontend
# (CloudFront) and the API (API Gateway) are different sites, so the cookie has
# to be None/Secure or silent token refresh never receives it.
_SAMESITE = settings.refresh_cookie_samesite.lower()
_COOKIE_SECURE = _SAMESITE == "none" or settings.environment != "development"


def _set_refresh_cookie(response: Response, user_id: str) -> None:
    token = create_refresh_token(user_id)
    response.set_cookie(
        REFRESH_COOKIE,
        token,
        httponly=True,
        secure=_COOKIE_SECURE,
        samesite=_SAMESITE,
        max_age=settings.refresh_token_expire_days * 24 * 3600,
        path=REFRESH_COOKIE_PATH,
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def register(request: Request, data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    user = await service.register_user(db, data)
    return user


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(request: Request, data: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    user = await service.authenticate_user(db, data.email, data.password)
    _set_refresh_cookie(response, str(user.id))
    access_token = create_access_token(str(user.id), user.role.value)
    return TokenResponse(access_token=access_token)


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("30/minute")
async def refresh(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    token = request.cookies.get(REFRESH_COOKIE)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing refresh token")
    try:
        payload = decode_token(token, TokenType.REFRESH)
    except InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token") from exc

    from sqlalchemy import select
    import uuid

    user = (await db.execute(select(User).where(User.id == uuid.UUID(payload["sub"])))).scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    _set_refresh_cookie(response, str(user.id))
    access_token = create_access_token(str(user.id), user.role.value)
    return TokenResponse(access_token=access_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response):
    # Attributes must match the Set-Cookie that created it (path, and
    # SameSite/Secure) or the browser keeps the original cookie.
    response.delete_cookie(
        REFRESH_COOKIE,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=_COOKIE_SECURE,
        samesite=_SAMESITE,
    )


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)):
    return user


@router.post("/verify", response_model=UserResponse)
async def verify(data: VerifyRequest, db: AsyncSession = Depends(get_db)):
    return await service.verify_user(db, data.token)


@router.post("/password-reset/request", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("5/minute")
async def password_reset_request(request: Request, data: PasswordResetRequest, db: AsyncSession = Depends(get_db)):
    await service.request_password_reset(db, data.email)


@router.post("/password-reset/confirm", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("5/minute")
async def password_reset_confirm(request: Request, data: PasswordResetConfirm, db: AsyncSession = Depends(get_db)):
    await service.confirm_password_reset(db, data.token, data.new_password)
