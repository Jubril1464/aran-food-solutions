import uuid
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from typing import Any

import bcrypt
import jwt

from app.core.config import get_settings

settings = get_settings()

_BCRYPT_MAX_BYTES = 72  # bcrypt silently ignores bytes beyond this; reject longer passwords instead


class TokenType(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"
    EMAIL_VERIFY = "email_verify"
    PASSWORD_RESET = "password_reset"


def hash_password(password: str) -> str:
    password_bytes = password.encode("utf-8")
    if len(password_bytes) > _BCRYPT_MAX_BYTES:
        raise ValueError(f"Password must be at most {_BCRYPT_MAX_BYTES} bytes")
    return bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    password_bytes = password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
    try:
        return bcrypt.checkpw(password_bytes, password_hash.encode("utf-8"))
    except ValueError:
        return False


def _create_token(subject: str, token_type: TokenType, expires_delta: timedelta, extra: dict[str, Any] | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type.value,
        "iat": now,
        "exp": now + expires_delta,
        "jti": str(uuid.uuid4()),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: str, role: str) -> str:
    return _create_token(
        user_id,
        TokenType.ACCESS,
        timedelta(minutes=settings.access_token_expire_minutes),
        extra={"role": role},
    )


def create_refresh_token(user_id: str) -> str:
    return _create_token(user_id, TokenType.REFRESH, timedelta(days=settings.refresh_token_expire_days))


def create_email_verify_token(user_id: str) -> str:
    return _create_token(user_id, TokenType.EMAIL_VERIFY, timedelta(hours=24))


def create_password_reset_token(user_id: str) -> str:
    return _create_token(user_id, TokenType.PASSWORD_RESET, timedelta(hours=1))


class InvalidTokenError(Exception):
    pass


def decode_token(token: str, expected_type: TokenType) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise InvalidTokenError(str(exc)) from exc
    if payload.get("type") != expected_type.value:
        raise InvalidTokenError("Unexpected token type")
    return payload
