"""API tests for creating, listing, fetching and cancelling orders."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, Driver, Order, OrderAssignment
from app.models.enums import AssignmentStatus, DriverStatus, OrderStatus, UserRole
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


def order_payload(**overrides: Any) -> dict[str, Any]:
    return {
        "customer_name": "Hina Malik",
        "customer_phone": "+923451234567",
        "dropoff_address": "House 12, Street 5, Model Town, Lahore",
        "dropoff_lat": 31.4835,
        "dropoff_lng": 74.3258,
    } | overrides


async def admin_headers(session: AsyncSession) -> dict[str, str]:
    admin = await create_user(session, UserRole.ADMIN)
    await session.commit()
    return auth_headers(admin.id, UserRole.ADMIN)


# --- Create ----------------------------------------------------------------------


async def test_business_creates_order_with_defaults(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    business = await create_business(db_session)
    await db_session.commit()

    before = datetime.now(UTC)
    response = await client.post(
        "/orders", json=order_payload(), headers=business_headers(business)
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "pending"
    assert body["business_id"] == str(business.id)
    assert body["driver_id"] is None
    # Pickup falls back to the business's own location.
    assert body["pickup_address"] == business.address
    assert (body["pickup_lat"], body["pickup_lng"]) == (business.lat, business.lng)
    # Default deadline: one hour from now.
    deliver_by = datetime.fromisoformat(body["deliver_by"])
    assert timedelta(minutes=59) < deliver_by - before < timedelta(minutes=61)

    audit = await db_session.scalar(select(AuditLog).where(AuditLog.action == "order.created"))
    assert audit is not None and audit.entity_id == body["id"]


async def test_create_order_with_explicit_pickup_and_deadline(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    business = await create_business(db_session)
    await db_session.commit()
    deadline = (datetime.now(UTC) + timedelta(hours=2)).isoformat()

    response = await client.post(
        "/orders",
        json=order_payload(
            pickup_address="Warehouse, Township, Lahore",
            pickup_lat=31.4500,
            pickup_lng=74.3000,
            deliver_by=deadline,
        ),
        headers=business_headers(business),
    )

    assert response.status_code == 201, response.text
    assert response.json()["pickup_address"] == "Warehouse, Township, Lahore"
    assert datetime.fromisoformat(response.json()["deliver_by"]) == datetime.fromisoformat(deadline)


@pytest.mark.parametrize(
    "overrides",
    [
        {"pickup_lat": 31.45},  # partial pickup
        {"deliver_by": "2020-01-01T00:00:00Z"},  # in the past
        {"deliver_by": (datetime.now(UTC) + timedelta(days=3)).isoformat()},  # too far
        {"deliver_by": "2030-01-01T00:00:00"},  # no timezone
        {"dropoff_lng": 200},
        {"customer_phone": "12"},
    ],
)
async def test_create_order_validation(
    client: AsyncClient, db_session: AsyncSession, overrides: dict[str, Any]
) -> None:
    business = await create_business(db_session)
    await db_session.commit()

    response = await client.post(
        "/orders", json=order_payload(**overrides), headers=business_headers(business)
    )

    assert response.status_code == 422


async def test_only_businesses_create_orders(client: AsyncClient, db_session: AsyncSession) -> None:
    driver = await create_driver(db_session)
    headers = await admin_headers(db_session)

    assert (await client.post("/orders", json=order_payload(), headers=headers)).status_code == 403
    response = await client.post("/orders", json=order_payload(), headers=driver_headers(driver))
    assert response.status_code == 403
    assert (await client.post("/orders", json=order_payload())).status_code == 401


# --- Visibility ------------------------------------------------------------------


async def test_list_is_scoped_by_role(client: AsyncClient, db_session: AsyncSession) -> None:
    shop_a, shop_b = await create_business(db_session), await create_business(db_session)
    driver = await create_driver(db_session)
    a1 = await create_order(db_session, shop_a)
    await create_order(db_session, shop_a)
    b1 = await create_order(db_session, shop_b)
    await assign_order(db_session, b1, driver)
    headers = await admin_headers(db_session)

    async def ids(h: dict[str, str]) -> set[str]:
        response = await client.get("/orders", headers=h)
        assert response.status_code == 200
        return {o["id"] for o in response.json()["items"]}

    assert len(await ids(business_headers(shop_a))) == 2
    assert str(a1.id) in await ids(business_headers(shop_a))
    assert await ids(business_headers(shop_b)) == {str(b1.id)}
    assert await ids(driver_headers(driver)) == {str(b1.id)}
    assert len(await ids(headers)) == 3


async def test_business_cannot_widen_scope_with_filter(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    shop_a, shop_b = await create_business(db_session), await create_business(db_session)
    await create_order(db_session, shop_b)
    await db_session.commit()

    response = await client.get(
        "/orders", params={"business_id": str(shop_b.id)}, headers=business_headers(shop_a)
    )

    assert response.json()["total"] == 0


async def test_get_order_of_other_business_is_not_found(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    shop_a, shop_b = await create_business(db_session), await create_business(db_session)
    order = await create_order(db_session, shop_b)
    headers = await admin_headers(db_session)

    assert (
        await client.get(f"/orders/{order.id}", headers=business_headers(shop_a))
    ).status_code == 404
    assert (
        await client.get(f"/orders/{order.id}", headers=business_headers(shop_b))
    ).status_code == 200
    assert (await client.get(f"/orders/{order.id}", headers=headers)).status_code == 200


# --- Filtering, sorting, pagination ----------------------------------------------


async def test_pagination(client: AsyncClient, db_session: AsyncSession) -> None:
    business = await create_business(db_session)
    for _ in range(7):
        await create_order(db_session, business)
    await db_session.commit()
    headers = business_headers(business)

    first = (await client.get("/orders", params={"page_size": 3}, headers=headers)).json()
    last = (await client.get("/orders", params={"page_size": 3, "page": 3}, headers=headers)).json()
    beyond = (
        await client.get("/orders", params={"page_size": 3, "page": 9}, headers=headers)
    ).json()

    assert (first["total"], first["pages"], len(first["items"])) == (7, 3, 3)
    assert len(last["items"]) == 1
    assert beyond["items"] == [] and beyond["total"] == 7


async def test_pages_do_not_overlap(client: AsyncClient, db_session: AsyncSession) -> None:
    business = await create_business(db_session)
    for _ in range(6):
        await create_order(db_session, business)
    await db_session.commit()
    headers = business_headers(business)

    seen: list[str] = []
    for page in (1, 2, 3):
        response = await client.get(
            "/orders", params={"page_size": 2, "page": page}, headers=headers
        )
        seen += [o["id"] for o in response.json()["items"]]

    assert len(seen) == len(set(seen)) == 6


async def test_filter_by_multiple_statuses(client: AsyncClient, db_session: AsyncSession) -> None:
    business = await create_business(db_session)
    driver = await create_driver(db_session)
    await create_order(db_session, business)
    assigned = await create_order(db_session, business)
    await assign_order(db_session, assigned, driver)
    await create_order(
        db_session,
        business,
        status=OrderStatus.FAILED,
        failure_reason="x",
        failed_at=datetime.now(UTC),
    )
    await db_session.commit()

    response = await client.get(
        "/orders",
        params=[("status", "pending"), ("status", "assigned")],
        headers=business_headers(business),
    )

    assert {o["status"] for o in response.json()["items"]} == {"pending", "assigned"}
    assert response.json()["total"] == 2


async def test_search_and_overdue_filters(client: AsyncClient, db_session: AsyncSession) -> None:
    business = await create_business(db_session)
    await create_order(db_session, business, customer_name="Zainab Raza")
    await create_order(db_session, business, customer_name="Ali_Raza", is_overdue=True)
    await create_order(db_session, business, customer_name="Omar Farooq")
    await db_session.commit()
    headers = business_headers(business)

    async def names(**params: Any) -> set[str]:
        response = await client.get("/orders", params=params, headers=headers)
        return {o["customer_name"] for o in response.json()["items"]}

    assert await names(search="raza") == {"Zainab Raza", "Ali_Raza"}
    # "_" is matched literally, not as a SQL wildcard.
    assert await names(search="i_r") == {"Ali_Raza"}
    assert await names(is_overdue="true") == {"Ali_Raza"}


async def test_created_date_range_filter(client: AsyncClient, db_session: AsyncSession) -> None:
    business = await create_business(db_session)
    old = await create_order(db_session, business)
    new = await create_order(db_session, business)
    old.created_at = datetime.now(UTC) - timedelta(days=10)
    await db_session.commit()

    response = await client.get(
        "/orders",
        params={"created_from": (datetime.now(UTC) - timedelta(days=1)).isoformat()},
        headers=business_headers(business),
    )

    assert [o["id"] for o in response.json()["items"]] == [str(new.id)]


async def test_sort_by_deadline(client: AsyncClient, db_session: AsyncSession) -> None:
    business = await create_business(db_session)
    now = datetime.now(UTC)
    late = await create_order(db_session, business, deliver_by=now + timedelta(hours=3))
    soon = await create_order(db_session, business, deliver_by=now + timedelta(minutes=20))
    await db_session.commit()

    response = await client.get(
        "/orders", params={"sort": "deliver_by"}, headers=business_headers(business)
    )

    assert [o["id"] for o in response.json()["items"]] == [str(soon.id), str(late.id)]


@pytest.mark.parametrize(
    "params",
    [{"page_size": 101}, {"page": 0}, {"status": "lost"}, {"sort": "name"}, {"colour": "red"}],
)
async def test_invalid_list_params(
    client: AsyncClient, db_session: AsyncSession, params: dict[str, Any]
) -> None:
    business = await create_business(db_session)
    await db_session.commit()

    response = await client.get("/orders", params=params, headers=business_headers(business))

    assert response.status_code == 422


# --- Cancel ----------------------------------------------------------------------


async def test_business_cancels_pending_order(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    business = await create_business(db_session)
    order = await create_order(db_session, business)
    await db_session.commit()

    response = await client.post(
        f"/orders/{order.id}/cancel",
        json={"reason": "Customer changed mind"},
        headers=business_headers(business),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "failed"
    assert body["failure_reason"] == "Cancelled by business: Customer changed mind"
    assert body["failed_at"] is not None

    again = await client.post(f"/orders/{order.id}/cancel", headers=business_headers(business))
    assert again.status_code == 409


async def test_cancelling_assigned_order_releases_driver(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    business = await create_business(db_session)
    driver = await create_driver(db_session)
    order = await create_order(db_session, business)
    await assign_order(db_session, order, driver)
    await db_session.commit()

    response = await client.post(f"/orders/{order.id}/cancel", headers=business_headers(business))

    assert response.status_code == 200
    assert (
        await db_session.get(Driver, driver.id, populate_existing=True)
    ).status == DriverStatus.AVAILABLE
    assignment = await db_session.scalar(
        select(OrderAssignment).where(OrderAssignment.order_id == order.id)
    )
    assert assignment.status == AssignmentStatus.FAILED
    assert assignment.ended_at is not None


async def test_business_cannot_cancel_after_pickup_but_admin_can(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    business = await create_business(db_session)
    driver = await create_driver(db_session)
    order = await create_order(db_session, business)
    await assign_order(db_session, order, driver, accepted=True)
    order.status = OrderStatus.PICKED_UP
    order.picked_up_at = datetime.now(UTC)
    headers = await admin_headers(db_session)

    as_business = await client.post(
        f"/orders/{order.id}/cancel", headers=business_headers(business)
    )
    assert as_business.status_code == 409

    as_admin = await client.post(
        f"/orders/{order.id}/cancel", json={"reason": "Damaged parcel"}, headers=headers
    )
    assert as_admin.status_code == 200
    assert as_admin.json()["failure_reason"] == "Cancelled by admin: Damaged parcel"

    stored = await db_session.get(Order, order.id, populate_existing=True)
    assert stored.status == OrderStatus.FAILED
    assert stored.driver_id == driver.id  # kept for history


async def test_cancel_permissions(client: AsyncClient, db_session: AsyncSession) -> None:
    shop_a, shop_b = await create_business(db_session), await create_business(db_session)
    driver = await create_driver(db_session)
    order = await create_order(db_session, shop_b)
    await assign_order(db_session, order, driver)
    await db_session.commit()

    other_business = await client.post(
        f"/orders/{order.id}/cancel", headers=business_headers(shop_a)
    )
    assert other_business.status_code == 404

    as_driver = await client.post(f"/orders/{order.id}/cancel", headers=driver_headers(driver))
    assert as_driver.status_code == 403
