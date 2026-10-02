"""Pagination: shared query parameters and a generic paginated response."""

import math
from collections.abc import Sequence
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

MAX_PAGE_SIZE = 100


class PageParams(BaseModel):
    """Base for list query parameters. Unknown parameters are rejected."""

    model_config = ConfigDict(extra="forbid")

    page: Annotated[int, Field(ge=1)] = 1
    page_size: Annotated[int, Field(ge=1, le=MAX_PAGE_SIZE)] = 20

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class Page[T](BaseModel):
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int

    @classmethod
    def build(cls, items: Sequence[T], *, total: int, page: int, page_size: int) -> "Page[T]":
        return cls(
            items=list(items),
            total=total,
            page=page,
            page_size=page_size,
            pages=math.ceil(total / page_size) if total else 0,
        )
