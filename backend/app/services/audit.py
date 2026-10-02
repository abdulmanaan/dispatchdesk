"""Audit trail helper.

Entries are added to the caller's session, so they are committed (or rolled
back) atomically with the change they describe.
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, User


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
