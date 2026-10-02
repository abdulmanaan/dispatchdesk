"""Order endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import BusinessUser, CurrentUser, DbSession, DriverUser, require_roles
from app.models import Order, User
from app.models.enums import UserRole
from app.schemas.order import OrderCancel, OrderCreate, OrderFail, OrderListParams, OrderRead
from app.schemas.pagination import Page
from app.services import dispatch
from app.services import orders as order_service

router = APIRouter(prefix="/orders", tags=["orders"])

AdminOrBusiness = Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.BUSINESS))]


@router.post("", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
async def create_order(data: OrderCreate, user: BusinessUser, session: DbSession) -> Order:
    """Create a delivery order for the signed-in business.

    The order is dispatched immediately if a suitable driver is available, so the
    response may already show it as ``assigned``. Otherwise it stays ``pending``.
    """
    order = await order_service.create_order(session, user, data)
    await dispatch.dispatch_quietly(session, order.id)
    await session.refresh(order)
    return order


@router.get("", response_model=Page[OrderRead])
async def list_orders(
    params: Annotated[OrderListParams, Query()], user: CurrentUser, session: DbSession
) -> Page[OrderRead]:
    """List orders visible to the caller, with filters and pagination.

    Admins see all orders, businesses their own, drivers those assigned to them.
    """
    items, total = await order_service.list_orders(session, user, params)
    return Page[OrderRead].build(
        [OrderRead.model_validate(o) for o in items],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


@router.get("/{order_id}", response_model=OrderRead)
async def get_order(order_id: uuid.UUID, user: CurrentUser, session: DbSession) -> Order:
    return await order_service.get_order(session, user, order_id)


@router.post("/{order_id}/cancel", response_model=OrderRead)
async def cancel_order(
    order_id: uuid.UUID,
    user: AdminOrBusiness,
    session: DbSession,
    data: OrderCancel | None = None,
) -> Order:
    """Cancel an open order. Businesses can cancel only before pickup."""
    return await order_service.cancel_order(session, user, order_id, data.reason if data else None)


# --- Driver actions --------------------------------------------------------------


@router.post("/{order_id}/accept", response_model=OrderRead)
async def accept_order(order_id: uuid.UUID, user: DriverUser, session: DbSession) -> Order:
    """Accept an order assigned to you. Unaccepted orders are reassigned after a timeout."""
    return await order_service.accept_order(session, user, order_id)


@router.post("/{order_id}/pickup", response_model=OrderRead)
async def pick_up_order(order_id: uuid.UUID, user: DriverUser, session: DbSession) -> Order:
    """Confirm you collected the order from the pickup location."""
    return await order_service.pick_up_order(session, user, order_id)


@router.post("/{order_id}/deliver", response_model=OrderRead)
async def deliver_order(order_id: uuid.UUID, user: DriverUser, session: DbSession) -> Order:
    """Confirm delivery. You become available and may be assigned the next order."""
    order = await order_service.deliver_order(session, user, order_id)
    await dispatch.dispatch_quietly(session)
    await session.refresh(order)
    return order


@router.post("/{order_id}/fail", response_model=OrderRead)
async def fail_order(
    order_id: uuid.UUID, data: OrderFail, user: DriverUser, session: DbSession
) -> Order:
    """Report that the delivery cannot be completed. You become available again."""
    order = await order_service.fail_order(session, user, order_id, data.reason)
    await dispatch.dispatch_quietly(session)
    await session.refresh(order)
    return order
