"""Order endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import BusinessUser, CurrentUser, DbSession, require_roles
from app.models import Order, User
from app.models.enums import UserRole
from app.schemas.order import OrderCancel, OrderCreate, OrderListParams, OrderRead
from app.schemas.pagination import Page
from app.services import orders as order_service

router = APIRouter(prefix="/orders", tags=["orders"])

AdminOrBusiness = Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.BUSINESS))]


@router.post("", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
async def create_order(data: OrderCreate, user: BusinessUser, session: DbSession) -> Order:
    """Create a delivery order for the signed-in business."""
    return await order_service.create_order(session, user, data)


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
