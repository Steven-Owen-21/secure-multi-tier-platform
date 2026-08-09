"""Unit tests for structured logging middleware and global error handler."""

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.middleware.error_handler import register_error_handlers
from app.middleware.logging import StructuredLoggingMiddleware, configure_logging


class TestStructuredLoggingMiddleware:
    """Tests for the structured JSON request logging middleware."""

    @pytest.fixture
    def app(self) -> FastAPI:
        return create_app(settings=Settings(log_level="DEBUG"))

    @pytest.fixture
    def client(self, app: FastAPI) -> TestClient:
        return TestClient(app)

    def test_request_id_generated_when_not_provided(self, client: TestClient):
        response = client.get("/health")
        assert "X-Request-ID" in response.headers
        # UUID format: 8-4-4-4-12 hex chars
        request_id = response.headers["X-Request-ID"]
        assert len(request_id) == 36

    def test_request_id_propagated_from_header(self, client: TestClient):
        custom_id = "my-custom-request-id-123"
        response = client.get("/health", headers={"X-Request-ID": custom_id})
        assert response.headers["X-Request-ID"] == custom_id

    def test_structured_log_emitted(self, client: TestClient, caplog):
        with caplog.at_level("INFO", logger="app"):
            response = client.get("/health")
        # The middleware should have logged "Request completed"
        found = False
        for record in caplog.records:
            if record.message == "Request completed" and hasattr(record, "json_fields"):
                found = True
                fields = record.json_fields
                assert "request_id" in fields
                assert "method" in fields
                assert "path" in fields
                assert "status_code" in fields
                assert "duration_ms" in fields
                assert "user_id" in fields
                assert fields["method"] == "GET"
                assert fields["path"] == "/health"
                break
        assert found, f"No structured log record found. Records: {caplog.records}"

    def test_duration_ms_is_positive(self, client: TestClient, caplog):
        with caplog.at_level("INFO", logger="app"):
            client.get("/health")
        for record in caplog.records:
            if record.message == "Request completed" and hasattr(record, "json_fields"):
                assert record.json_fields["duration_ms"] >= 0
                break

    def test_user_id_none_when_not_authenticated(self, client: TestClient, caplog):
        with caplog.at_level("INFO", logger="app"):
            client.get("/health")
        for record in caplog.records:
            if record.message == "Request completed" and hasattr(record, "json_fields"):
                assert record.json_fields["user_id"] is None
                break


class TestConfigureLogging:
    """Tests for the logging configuration function."""

    def test_returns_logger(self):
        logger = configure_logging("INFO")
        assert logger.name == "app"

    def test_sets_log_level(self):
        import logging

        logger = configure_logging("WARNING")
        assert logger.level == logging.WARNING

    def test_no_duplicate_handlers(self):
        logger = configure_logging("DEBUG")
        handler_count = len(logger.handlers)
        # Calling again should not add more handlers
        configure_logging("DEBUG")
        assert len(logger.handlers) == handler_count


class TestErrorHandler:
    """Tests for the global exception handling middleware."""

    @pytest.fixture
    def app(self) -> FastAPI:
        return create_app(settings=Settings(log_level="ERROR"))

    @pytest.fixture
    def client(self, app: FastAPI) -> TestClient:
        return TestClient(app, raise_server_exceptions=False)

    def test_404_returns_structured_error(self, client: TestClient):
        response = client.get("/nonexistent-path")
        assert response.status_code == 404
        body = response.json()
        assert "error" in body
        assert body["error"]["code"] == "HTTP_404"
        assert "message" in body["error"]
        assert "request_id" in body["error"]

    def test_validation_error_returns_422_with_details(self):
        """Test that Pydantic validation errors return field-level details."""
        from pydantic import BaseModel, Field

        app = FastAPI()
        app.add_middleware(StructuredLoggingMiddleware, log_level="ERROR")
        register_error_handlers(app)

        class ItemCreate(BaseModel):
            name: str = Field(min_length=1)
            price: int = Field(gt=0)

        @app.post("/items")
        async def create_item(item: ItemCreate):
            return {"id": "test"}

        client = TestClient(app, raise_server_exceptions=False)
        response = client.post("/items", json={"name": "", "price": -1})
        assert response.status_code == 422
        body = response.json()
        assert body["error"]["code"] == "VALIDATION_ERROR"
        assert body["error"]["message"] == "Request validation failed"
        assert "details" in body["error"]
        assert len(body["error"]["details"]) >= 1
        # Each detail should have field, message, type
        for detail in body["error"]["details"]:
            assert "field" in detail
            assert "message" in detail
            assert "type" in detail

    def test_unhandled_exception_returns_500_generic(self):
        """Test that unhandled exceptions don't leak internal details."""
        app = FastAPI()
        app.add_middleware(StructuredLoggingMiddleware, log_level="ERROR")
        register_error_handlers(app)

        @app.get("/crash")
        async def crash():
            raise RuntimeError("Secret database connection string leaked!")

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/crash")
        assert response.status_code == 500
        body = response.json()
        assert body["error"]["code"] == "INTERNAL_ERROR"
        # Internal details MUST NOT be exposed
        assert "Secret" not in body["error"]["message"]
        assert "database" not in body["error"]["message"]
        assert "request_id" in body["error"]

    def test_http_exception_custom_message(self):
        """Test HTTPException with custom detail."""
        app = FastAPI()
        app.add_middleware(StructuredLoggingMiddleware, log_level="ERROR")
        register_error_handlers(app)

        @app.get("/forbidden")
        async def forbidden():
            raise HTTPException(status_code=403, detail="Insufficient permissions")

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/forbidden")
        assert response.status_code == 403
        body = response.json()
        assert body["error"]["code"] == "HTTP_403"
        assert body["error"]["message"] == "Insufficient permissions"

    def test_error_response_includes_request_id(self):
        """Error responses include the X-Request-ID for correlation."""
        app = FastAPI()
        app.add_middleware(StructuredLoggingMiddleware, log_level="ERROR")
        register_error_handlers(app)

        @app.get("/fail")
        async def fail():
            raise HTTPException(status_code=400, detail="Bad input")

        client = TestClient(app, raise_server_exceptions=False)
        custom_id = "trace-abc-123"
        response = client.get("/fail", headers={"X-Request-ID": custom_id})
        body = response.json()
        assert body["error"]["request_id"] == custom_id
