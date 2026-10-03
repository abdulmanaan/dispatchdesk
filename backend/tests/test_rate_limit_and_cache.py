"""Tests for Redis-backed rate limiting and caching, including Redis outages."""

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import redis as redis_module
from app.core.config import get_settings
from app.core.redis import get_redis
from app.main import app
from app.models.enums import OrderStatus, UserRole
from tests.factories import auth_headers, create_business, create_order, create_user


def client_from(ip: str, **headers: str) -> AsyncClient:
    transport = ASGITransport(app=app, client=(ip, 12345))
    return AsyncClient(transport=transport, base_url="http://test", headers=headers)


async def login(client: AsyncClient):
    return await client.post("/auth/login", data={"username": "x@example.com", "password": "x"})


@pytest.fixture
def low_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "rate_limit_auth_per_minute", 3)
    monkeypatch.setattr(settings, "rate_limit_default_per_minute", 5)


@pytest.fixture
async def redis_down(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[None]:
    """Point the client at a port where nothing listens."""
    await redis_module.close_redis()
    monkeypatch.setattr(get_settings(), "redis_url", "redis://localhost:6390/0")
    yield
    await redis_module.close_redis()


# --- Rate limiting ---------------------------------------------------------------


@pytest.mark.usefixtures("low_limits")
async def test_login_is_limited_per_ip() -> None:
    async with client_from("10.0.0.1") as attacker, client_from("10.0.0.2") as neighbour:
        codes = [(await login(attacker)).status_code for _ in range(4)]
        blocked = await login(attacker)
        other_ip = await login(neighbour)

    assert codes == [401, 401, 401, 429]
    assert blocked.status_code == 429
    assert 0 < int(blocked.headers["retry-after"]) <= 60
    assert blocked.headers["x-ratelimit-remaining"] == "0"
    assert other_ip.status_code == 401  # a different IP has its own budget


@pytest.mark.usefixtures("low_limits")
async def test_api_limit_is_per_user(db_session: AsyncSession) -> None:
    alice = await create_user(db_session, UserRole.ADMIN)
    bob = await create_user(db_session, UserRole.ADMIN)
    await db_session.commit()

    # Both users share one IP (e.g. an office network) but have separate budgets.
    async with client_from("10.0.0.9") as client:
        alice_codes = [
            (
                await client.get("/auth/me", headers=auth_headers(alice.id, UserRole.ADMIN))
            ).status_code
            for _ in range(6)
        ]
        bob_response = await client.get("/auth/me", headers=auth_headers(bob.id, UserRole.ADMIN))

    assert alice_codes == [200] * 5 + [429]
    assert bob_response.status_code == 200
    assert bob_response.headers["x-ratelimit-limit"] == "5"
    assert bob_response.headers["x-ratelimit-remaining"] == "4"


@pytest.mark.usefixtures("low_limits")
async def test_health_is_not_rate_limited() -> None:
    async with client_from("10.0.0.3") as client:
        codes = {(await client.get("/health")).status_code for _ in range(10)}

    assert codes == {200}


async def burst(client: AsyncClient, forwarded_for: list[str]) -> list[int]:
    """One login attempt per X-Forwarded-For value."""
    return [
        (
            await client.post(
                "/auth/login",
                data={"username": "x@example.com", "password": "x"},
                headers={"X-Forwarded-For": value},
            )
        ).status_code
        for value in forwarded_for
    ]


@pytest.mark.usefixtures("low_limits")
async def test_forwarded_for_is_ignored_without_trusted_proxies() -> None:
    async with client_from("10.0.0.4") as client:
        # Rotating the header does not bypass the limit.
        codes = await burst(client, ["1.1.1.1", "2.2.2.2", "3.3.3.3", "4.4.4.4"])

    assert codes[-1] == 429


@pytest.mark.usefixtures("low_limits")
async def test_behind_one_proxy_each_client_has_its_own_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "trusted_proxy_hops", 1)

    async with client_from("10.0.0.5") as proxy:
        # Four different visitors behind the same proxy: none is limited.
        visitors = await burst(proxy, ["203.0.113.1", "203.0.113.2", "203.0.113.3", "203.0.113.4"])
        # One visitor faking a new IP each time: the proxy appends the real one last,
        # so the fake left-hand values are ignored and the limit still applies.
        spoofer = await burst(proxy, [f"6.6.6.{n}, 198.51.100.9" for n in range(4)])

    assert 429 not in visitors
    assert spoofer[-1] == 429


