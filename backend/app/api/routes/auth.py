"""Registration, login and current-user endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import CurrentUser, DbSession
from app.core.config import get_settings
from app.core.rate_limit import auth_rate_limit
from app.core.security import create_access_token
from app.models import User
from app.schemas.auth import TokenResponse
from app.schemas.user import BusinessRegister, DriverRegister, UserRead
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])

_email_taken = HTTPException(
    status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists"
)


@router.post(
    "/register/business",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(auth_rate_limit)],
)
async def register_business(data: BusinessRegister, session: DbSession) -> User:
    """Create a business account together with its business profile."""
    try:
        return await auth_service.register_business(session, data)
    except auth_service.EmailAlreadyRegisteredError:
        raise _email_taken from None


@router.post(
    "/register/driver",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(auth_rate_limit)],
)
async def register_driver(data: DriverRegister, session: DbSession) -> User:
    """Create a driver account. Drivers start offline."""
    try:
        return await auth_service.register_driver(session, data)
    except auth_service.EmailAlreadyRegisteredError:
        raise _email_taken from None


@router.post("/login", response_model=TokenResponse, dependencies=[Depends(auth_rate_limit)])
async def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()], session: DbSession
) -> TokenResponse:
    """Exchange email + password for a bearer token.

    Uses the OAuth2 form format (``username`` field holds the email) so the
    interactive docs' "Authorize" button works out of the box.
    """
    try:
        user = await auth_service.authenticate(session, email=form.username, password=form.password)
    except auth_service.InvalidCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    except auth_service.InactiveUserError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled"
        ) from None

    expires_in = get_settings().access_token_expire_minutes * 60
    return TokenResponse(
        access_token=create_access_token(user.id, user.role),
        expires_in=expires_in,
        user=UserRead.model_validate(user),
    )


@router.get("/me", response_model=UserRead)
async def read_me(user: CurrentUser) -> User:
    """Return the signed-in user and their profile."""
    return user
