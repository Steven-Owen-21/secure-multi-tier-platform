"""Global exception handling returning consistent structured error responses.

Requirement 6.7: The API_Gateway SHALL return structured error responses with
consistent format (error code, message, request ID) for all 4xx and 5xx status codes.

This module ensures unhandled exceptions and known application errors are returned
in a uniform JSON structure.
"""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("app")


def _build_error_response(
    status_code: int,
    error_code: str,
    message: str,
    request_id: str | None = None,
    details: Any = None,
) -> JSONResponse:
    """Build a structured error JSON response.

    Response format:
    {
        "error": {
            "code": "<ERROR_CODE>",
            "message": "<human-readable message>",
            "request_id": "<uuid>",
            "details": <optional additional context>
        }
    }
    """
    body: dict[str, Any] = {
        "error": {
            "code": error_code,
            "message": message,
            "request_id": request_id,
        }
    }
    if details is not None:
        body["error"]["details"] = details
    return JSONResponse(status_code=status_code, content=body)


def _get_request_id(request: Request) -> str | None:
    """Retrieve request_id from state, falling back to header."""
    return getattr(request.state, "request_id", None) or request.headers.get(
        "X-Request-ID"
    )


async def _http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """Handle Starlette/FastAPI HTTPException with structured response."""
    request_id = _get_request_id(request)
    error_code = f"HTTP_{exc.status_code}"
    message = exc.detail if isinstance(exc.detail, str) else str(exc.detail)

    logger.warning(
        "HTTP exception: %s %s",
        exc.status_code,
        message,
        extra={
            "json_fields": {
                "request_id": request_id,
                "status_code": exc.status_code,
                "error_code": error_code,
            }
        },
    )

    return _build_error_response(
        status_code=exc.status_code,
        error_code=error_code,
        message=message,
        request_id=request_id,
    )


async def _validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle Pydantic validation errors with field-level details.

    Returns HTTP 422 with structured error containing field-level messages.
    """
    request_id = _get_request_id(request)
    field_errors = []
    for error in exc.errors():
        field_errors.append(
            {
                "field": ".".join(str(loc) for loc in error["loc"]),
                "message": error["msg"],
                "type": error["type"],
            }
        )

    logger.warning(
        "Validation error: %d field(s) invalid",
        len(field_errors),
        extra={
            "json_fields": {
                "request_id": request_id,
                "status_code": 422,
                "error_code": "VALIDATION_ERROR",
                "field_count": len(field_errors),
            }
        },
    )

    return _build_error_response(
        status_code=422,
        error_code="VALIDATION_ERROR",
        message="Request validation failed",
        request_id=request_id,
        details=field_errors,
    )


async def _unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """Handle unexpected exceptions, hiding internal details from clients.

    Logs the full traceback server-side but returns a generic error to the caller
    to avoid leaking internal architecture details.
    """
    request_id = _get_request_id(request)

    logger.error(
        "Unhandled exception: %s",
        str(exc),
        exc_info=True,
        extra={
            "json_fields": {
                "request_id": request_id,
                "status_code": 500,
                "error_code": "INTERNAL_ERROR",
                "exception_type": type(exc).__name__,
            }
        },
    )

    return _build_error_response(
        status_code=500,
        error_code="INTERNAL_ERROR",
        message="An internal error occurred. Please try again later.",
        request_id=request_id,
    )


def register_error_handlers(app: FastAPI) -> None:
    """Register all exception handlers on the FastAPI application.

    Args:
        app: The FastAPI application instance.
    """
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)
    app.add_exception_handler(RequestValidationError, _validation_exception_handler)
    app.add_exception_handler(Exception, _unhandled_exception_handler)
