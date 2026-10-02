"""Unit tests for the order lifecycle state machine (no database needed)."""

import uuid
from datetime import UTC, datetime

import pytest

from app.models import Order
from app.models.enums import OrderStatus
from app.services import order_state
from app.services.order_state import ALLOWED_TRANSITIONS, InvalidTransitionError

NOW = datetime(2026, 10, 3, 12, 0, tzinfo=UTC)
DRIVER_ID = uuid.uuid4()


def make_order(status: OrderStatus = OrderStatus.PENDING, **fields: object) -> Order:
    order = Order(status=status, assignment_attempts=0, **fields)
    if status != OrderStatus.PENDING:
        order.driver_id = DRIVER_ID
        order.assigned_at = NOW
    if status in (OrderStatus.PICKED_UP, OrderStatus.DELIVERED):
        order.accepted_at = NOW
    return order


def run(order: Order, target: OrderStatus) -> None:
    """Drive a single transition through the matching state machine function."""
    match target:
        case OrderStatus.ASSIGNED:
            order_state.assign(order, DRIVER_ID, now=NOW)
        case OrderStatus.PENDING:
            order_state.unassign(order)
        case OrderStatus.PICKED_UP:
            order_state.pick_up(order, now=NOW)
        case OrderStatus.DELIVERED:
            order_state.deliver(order, now=NOW)
        case OrderStatus.FAILED:
            order_state.fail(order, reason="test", now=NOW)


ALL_PAIRS = [(src, dst) for src in OrderStatus for dst in OrderStatus if src != dst]


@pytest.mark.parametrize(("source", "target"), ALL_PAIRS)
def test_transition_matrix(source: OrderStatus, target: OrderStatus) -> None:
    """Every allowed transition succeeds and every other one is rejected."""
    order = make_order(source, accepted_at=NOW)

    if target in ALLOWED_TRANSITIONS[source]:
        run(order, target)
        assert order.status == target
    else:
        with pytest.raises(InvalidTransitionError):
            run(order, target)
        assert order.status == source


def test_terminal_statuses() -> None:
    assert {OrderStatus.DELIVERED, OrderStatus.FAILED} == order_state.TERMINAL_STATUSES


def test_assign_sets_driver_and_counts_attempts() -> None:
    order = make_order()

    order_state.assign(order, DRIVER_ID, now=NOW)

    assert order.driver_id == DRIVER_ID
    assert order.assigned_at == NOW
    assert order.accepted_at is None
    assert order.assignment_attempts == 1


def test_unassign_clears_driver_but_keeps_attempt_count() -> None:
    order = make_order()
    order_state.assign(order, DRIVER_ID, now=NOW)

    order_state.unassign(order)

    assert order.status == OrderStatus.PENDING
    assert order.driver_id is None
    assert order.assigned_at is None
    assert order.assignment_attempts == 1


def test_accept_then_pick_up_then_deliver() -> None:
    order = make_order()
    order_state.assign(order, DRIVER_ID, now=NOW)

    order_state.accept(order, now=NOW)
    assert order.status == OrderStatus.ASSIGNED
    assert order.accepted_at == NOW

    order_state.pick_up(order, now=NOW)
    order_state.deliver(order, now=NOW)
    assert order.status == OrderStatus.DELIVERED
    assert order.picked_up_at == NOW and order.delivered_at == NOW


def test_pick_up_requires_acceptance() -> None:
    order = make_order()
    order_state.assign(order, DRIVER_ID, now=NOW)

    with pytest.raises(InvalidTransitionError, match="accepted"):
        order_state.pick_up(order, now=NOW)


@pytest.mark.parametrize(
    "status", [OrderStatus.PENDING, OrderStatus.PICKED_UP, OrderStatus.DELIVERED]
)
def test_accept_only_from_assigned(status: OrderStatus) -> None:
    with pytest.raises(InvalidTransitionError):
        order_state.accept(make_order(status), now=NOW)


def test_accept_twice_is_rejected() -> None:
    order = make_order()
    order_state.assign(order, DRIVER_ID, now=NOW)
    order_state.accept(order, now=NOW)

    with pytest.raises(InvalidTransitionError, match="already"):
        order_state.accept(order, now=NOW)


def test_fail_keeps_driver_and_requires_reason() -> None:
    order = make_order(OrderStatus.PICKED_UP)

    with pytest.raises(ValueError):
        order_state.fail(order, reason="  ", now=NOW)

    order_state.fail(order, reason="Customer unreachable", now=NOW)
    assert order.status == OrderStatus.FAILED
    assert order.driver_id == DRIVER_ID
    assert order.failure_reason == "Customer unreachable"
