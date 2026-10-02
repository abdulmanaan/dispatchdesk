"""The order lifecycle state machine.

    pending ──▶ assigned ──▶ picked_up ──▶ delivered
       │  ▲        │              │
       │  └────────┤ (unassigned / reassigned)
       ▼           ▼              ▼
     failed ◀──────┴──────────────┘

Acceptance is not a separate status: an ``assigned`` order is accepted when
``accepted_at`` is set, and only accepted orders can be picked up.

These functions only mutate the ``Order`` in memory. Callers are responsible
for locking, persistence, driver status and assignment history.
"""

import uuid
from datetime import datetime

from app.core.errors import ConflictError
from app.models import Order
from app.models.enums import OrderStatus

ALLOWED_TRANSITIONS: dict[OrderStatus, frozenset[OrderStatus]] = {
    OrderStatus.PENDING: frozenset({OrderStatus.ASSIGNED, OrderStatus.FAILED}),
    OrderStatus.ASSIGNED: frozenset(
        {OrderStatus.PENDING, OrderStatus.PICKED_UP, OrderStatus.FAILED}
    ),
    OrderStatus.PICKED_UP: frozenset({OrderStatus.DELIVERED, OrderStatus.FAILED}),
    OrderStatus.DELIVERED: frozenset(),
    OrderStatus.FAILED: frozenset(),
}

TERMINAL_STATUSES = frozenset(s for s, targets in ALLOWED_TRANSITIONS.items() if not targets)


class InvalidTransitionError(ConflictError):
    pass


def can_transition(current: OrderStatus, target: OrderStatus) -> bool:
    return target in ALLOWED_TRANSITIONS[current]


def assign(order: Order, driver_id: uuid.UUID, *, now: datetime) -> None:
    """pending -> assigned: hand the order to a driver, awaiting acceptance."""
    _check(order, OrderStatus.ASSIGNED)
    order.status = OrderStatus.ASSIGNED
    order.driver_id = driver_id
    order.assigned_at = now
    order.accepted_at = None
    order.assignment_attempts += 1


def accept(order: Order, *, now: datetime) -> None:
    """Driver confirms an assigned order. The status stays ``assigned``."""
    if order.status != OrderStatus.ASSIGNED:
        raise InvalidTransitionError(
            f"Only assigned orders can be accepted (order is {order.status})"
        )
    if order.accepted_at is not None:
        raise InvalidTransitionError("Order has already been accepted")
    order.accepted_at = now


def unassign(order: Order) -> None:
    """assigned -> pending: take the order back from its driver (e.g. acceptance timeout)."""
    _check(order, OrderStatus.PENDING)
    order.status = OrderStatus.PENDING
    order.driver_id = None
    order.assigned_at = None
    order.accepted_at = None


def pick_up(order: Order, *, now: datetime) -> None:
    """assigned -> picked_up: driver collected the parcel. Requires prior acceptance."""
    _check(order, OrderStatus.PICKED_UP)
    if order.accepted_at is None:
        raise InvalidTransitionError("Order must be accepted before it can be picked up")
    order.status = OrderStatus.PICKED_UP
    order.picked_up_at = now


def deliver(order: Order, *, now: datetime) -> None:
    """picked_up -> delivered."""
    _check(order, OrderStatus.DELIVERED)
    order.status = OrderStatus.DELIVERED
    order.delivered_at = now


def fail(order: Order, *, reason: str, now: datetime) -> None:
    """Any open status -> failed. The driver (if any) is kept for history."""
    _check(order, OrderStatus.FAILED)
    if not reason.strip():
        raise ValueError("A failure reason is required")
    order.status = OrderStatus.FAILED
    order.failed_at = now
    order.failure_reason = reason[:255]


def _check(order: Order, target: OrderStatus) -> None:
    if not can_transition(order.status, target):
        raise InvalidTransitionError(f"Cannot move order from {order.status} to {target}")
