"""Tests for audit log browsing and order timelines."""

from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog
from app.models.enums import UserRole
from app.services.dispatch import try_dispatch_order
from tests.factories import (
    add_driver,
    auth_headers,
    business_headers,
    create_business,
    create_order,
    create_user,
    driver_headers,
)


async def admin_headers(session: AsyncSession) -> dict[str, str]:
    admin = await create_user(session, UserRole.ADMIN, email="boss@dispatchdesk.pk")
    await session.commit()
    return auth_headers(admin.id, UserRole.ADMIN)


async def test_order_timeline_through_the_api(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    business = await create_business(db_session)
    driver = await add_driver(db_session, 1)
    await db_session.commit()
    created = await client.post(
        "/orders",
        json={
            "customer_name": "Saad",
            "customer_phone": "+923001234000",
            "dropoff_address": "Cantt, Lahore",
            "dropoff_lat": 31.52,
            "dropoff_lng": 74.38,
        },
        headers=business_headers(business),
    )
    order_id = created.json()["id"]
    for action in ("accept", "pickup", "deliver"):
        await client.post(f"/orders/{order_id}/{action}", headers=driver_headers(driver))

    timeline = await client.get(f"/orders/{order_id}/events", headers=business_headers(business))

    assert timeline.status_code == 200
    events = timeline.json()
    assert [e["action"] for e in events] == [
        "order.created",
        "order.assigned",
        "order.accepted",
        "order.picked_up",
        "order.delivered",
    ]
    assert events[0]["actor_email"] is not None  # the business owner
    assert events[0]["actor_name"] == "Test User"
    assert events[1]["actor_id"] is None  # automatic dispatch
    assert events[1]["details"]["driver_id"] == str(driver.id)


async def test_order_timeline_respects_visibility(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    owner, stranger = await create_business(db_session), await create_business(db_session)
    order = await create_order(db_session, owner)
    await db_session.commit()

    response = await client.get(f"/orders/{order.id}/events", headers=business_headers(stranger))

    assert response.status_code == 404


async def test_admin_browses_and_filters_audit_logs(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    business = await create_business(db_session)
    await add_driver(db_session, 1)
    order = await create_order(db_session, business)
    old = datetime.now(UTC) - timedelta(days=3)
    db_session.add_all(
        [
            AuditLog(action="order.created", entity_type="order", entity_id=str(order.id)),
            AuditLog(action="driver.status_changed", entity_type="driver", entity_id="d1"),
            AuditLog(
                action="order.overdue", entity_type="order", entity_id="o-old", created_at=old
            ),
        ]
    )
    await db_session.commit()
    await try_dispatch_order(db_session, order.id)  # adds "order.assigned"
    headers = await admin_headers(db_session)

    async def query(**params: str) -> dict:
        response = await client.get("/audit-logs", params=params, headers=headers)
        assert response.status_code == 200, response.text
        return response.json()

    everything = await query()
    assert everything["total"] == 4
    assert everything["items"][0]["action"] == "order.assigned"  # newest first

    assert (await query(action="order."))["total"] == 3  # prefix match
    assert (await query(action="order.assigned"))["total"] == 1
    assert (await query(entity_type="driver"))["total"] == 1
    assert (await query(entity_id=str(order.id)))["total"] == 2
    recent = await query(created_from=(datetime.now(UTC) - timedelta(days=1)).isoformat())
    assert recent["total"] == 3
    assert (await query(page_size="2", page="2"))["items"][0]["id"] > 0


async def test_prefix_filter_escapes_wildcards(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    db_session.add_all(
        [
            AuditLog(action="order.created", entity_type="order", entity_id="1"),
            AuditLog(action="orderXcreated", entity_type="order", entity_id="2"),
        ]
    )
    headers = await admin_headers(db_session)

    response = await client.get("/audit-logs", params={"action": "order_"}, headers=headers)
    # "order_" does not end with "." so it is an exact match, and matches nothing.
    assert response.json()["total"] == 0


async def test_audit_logs_are_admin_only(client: AsyncClient, db_session: AsyncSession) -> None:
    business = await create_business(db_session)
    await db_session.commit()

    response = await client.get("/audit-logs", headers=business_headers(business))

    assert response.status_code == 403
