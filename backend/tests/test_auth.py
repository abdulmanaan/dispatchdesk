"""API tests for registration, login, current user and role checks."""

from typing import Any

import pytest
from fastapi import APIRouter, Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AdminUser, BusinessUser, require_roles
from app.core.security import create_access_token
from app.models import User
from app.models.enums import UserRole
from app.services.auth import create_admin

PASSWORD = "s3cure-pass!"


def business_payload(email: str = "owner@karachi-biryani.pk") -> dict[str, Any]:
    return {
        "email": email,
        "password": PASSWORD,
        "full_name": "Bilal Ahmed",
        "business": {
            "name": "Karachi Biryani House",
            "category": "restaurant",
            "phone": "+923001234567",
            "address": "MM Alam Road, Gulberg III, Lahore",
            "lat": 31.5120,
            "lng": 74.3517,
        },
    }


def driver_payload(email: str = "rider@example.com") -> dict[str, Any]:
    return {
        "email": email,
        "password": PASSWORD,
        "full_name": "Usman Tariq",
        "driver": {"phone": "+923217654321", "vehicle_type": "motorbike"},
    }


async def login(client: AsyncClient, email: str, password: str = PASSWORD):
    return await client.post("/auth/login", data={"username": email, "password": password})


async def token_for(client: AsyncClient, email: str) -> str:
    response = await login(client, email)
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# --- Registration ----------------------------------------------------------------


async def test_register_business_creates_user_and_profile(client: AsyncClient) -> None:
    response = await client.post("/auth/register/business", json=business_payload())

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["role"] == "business"
    assert body["business"]["name"] == "Karachi Biryani House"
    assert body["driver"] is None
    assert "password" not in body and "hashed_password" not in body


async def test_register_driver_starts_offline(client: AsyncClient) -> None:
    response = await client.post("/auth/register/driver", json=driver_payload())

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["role"] == "driver"
    assert body["driver"]["status"] == "offline"
    assert body["driver"]["current_lat"] is None


