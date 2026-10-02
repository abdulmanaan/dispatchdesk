"""Admin endpoints to trigger dispatch manually."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import AdminUser, DbSession
from app.core.errors import ConflictError, NotFoundError
from app.schemas.dispatch import DispatchOrderResponse, DispatchResultRead, DispatchRunResponse
from app.schemas.order import OrderRead
from app.services import dispatch
from app.services import orders as order_service
from app.services.dispatch import DispatchOutcome

router = APIRouter(prefix="/dispatch", tags=["dispatch"])


@router.post("/orders/{order_id}", response_model=DispatchOrderResponse)
async def dispatch_order(
    order_id: uuid.UUID, admin: AdminUser, session: DbSession
) -> DispatchOrderResponse:
    """Try to assign one pending order now. ``outcome`` explains what happened."""
    result = await dispatch.try_dispatch_order(session, order_id, actor=admin)
    if result.outcome == DispatchOutcome.NOT_FOUND:
        raise NotFoundError("Order not found")
    if result.outcome == DispatchOutcome.NOT_PENDING:
        raise ConflictError("Only pending orders can be dispatched")
    order = await order_service.get_order(session, admin, order_id)
    await session.refresh(order)
    return DispatchOrderResponse(
        result=DispatchResultRead.model_validate(result), order=OrderRead.model_validate(order)
    )


@router.post("/run", response_model=DispatchRunResponse)
async def run_dispatch(
    admin: AdminUser,
    session: DbSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> DispatchRunResponse:
    """Try to assign up to ``limit`` pending orders, most urgent first."""
    results = await dispatch.dispatch_pending_orders(session, limit=limit, actor=admin)
    return DispatchRunResponse(
        attempted=len(results),
        assigned=sum(r.outcome == DispatchOutcome.ASSIGNED for r in results),
        results=[DispatchResultRead.model_validate(r) for r in results],
    )
