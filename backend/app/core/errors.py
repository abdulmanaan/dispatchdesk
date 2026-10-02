"""Domain exceptions and their translation into HTTP responses.

Services raise these instead of ``HTTPException`` so business logic stays
independent of the web layer. A single handler maps them to status codes.
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse


class DomainError(Exception):
    status_code: int = status.HTTP_400_BAD_REQUEST

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class NotFoundError(DomainError):
    status_code = status.HTTP_404_NOT_FOUND


class PermissionDeniedError(DomainError):
    status_code = status.HTTP_403_FORBIDDEN


class ConflictError(DomainError):
    """The request is valid but conflicts with the resource's current state."""

    status_code = status.HTTP_409_CONFLICT


async def _domain_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, DomainError)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, _domain_error_handler)