async def test_email_is_case_insensitive_and_unique(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    first = await client.post("/auth/register/business", json=business_payload("Owner@Shop.PK"))
    assert first.status_code == 201
    assert first.json()["email"] == "owner@shop.pk"

    # Same email, different case, different role: still rejected.
    second = await client.post("/auth/register/driver", json=driver_payload("OWNER@shop.pk"))
    assert second.status_code == 409

    count = len((await db_session.scalars(select(User))).all())
    assert count == 1


@pytest.mark.parametrize(
    ("path", "change"),
    [
        ("password", "short"),
        ("email", "not-an-email"),
        ("business.lat", 120),
        ("business.phone", "call me"),
        ("business.category", "casino"),
        ("business.name", "   "),
    ],
)
async def test_register_business_validation(client: AsyncClient, path: str, change: Any) -> None:
    payload = business_payload()
    target = payload
    *parents, field = path.split(".")
    for key in parents:
        target = target[key]
    target[field] = change

    response = await client.post("/auth/register/business", json=payload)

    assert response.status_code == 422


async def test_role_cannot_be_chosen_at_registration(client: AsyncClient) -> None:
    payload = driver_payload() | {"role": "admin"}

    response = await client.post("/auth/register/driver", json=payload)

    assert response.status_code == 201
    assert response.json()["role"] == "driver"


# --- Login -----------------------------------------------------------------------


async def test_login_returns_token_and_user(client: AsyncClient) -> None:
    await client.post("/auth/register/business", json=business_payload())

    response = await login(client, "OWNER@karachi-biryani.pk")

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 3600
    assert body["user"]["business"]["name"] == "Karachi Biryani House"


@pytest.mark.parametrize(
    ("email", "password"),
    [("owner@karachi-biryani.pk", "wrong-password"), ("nobody@example.com", PASSWORD)],
)
async def test_login_rejects_bad_credentials(
    client: AsyncClient, email: str, password: str
) -> None:
    await client.post("/auth/register/business", json=business_payload())

    response = await login(client, email, password)

    # Same response for unknown email and wrong password: no account enumeration.
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"


async def test_disabled_account_cannot_log_in(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await client.post("/auth/register/driver", json=driver_payload())
    user = await db_session.scalar(select(User).where(User.email == "rider@example.com"))
    assert user is not None
    user.is_active = False
    await db_session.commit()

    response = await login(client, "rider@example.com")

    assert response.status_code == 403


# --- Current user ----------------------------------------------------------------


async def test_me_returns_profile(client: AsyncClient) -> None:
    await client.post("/auth/register/driver", json=driver_payload())
    token = await token_for(client, "rider@example.com")

    response = await client.get("/auth/me", headers=bearer(token))

    assert response.status_code == 200
    assert response.json()["driver"]["vehicle_type"] == "motorbike"


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer garbage"}])
async def test_me_requires_valid_token(client: AsyncClient, headers: dict[str, str]) -> None:
    response = await client.get("/auth/me", headers=headers)

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


async def test_token_of_deleted_user_is_rejected(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await client.post("/auth/register/driver", json=driver_payload())
    token = await token_for(client, "rider@example.com")
    user = await db_session.scalar(select(User).where(User.email == "rider@example.com"))
    await db_session.delete(user)
    await db_session.commit()

    response = await client.get("/auth/me", headers=bearer(token))

    assert response.status_code == 401


async def test_token_of_disabled_user_is_rejected(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await client.post("/auth/register/driver", json=driver_payload())
    token = await token_for(client, "rider@example.com")
    user = await db_session.scalar(select(User).where(User.email == "rider@example.com"))
    assert user is not None
    user.is_active = False
    await db_session.commit()

    response = await client.get("/auth/me", headers=bearer(token))

    assert response.status_code == 403


# --- Role-based access -----------------------------------------------------------


@pytest.fixture
async def rbac_client() -> Any:
    """A throwaway app with one endpoint per access rule, to test the role guards."""
    router = APIRouter()

    @router.get("/admin-only")
    async def admin_only(user: AdminUser) -> dict[str, str]:
        return {"role": user.role}

    @router.get("/business-only")
    async def business_only(user: BusinessUser) -> dict[str, str]:
        return {"role": user.role}

    @router.get("/staff", dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.DRIVER))])
    async def staff() -> dict[str, bool]:
        return {"ok": True}

    rbac_app = FastAPI()
    rbac_app.include_router(router)
    async with AsyncClient(transport=ASGITransport(app=rbac_app), base_url="http://t") as ac:
        yield ac


@pytest.mark.parametrize(
    ("role", "path", "expected"),
    [
        (UserRole.ADMIN, "/admin-only", 200),
        (UserRole.BUSINESS, "/admin-only", 403),
        (UserRole.DRIVER, "/admin-only", 403),
        (UserRole.BUSINESS, "/business-only", 200),
        (UserRole.ADMIN, "/business-only", 403),
        (UserRole.ADMIN, "/staff", 200),
        (UserRole.DRIVER, "/staff", 200),
        (UserRole.BUSINESS, "/staff", 403),
    ],
)
async def test_role_guards(
    rbac_client: AsyncClient,
    db_session: AsyncSession,
    role: UserRole,
    path: str,
    expected: int,
) -> None:
    user = User(email=f"{role}@example.com", hashed_password="x", full_name="X", role=role)
    db_session.add(user)
    await db_session.commit()

    response = await rbac_client.get(path, headers=bearer(create_access_token(user.id, role)))

    assert response.status_code == expected


async def test_role_is_read_from_database_not_token(
    rbac_client: AsyncClient, db_session: AsyncSession
) -> None:
    """A token claiming 'admin' does not grant admin access to a business user."""
    user = User(email="biz@example.com", hashed_password="x", full_name="X", role=UserRole.BUSINESS)
    db_session.add(user)
    await db_session.commit()

    forged_role_token = create_access_token(user.id, UserRole.ADMIN)
    response = await rbac_client.get("/admin-only", headers=bearer(forged_role_token))

    assert response.status_code == 403


async def test_create_admin_and_login(client: AsyncClient, db_session: AsyncSession) -> None:
    admin = await create_admin(
        db_session, email="Admin@DispatchDesk.pk", password=PASSWORD, full_name="Admin"
    )
    assert admin.role == UserRole.ADMIN

    token = await token_for(client, "admin@dispatchdesk.pk")
    me = await client.get("/auth/me", headers=bearer(token))
    assert me.json()["role"] == "admin"
