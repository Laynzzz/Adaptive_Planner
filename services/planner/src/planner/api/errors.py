"""Stable public errors without internal details."""

from uuid import uuid4

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class APIError(Exception):
    def __init__(self, code: str, status: int, message: str, *, retryable: bool = False):
        self.code, self.status, self.message, self.retryable = code, status, message, retryable


def install_error_handlers(app):
    @app.exception_handler(APIError)
    async def api_error(request: Request, error: APIError):
        correlation_id = str(uuid4())
        return JSONResponse(
            {
                "code": error.code,
                "message": error.message,
                "field_ids": [],
                "related_ids": [],
                "retryable": error.retryable,
                "correlation_id": correlation_id,
            },
            status_code=error.status,
            headers={"X-Correlation-ID": correlation_id},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError):
        # Exclude input values, which may contain private data or accidental secrets.
        response = await api_error(
            request, APIError("INVALID_INPUT", 422, "Check the input fields.")
        )
        return response
