"""API tests for driver self-service and the driver's order actions."""

import asyncio
from datetime import UTC, datetime
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import SessionLocal
from app.models import AuditLog, Driver, Order, OrderAssignment
from app.models.enums import AssignmentStatus, DriverStatus, OrderStatus, UserRole
from app.services import order_state
from app.services import orders as order_service
from app.services.auth import get_user_with_profiles
from app.services.order_state import InvalidTransitionError
from tests.factories import (
    assign_order,
    auth_headers,
    business_headers,
    create_business,
    create_driver,
    create_order,
    create_user,
    driver_headers,
)


async def fresh_driver(session: AsyncSession, driver: Driver) -> Driver:
    driver = await session.get(Driver, driver.id, populate_existing=True)
    assert driver is not None
    return driver


async def assignment_for(session: AsyncSession, order: Order) -> OrderAssignment:
    assignment = await session.scalar(
        select(OrderAssignment)
        .where(OrderAssignment.order_id == order.id)
        .execution_options(populate_existing=True)
    )
    assert assignment is not None
    return assignment


async def setup_assigned(
    session: AsyncSession, *, accepted: bool = False
) -> tuple[Driver, Order, dict[str, str]]:
    business = await create_business(session)
    driver = await create_driver(session)
    order = await create_order(session, business)
    await assign_order(session, order, driver, accepted=accepted)
    await session.commit()
    return driver, order, driver_headers(driver)


# --- Location and status ---------------------------------------------------------


async def test_update_location(client: AsyncClient, db_session: AsyncSession) -> None:
    driver = await create_driver(db_session, current_lat=None, current_lng=None)
    await db_session.commit()

    response = await client.put(
        "/drivers/me/location", json={"lat": 31.52, "lng": 74.35}, headers=driver_headers(driver)
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["current_lat"], body["current_lng"]) == (31.52, 74.35)
    assert body["location_updated_at"] is not None


