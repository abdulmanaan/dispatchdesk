"""Driver endpoints: self-service for drivers, listing for admins."""

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import AdminUser, DbSession, DriverUser
from app.models import Driver, Order
from app.models.enums import DriverStatus
from app.schemas.driver import DriverAdminRead, DriverListParams, DriverStatusUpdate, LocationUpdate
from app.schemas.order import OrderRead
from app.schemas.pagination import Page
from app.schemas.user import DriverRead
from app.services import dispatch
from app.services import drivers as driver_service
from app.services import orders as order_service

router = APIRouter(prefix="/drivers", tags=["drivers"])


@router.get("", response_model=Page[DriverAdminRead])
async def list_drivers(
    params: Annotated[DriverListParams, Query()], _admin: AdminUser, session: DbSession
) -> Page[DriverAdminRead]:
    """List drivers with their status, location and current active order (admin only)."""
    items, total = await driver_service.list_drivers(session, params)
    return Page[DriverAdminRead].build(
        [DriverAdminRead.model_validate(i) for i in items],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


@router.put("/me/status", response_model=DriverRead)
async def set_my_status(data: DriverStatusUpdate, user: DriverUser, session: DbSession) -> Driver:
    """Go available or offline. Not allowed while holding an active order.

    Going available triggers dispatch, so the response may already show ``busy``.
    """
    driver = await driver_service.set_status(session, user, data)
    if driver.status == DriverStatus.AVAILABLE:
        await dispatch.dispatch_quietly(session)
        await session.refresh(driver)
    return driver


@router.put("/me/location", response_model=DriverRead)
async def update_my_location(data: LocationUpdate, user: DriverUser, session: DbSession) -> Driver:
    return await driver_service.update_location(session, user, data)


@router.get("/me/order", response_model=OrderRead | None)
async def get_my_current_order(user: DriverUser, session: DbSession) -> Order | None:
    """The order the driver is currently working on, or null."""
    assert user.driver is not None
    return await order_service.get_current_order(session, user.driver.id)
