"""Password hashing and JWT access tokens."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from pwdlib import PasswordHash

from app.core.config import get_settings
from app.models.enums import UserRole

# Argon2id with library-recommended parameters.
_password_hash = PasswordHash.recommended()

# Verified against when a login email does not exist, so the response time does
# not reveal whether an account is registered.
DUMMY_PASSWORD_HASH = _password_hash.hash("dummy-password-for-timing")


class InvalidTokenError(Exception):
    """Raised when an access token is malformed, tampered with or expired."""


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return _password_hash.verify(password, hashed_password)


def create_access_token(
    user_id: uuid.UUID, role: UserRole, expires_delta: timedelta | None = None
) -> str:
    """Issue a signed JWT identifying the user and their role."""
    settings = get_settings()
    now = datetime.now(UTC)
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.access_token_expire_minutes)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role.value,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(
        payload, settings.jwt_secret_key.get_secret_value(), algorithm=settings.jwt_algorithm
    )


def decode_access_token(token: str) -> uuid.UUID:
    """Validate a token and return the user id it was issued for."""
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "exp"]},
        )
        return uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, ValueError) as exc:
        raise InvalidTokenError(str(exc)) from exc
