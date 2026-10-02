"""Unit tests for password hashing and JWT handling."""

import uuid
from datetime import timedelta

import jwt
import pytest

from app.core.config import Settings
from app.core.security import (
    InvalidTokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.models.enums import UserRole


def test_password_hash_roundtrip() -> None:
    hashed = hash_password("correct horse battery")

    assert hashed != "correct horse battery"
    assert hashed.startswith("$argon2id$")
    assert verify_password("correct horse battery", hashed)
    assert not verify_password("wrong password", hashed)


def test_access_token_roundtrip() -> None:
    user_id = uuid.uuid4()

    token = create_access_token(user_id, UserRole.DRIVER)

    assert decode_access_token(token) == user_id
    claims = jwt.decode(token, options={"verify_signature": False})
    assert claims["role"] == "driver"


def test_expired_token_is_rejected() -> None:
    token = create_access_token(uuid.uuid4(), UserRole.ADMIN, expires_delta=timedelta(seconds=-1))

    with pytest.raises(InvalidTokenError):
        decode_access_token(token)


def test_token_signed_with_other_key_is_rejected() -> None:
    forged = jwt.encode(
        {"sub": str(uuid.uuid4()), "exp": 9999999999}, "attacker-key-" * 4, algorithm="HS256"
    )

    with pytest.raises(InvalidTokenError):
        decode_access_token(forged)


@pytest.mark.parametrize("token", ["", "not-a-jwt", "a.b.c"])
def test_garbage_token_is_rejected(token: str) -> None:
    with pytest.raises(InvalidTokenError):
        decode_access_token(token)


def test_production_requires_real_jwt_secret() -> None:
    with pytest.raises(ValueError, match="JWT_SECRET_KEY"):
        Settings(environment="production", _env_file=None)

    settings = Settings(environment="production", jwt_secret_key="x" * 40, _env_file=None)
    assert settings.environment == "production"
