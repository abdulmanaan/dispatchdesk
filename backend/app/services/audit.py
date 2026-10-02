"""Audit trail helper.

Entries are added to the caller's session, so they are committed (or rolled
back) atomically with the change they describe.
"""

from collections.abc import Sequence
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, User
from app.schemas.audit import AuditLogListParams


def record(
    session: AsyncSession,
    *,
    actor: User | None,
    action: str,
    entity_type: str,
    entity_id: object,
    details: dict[str, Any] | None = None,
) -> None:
    """Queue an audit entry. ``actor=None`` means the system (e.g. a background job)."""
    session.add(
        AuditLog(
            actor_id=actor.id if actor else None,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id),
            details=details or {},
        )
    )


def _with_actor_email(stmt: Select) -> Select:
    return stmt.add_columns(User.email).outerjoin(User, User.id == AuditLog.actor_id)


def _to_dict(entry: AuditLog, actor_email: str | None) -> dict[str, Any]:
    return {c.key: getattr(entry, c.key) for c in AuditLog.__table__.columns} | {
        "actor_email": actor_email
    }


async def list_entries(
    session: AsyncSession, params: AuditLogListParams
) -> tuple[Sequence[dict[str, Any]], int]:
    """One page of audit entries, newest first."""
    conditions = []
    if params.action:
        if params.action.endswith("."):
            conditions.append(AuditLog.action.startswith(params.action, autoescape=True))
        else:
            conditions.append(AuditLog.action == params.action)
    if params.entity_type:
        conditions.append(AuditLog.entity_type == params.entity_type)
    if params.entity_id:
        conditions.append(AuditLog.entity_id == params.entity_id)
    if params.actor_id:
        conditions.append(AuditLog.actor_id == params.actor_id)
    if params.created_from:
        conditions.append(AuditLog.created_at >= params.created_from)
    if params.created_to:
        conditions.append(AuditLog.created_at < params.created_to)

    total = await session.scalar(select(func.count()).select_from(AuditLog).where(*conditions))
    rows = await session.execute(
        _with_actor_email(select(AuditLog))
        .where(*conditions)
        .order_by(AuditLog.id.desc())
        .offset(params.offset)
        .limit(params.page_size)
    )
    return [_to_dict(entry, email) for entry, email in rows.all()], total or 0


async def entity_history(
    session: AsyncSession, entity_type: str, entity_id: object
) -> list[dict[str, Any]]:
    """All entries for one entity, oldest first (a timeline)."""
    rows = await session.execute(
        _with_actor_email(select(AuditLog))
        .where(AuditLog.entity_type == entity_type, AuditLog.entity_id == str(entity_id))
        .order_by(AuditLog.id)
    )
    return [_to_dict(entry, email) for entry, email in rows.all()]