@pytest.mark.usefixtures("low_limits", "redis_down")
async def test_requests_succeed_when_redis_is_down() -> None:
    async with client_from("10.0.0.6") as client:
        codes = [(await login(client)).status_code for _ in range(6)]

    assert set(codes) == {401}  # limits off, endpoint itself still works


async def test_rate_limiting_can_be_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "rate_limit_enabled", False)
    monkeypatch.setattr(get_settings(), "rate_limit_auth_per_minute", 1)

    async with client_from("10.0.0.7") as client:
        codes = [(await login(client)).status_code for _ in range(3)]

    assert codes == [401, 401, 401]


# --- Stats cache -----------------------------------------------------------------


async def admin_client(session: AsyncSession) -> AsyncClient:
    admin = await create_user(session, UserRole.ADMIN)
    await session.commit()
    return client_from("10.1.0.1", **auth_headers(admin.id, UserRole.ADMIN))


async def test_stats_are_cached_briefly(db_session: AsyncSession) -> None:
    business = await create_business(db_session)
    await create_order(db_session, business)
    async with await admin_client(db_session) as client:
        first = await client.get("/stats/overview")

        await create_order(db_session, business)
        await db_session.commit()
        second = await client.get("/stats/overview")

        await get_redis().delete("cache:stats:overview")  # simulate TTL expiry
        third = await client.get("/stats/overview")

    assert first.headers["x-cache"] == "MISS"
    assert second.headers["x-cache"] == "HIT"
    assert third.headers["x-cache"] == "MISS"
    assert first.json()["orders_by_status"]["pending"] == 1
    assert second.json()["orders_by_status"]["pending"] == 1  # served from cache
    assert third.json()["orders_by_status"]["pending"] == 2
    ttl = await get_redis().ttl("cache:stats:overview")
    assert 0 < ttl <= get_settings().cache_stats_ttl_seconds


@pytest.mark.usefixtures("redis_down")
async def test_stats_work_without_redis(db_session: AsyncSession) -> None:
    async with await admin_client(db_session) as client:
        responses = [await client.get("/stats/overview") for _ in range(2)]

    assert [r.status_code for r in responses] == [200, 200]
    assert {r.headers["x-cache"] for r in responses} == {"MISS"}


async def test_stats_content(db_session: AsyncSession) -> None:
    from datetime import UTC, datetime, timedelta

    from tests.factories import add_driver

    business = await create_business(db_session)
    driver = await add_driver(db_session, 1)
    now = datetime.now(UTC)
    common = {"driver_id": driver.id, "assigned_at": now, "accepted_at": now, "picked_up_at": now}
    await create_order(
        db_session,
        business,
        status=OrderStatus.DELIVERED,
        delivered_at=now,
        deliver_by=now + timedelta(minutes=5),
        **common,
    )
    await create_order(
        db_session,
        business,
        status=OrderStatus.DELIVERED,
        delivered_at=now,
        deliver_by=now - timedelta(minutes=5),
        **common,
    )
    await create_order(db_session, business, is_overdue=True)

    async with await admin_client(db_session) as client:
        body = (await client.get("/stats/overview")).json()

    assert body["orders_by_status"] == {
        "pending": 1,
        "assigned": 0,
        "picked_up": 0,
        "delivered": 2,
        "failed": 0,
    }
    assert body["drivers_by_status"]["available"] == 1
    assert body["overdue_open_orders"] == 1
    assert body["last_24h"]["delivered"] == 2
    assert body["last_24h"]["on_time_rate"] == 0.5
    assert body["last_24h"]["avg_delivery_minutes"] is not None


async def test_stats_are_admin_only(db_session: AsyncSession) -> None:
    business = await create_business(db_session)
    await db_session.commit()

    async with client_from("10.1.0.2", **auth_headers(business.owner_id, UserRole.BUSINESS)) as c:
        assert (await c.get("/stats/overview")).status_code == 403
