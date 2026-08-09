"""Structured JSON request logging middleware.

Emits a JSON log line for every HTTP request containing:
timestamp, level, request_id, method, path, status_code, duration_ms, user_id.

Requirement 12.5: The Application_Service SHALL emit structured JSON logs for every
request including fields for timestamp, level, request_id, method, path, status_code,
duration_ms, and user_id.
"""

import json
import logging
import sys
import time
import uuid
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


class _JSONFormatter(logging.Formatter):
    """Format log records as single-line JSON."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Merge any extra fields attached by the middleware
        if hasattr(record, "json_fields"):
            log_entry.update(record.json_fields)
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, default=str)


def configure_logging(log_level: str = "INFO") -> logging.Logger:
    """Configure the application-wide structured JSON logger.

    Args:
        log_level: One of DEBUG, INFO, WARNING, ERROR.

    Returns:
        The configured root application logger.
    """
    logger = logging.getLogger("app")
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Avoid duplicate handlers if called multiple times
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(_JSONFormatter(datefmt="%Y-%m-%dT%H:%M:%S.%fZ"))
        logger.addHandler(handler)

    # Prevent propagation to root logger which may have its own format
    logger.propagate = False
    return logger


class StructuredLoggingMiddleware(BaseHTTPMiddleware):
    """ASGI middleware that logs every request as structured JSON.

    Generates a unique request_id per request and attaches it to the response
    headers (X-Request-ID) for traceability.
    """

    def __init__(self, app: Any, log_level: str = "INFO") -> None:
        super().__init__(app)
        self.logger = configure_logging(log_level)

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Generate or propagate request ID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id

        start_time = time.perf_counter()

        response = await call_next(request)

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # Extract user_id from request state (set by auth middleware/dependency if present)
        user_id: str | None = getattr(request.state, "user_id", None)

        log_fields = {
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
            "user_id": user_id,
        }

        # Choose log level based on status code
        if response.status_code >= 500:
            self.logger.error(
                "Request completed",
                extra={"json_fields": log_fields},
            )
        elif response.status_code >= 400:
            self.logger.warning(
                "Request completed",
                extra={"json_fields": log_fields},
            )
        else:
            self.logger.info(
                "Request completed",
                extra={"json_fields": log_fields},
            )

        # Attach request ID to response for client traceability
        response.headers["X-Request-ID"] = request_id
        return response