async def test_go_available_requires_location(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    driver = await create_driver(
        db_session, status=DriverStatus.OFFLINE, current_lat=None, current_lng=None
    )
    await db_session.commit()
    headers = driver_headers(driver)

    no_location = await client.put(
        "/drivers/me/status", json={"status": "available"}, headers=headers
    )
    assert no_location.status_code == 409

    with_location = await client.put(
        "/drivers/me/status",
        json={"status": "available", "lat": 31.5, "lng": 74.3},
        headers=headers,
    )
    assert with_location.status_code == 200
    assert with_location.json()["status"] == "available"

    audit = await db_session.scalar(
        select(AuditLog).where(AuditLog.action == "driver.status_changed")
    )
    assert audit is not None and audit.details == {"from": "offline", "to": "available"}


async def test_go_offline_and_back(client: AsyncClient, db_session: AsyncSession) -> None:
    driver = await create_driver(db_session)  # available, with location
    await db_session.commit()
    headers = driver_headers(driver)

    off = await client.put("/drivers/me/status", json={"status": "offline"}, headers=headers)
    on = await client.put("/drivers/me/status", json={"status": "available"}, headers=headers)

    assert off.json()["status"] == "offline"
    assert on.json()["status"] == "available"


@pytest.mark.parametrize(
    "payload",
    [{"status": "busy"}, {"status": "sleeping"}, {"status": "available", "lat": 31.5}],
)
async def test_status_validation(
    client: AsyncClient, db_session: AsyncSession, payload: dict[str, Any]
) -> None:
    driver = await create_driver(db_session)
    await db_session.commit()

    response = await client.put("/drivers/me/status", json=payload, headers=driver_headers(driver))

    assert response.status_code == 422


@pytest.mark.parametrize("target", ["offline", "available"])
async def test_busy_driver_cannot_change_status(
    client: AsyncClient, db_session: AsyncSession, target: str
) -> None:
    driver, _order, headers = await setup_assigned(db_session)

    response = await client.put("/drivers/me/status", json={"status": target}, headers=headers)

    assert response.status_code == 409
    assert (await fresh_driver(db_session, driver)).status == DriverStatus.BUSY


async def test_driver_endpoints_require_driver_role(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    business = await create_business(db_session)
    await db_session.commit()
    headers = business_headers(business)

    for method, path, body in [
        ("PUT", "/drivers/me/status", {"status": "offline"}),
        ("PUT", "/drivers/me/location", {"lat": 31.5, "lng": 74.3}),
        ("GET", "/drivers/me/order", None),
    ]:
        response = await client.request(method, path, json=body, headers=headers)
        assert response.status_code == 403, path


# --- Current order ---------------------------------------------------------------


async def test_current_order(client: AsyncClient, db_session: AsyncSession) -> None:
    idle = await create_driver(db_session)
    await db_session.commit()
    driver, order, headers = await setup_assigned(db_session)

    assert (await client.get("/drivers/me/order", headers=driver_headers(idle))).json() is None
    assert (await client.get("/drivers/me/order", headers=headers)).json()["id"] == str(order.id)


# --- Order lifecycle (driver side) -----------------------------------------------


async def test_full_delivery_flow(client: AsyncClient, db_session: AsyncSession) -> None:
    driver, order, headers = await setup_assigned(db_session)

    accepted = await client.post(f"/orders/{order.id}/accept", headers=headers)
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "assigned"
    assert accepted.json()["accepted_at"] is not None
    assert (await assignment_for(db_session, order)).status == AssignmentStatus.ACCEPTED

    picked = await client.post(f"/orders/{order.id}/pickup", headers=headers)
    assert picked.json()["status"] == "picked_up"

    delivered = await client.post(f"/orders/{order.id}/deliver", headers=headers)
    assert delivered.status_code == 200
    assert delivered.json()["status"] == "delivered"
    assert delivered.json()["delivered_at"] is not None

    # The driver is free again and the assignment is closed as completed.
    assert (await fresh_driver(db_session, driver)).status == DriverStatus.AVAILABLE
    assignment = await assignment_for(db_session, order)
    assert assignment.status == AssignmentStatus.COMPLETED
    assert assignment.ended_at is not None

    actions = (
        await db_session.scalars(
            select(AuditLog.action).where(AuditLog.entity_id == str(order.id)).order_by(AuditLog.id)
        )
    ).all()
    assert actions == ["order.accepted", "order.picked_up", "order.delivered"]


async def test_cannot_pick_up_before_accepting(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _driver, order, headers = await setup_assigned(db_session)

    response = await client.post(f"/orders/{order.id}/pickup", headers=headers)

    assert response.status_code == 409
    assert "accepted" in response.json()["detail"]


async def test_cannot_deliver_before_pickup(client: AsyncClient, db_session: AsyncSession) -> None:
    _driver, order, headers = await setup_assigned(db_session, accepted=True)

    response = await client.post(f"/orders/{order.id}/deliver", headers=headers)

    assert response.status_code == 409


async def test_accept_twice_is_rejected(client: AsyncClient, db_session: AsyncSession) -> None:
    _driver, order, headers = await setup_assigned(db_session)

    await client.post(f"/orders/{order.id}/accept", headers=headers)
    response = await client.post(f"/orders/{order.id}/accept", headers=headers)

    assert response.status_code == 409


async def test_driver_cannot_touch_other_drivers_order(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _driver, order, _headers = await setup_assigned(db_session)
    other = await create_driver(db_session)
    await db_session.commit()

    for action in ("accept", "pickup", "deliver"):
        response = await client.post(f"/orders/{order.id}/{action}", headers=driver_headers(other))
        assert response.status_code == 404, action


async def test_only_drivers_perform_delivery_actions(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _driver, order, _headers = await setup_assigned(db_session)
    admin = await create_user(db_session, UserRole.ADMIN)
    await db_session.commit()

    response = await client.post(
        f"/orders/{order.id}/accept", headers=auth_headers(admin.id, UserRole.ADMIN)
    )

    assert response.status_code == 403


@pytest.mark.parametrize("accepted", [False, True])
async def test_driver_fails_order(
    client: AsyncClient, db_session: AsyncSession, accepted: bool
) -> None:
    driver, order, headers = await setup_assigned(db_session, accepted=accepted)
    if accepted:
        await client.post(f"/orders/{order.id}/pickup", headers=headers)

    response = await client.post(
        f"/orders/{order.id}/fail", json={"reason": "Customer not answering"}, headers=headers
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "failed"
    assert response.json()["failure_reason"] == "Failed by driver: Customer not answering"
    assert (await fresh_driver(db_session, driver)).status == DriverStatus.AVAILABLE
    assert (await assignment_for(db_session, order)).status == AssignmentStatus.FAILED


@pytest.mark.parametrize("body", [{}, {"reason": ""}, {"reason": "  "}, {"reason": "x" * 201}])
async def test_fail_requires_reason(
    client: AsyncClient, db_session: AsyncSession, body: dict[str, Any]
) -> None:
    _driver, order, headers = await setup_assigned(db_session)

    response = await client.post(f"/orders/{order.id}/fail", json=body, headers=headers)

    assert response.status_code == 422


async def test_driver_loses_access_after_delivery(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """A finished order stays visible in history, but cannot be acted on again."""
    _driver, order, headers = await setup_assigned(db_session, accepted=True)
    await client.post(f"/orders/{order.id}/pickup", headers=headers)
    await client.post(f"/orders/{order.id}/deliver", headers=headers)

    again = await client.post(f"/orders/{order.id}/deliver", headers=headers)
    history = await client.get("/orders", params={"status": "delivered"}, headers=headers)

    assert again.status_code == 409
    assert history.json()["total"] == 1
    assert (await client.get("/drivers/me/order", headers=headers)).json() is None


async def test_order_status_stays_consistent(client: AsyncClient, db_session: AsyncSession) -> None:
    """After a successful delivery, the order row reflects every lifecycle timestamp."""
    _driver, order, headers = await setup_assigned(db_session)
    for action in ("accept", "pickup", "deliver"):
        await client.post(f"/orders/{order.id}/{action}", headers=headers)

    stored = await db_session.get(Order, order.id, populate_existing=True)
    assert stored is not None
    assert stored.status == OrderStatus.DELIVERED
    assert stored.assigned_at <= stored.accepted_at <= stored.picked_up_at <= stored.delivered_at


# --- Admin driver list -----------------------------------------------------------


async def test_admin_lists_drivers(client: AsyncClient, db_session: AsyncSession) -> None:
    busy_driver, order, _ = await setup_assigned(db_session)
    await create_driver(db_session, status=DriverStatus.OFFLINE)
    await create_driver(db_session)
    admin = await create_user(db_session, UserRole.ADMIN)
    await db_session.commit()
    headers = auth_headers(admin.id, UserRole.ADMIN)

    everyone = (await client.get("/drivers", headers=headers)).json()
    busy = (await client.get("/drivers", params={"status": "busy"}, headers=headers)).json()

    assert everyone["total"] == 3
    assert busy["total"] == 1
    item = busy["items"][0]
    assert item["id"] == str(busy_driver.id)
    assert item["active_order_id"] == str(order.id)
    assert item["email"].startswith("driver-")


async def test_admin_driver_search(client: AsyncClient, db_session: AsyncSession) -> None:
    await create_driver(db_session, phone="+923009998887")
    await create_driver(db_session)
    admin = await create_user(db_session, UserRole.ADMIN)
    await db_session.commit()

    response = await client.get(
        "/drivers", params={"search": "9998887"}, headers=auth_headers(admin.id, UserRole.ADMIN)
    )

    assert response.json()["total"] == 1


async def test_driver_list_is_admin_only(client: AsyncClient, db_session: AsyncSession) -> None:
    driver = await create_driver(db_session)
    business = await create_business(db_session)
    await db_session.commit()

    assert (await client.get("/drivers", headers=driver_headers(driver))).status_code == 403
    assert (await client.get("/drivers", headers=business_headers(business))).status_code == 403


# --- Concurrency -----------------------------------------------------------------


async def test_order_lock_serializes_conflicting_actions(db_session: AsyncSession) -> None:
    """While an admin holds the order lock, the driver's delivery must wait for it.

    Once the admin's cancellation commits, the waiting delivery sees the new state
    and is rejected, so the order can never be both delivered and cancelled.
    """
    driver, order, _headers = await setup_assigned(db_session, accepted=True)
    order.status = OrderStatus.PICKED_UP
    order.picked_up_at = datetime.now(UTC)
    admin = await create_user(db_session, UserRole.ADMIN)
    await db_session.commit()

    async with SessionLocal() as admin_session, SessionLocal() as driver_session:
        admin_user = await get_user_with_profiles(admin_session, admin.id)
        driver_user = await get_user_with_profiles(driver_session, driver.user_id)
        assert admin_user is not None and driver_user is not None

        # The admin's transaction locks the order and keeps the lock (not committed yet).
        locked = await order_service.get_order(admin_session, admin_user, order.id, for_update=True)

        delivery = asyncio.create_task(
            order_service.deliver_order(driver_session, driver_user, order.id)
        )
        done, _ = await asyncio.wait({delivery}, timeout=0.3)
        assert not done, "delivery should be blocked by the order row lock"

        order_state.fail(locked, reason="Cancelled by admin", now=datetime.now(UTC))
        await admin_session.commit()

        with pytest.raises(InvalidTransitionError):
            await delivery

    stored = await db_session.get(Order, order.id, populate_existing=True)
    assert stored is not None and stored.status == OrderStatus.FAILED
