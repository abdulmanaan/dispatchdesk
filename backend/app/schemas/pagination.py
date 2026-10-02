"""Generic paginated response."""

import math
from collections.abc import Sequence

from pydantic import BaseModel

MAX_PAGE_SIZE = 100


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
