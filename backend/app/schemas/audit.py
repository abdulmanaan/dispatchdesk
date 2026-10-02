"""Schemas for audit log entries."""

import uuid
from datetime import datetime
from typing import Annotated, Any

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.schemas.pagination import PageParams


class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    actor_id: uuid.UUID | None  # None means the system (dispatch, background jobs)
    actor_email: str | None = None
    actor_name: str | None = None
    action: str
    entity_type: str
    entity_id: str | None
    details: dict[str, Any]
    created_at: datetime


class AuditLogListParams(PageParams):
    # Exact action ("order.assigned") or a prefix ending in "." ("order.").
    action: Annotated[str, Field(max_length=64)] | None = None
    entity_type: Annotated[str, Field(max_length=32)] | None = None
    entity_id: Annotated[str, Field(max_length=64)] | None = None
    actor_id: uuid.UUID | None = None
    created_from: AwareDatetime | None = None
    created_to: AwareDatetime | None = None
