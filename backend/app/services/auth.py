"""Account registration and authentication."""

import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import DUMMY_PASSWORD_HASH, hash_password, verify_password
from app.models import Business, Driver, User
from app.models.enums import DriverStatus, UserRole
from app.schemas.user import BusinessRegister, DriverRegister


class EmailAlreadyRegisteredError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


class InactiveUserError(Exception):
    pass


def _with_profiles():
    """Loader options that eagerly fetch the role-specific profiles."""
    return (selectinload(User.business), selectinload(User.driver))


async def get_user_with_profiles(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    result = await session.execute(
        select(User).where(User.id == user_id).options(*_with_profiles())
    )
    return result.scalar_one_or_none()


async def _add_user(
    session: AsyncSession, *, email: str, password: str, full_name: str, role: UserRole
) -> User:
    if await session.scalar(select(User.id).where(User.email == email)) is not None:
        raise EmailAlreadyRegisteredError(email)
    user = User(
        email=email, hashed_password=hash_password(password), full_name=full_name, role=role
    )
    session.add(user)
    return user


async def _commit_new_user(session: AsyncSession, user: User) -> User:
    """Commit a freshly built user and reload it with profiles attached."""
    try:
        await session.commit()
    except IntegrityError as exc:
        # A concurrent registration with the same email won the race.
        await session.rollback()
        if "uq_users_email" in str(exc.orig):
            raise EmailAlreadyRegisteredError(user.email) from exc
        raise
    created = await get_user_with_profiles(session, user.id)
    assert created is not None
    return created


async def register_business(session: AsyncSession, data: BusinessRegister) -> User:
    user = await _add_user(
        session,
        email=data.email,
        password=data.password,
        full_name=data.full_name,
        role=UserRole.BUSINESS,
    )
    user.business = Business(**data.business.model_dump())
    return await _commit_new_user(session, user)


async def register_driver(session: AsyncSession, data: DriverRegister) -> User:
    user = await _add_user(
        session,
        email=data.email,
        password=data.password,
        full_name=data.full_name,
        role=UserRole.DRIVER,
    )
    # New drivers start offline until they choose to go online.
    user.driver = Driver(**data.driver.model_dump(), status=DriverStatus.OFFLINE)
    return await _commit_new_user(session, user)


async def create_admin(session: AsyncSession, *, email: str, password: str, full_name: str) -> User:
    user = await _add_user(
        session,
        email=email.lower(),
        password=password,
        full_name=full_name,
        role=UserRole.ADMIN,
    )
    return await _commit_new_user(session, user)


async def authenticate(session: AsyncSession, *, email: str, password: str) -> User:
    """Return the user for valid credentials, or raise."""
    result = await session.execute(
        select(User).where(User.email == email.lower()).options(*_with_profiles())
    )
    user = result.scalar_one_or_none()
    if user is None:
        # Spend the same hashing time as a real check to avoid account enumeration.
        verify_password(password, DUMMY_PASSWORD_HASH)
        raise InvalidCredentialsError
    if not verify_password(password, user.hashed_password):
        raise InvalidCredentialsError
    if not user.is_active:
        raise InactiveUserError
    return user
