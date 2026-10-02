"""Shared FastAPI dependencies: database session, current user, role checks."""

from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import InvalidTokenError, decode_access_token
from app.db.session import get_db
from app.models import User
from app.models.enums import UserRole
from app.services.auth import get_user_with_profiles

DbSession = Annotated[AsyncSession, Depends(get_db)]

# tokenUrl powers the "Authorize" button in the interactive API docs.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

_credentials_error = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)], session: DbSession
) -> User:
    """Resolve the bearer token to an active user (with profiles loaded)."""
    try:
        user_id = decode_access_token(token)
    except InvalidTokenError:
        raise _credentials_error from None

    user = await get_user_with_profiles(session, user_id)
    if user is None:
        raise _credentials_error
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: UserRole) -> Callable[[User], Awaitable[User]]:
    """Dependency factory: allow only users whose role is in ``roles``.

    The role is read from the database (via ``get_current_user``), not from the
    token, so a role change takes effect immediately.
    """
    allowed = frozenset(roles)

    async def checker(user: CurrentUser) -> User:
        if user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action",
            )
        return user

    return checker


AdminUser = Annotated[User, Depends(require_roles(UserRole.ADMIN))]
BusinessUser = Annotated[User, Depends(require_roles(UserRole.BUSINESS))]
DriverUser = Annotated[User, Depends(require_roles(UserRole.DRIVER))]
