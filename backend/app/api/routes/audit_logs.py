"""Audit log browsing."""

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import AdminUser, DbSession
from app.schemas.audit import AuditLogListParams, AuditLogRead
from app.schemas.pagination import Page
from app.services import audit

router = APIRouter(prefix="/audit-logs", tags=["audit"])


@router.get("", response_model=Page[AuditLogRead])
async def list_audit_logs(
    params: Annotated[AuditLogListParams, Query()], _admin: AdminUser, session: DbSession
) -> Page[AuditLogRead]:
    """Browse the audit trail, newest first (admin only).

    ``action`` matches exactly, or as a prefix when it ends with ``.`` (e.g. ``order.``).
    """
    items, total = await audit.list_entries(session, params)
    return Page[AuditLogRead].build(
        [AuditLogRead.model_validate(i) for i in items],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )
