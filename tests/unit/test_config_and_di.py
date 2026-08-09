"""Unit tests for app configuration, application factory, and dependency injection."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.dependencies import AuthService, SecretsClient
from app.main import create_app


class TestSettings:
    """Tests for Pydantic Settings configuration."""

    def test_default_settings_are_local(self):
        settings = Settings()
        assert settings.environment == "local"
        assert settings.log_level == "DEBUG"
        assert settings.is_local is True

    def test_demo_environment(self):
        settings = Settings(environment="demo")
        assert settings.is_local is False

    def test_database_url_default(self):
        settings = Settings()
        assert "asyncpg" in settings.database_url
        assert "platform_db" in settings.database_url

    def test_redis_url_default(self):
        settings = Settings()
        assert "6379" in settings.redis_url

    def test_cognito_settings(self):
        settings = Settings(
            cognito_user_pool_id="pool-123",
            cognito_client_id="client-456",
            cognito_jwks_url="https://example.com/jwks.json",
        )
        assert settings.cognito_user_pool_id == "pool-123"
        assert settings.cognito_client_id == "client-456"
        assert settings.cognito_jwks_url == "https://example.com/jwks.json"

    def test_secrets_manager_arns(self):
        settings = Settings()
        assert "secretsmanager" in settings.secrets_db_arn
        assert "secretsmanager" in settings.secrets_redis_arn

    def test_secrets_cache_ttl(self):
        settings = Settings(secrets_cache_ttl=3600)
        assert settings.secrets_cache_ttl == 3600

    def test_pool_settings(self):
        settings = Settings(db_pool_size=5, db_max_overflow=10)
        assert settings.db_pool_size == 5
        assert settings.db_max_overflow == 10

    def test_get_settings_returns_instance(self):
        settings = get_settings()
        assert isinstance(settings, Settings)


class TestCreateApp:
    """Tests for the FastAPI application factory."""

    def test_creates_fastapi_instance(self):
        app = create_app()
        assert isinstance(app, FastAPI)

    def test_app_title_and_version(self):
        app = create_app()
        assert app.title == "Secure Multi-Tier Platform"
        assert app.version == "0.1.0"

    def test_docs_enabled_in_local(self):
        settings = Settings(environment="local")
        app = create_app(settings=settings)
        assert app.docs_url == "/docs"
        assert app.redoc_url == "/redoc"

    def test_docs_disabled_in_demo(self):
        settings = Settings(environment="demo")
        app = create_app(settings=settings)
        assert app.docs_url is None
        assert app.redoc_url is None

    def test_settings_stored_on_app_state(self):
        settings = Settings(log_level="WARNING")
        app = create_app(settings=settings)
        assert app.state.settings.log_level == "WARNING"

    def test_custom_settings_override(self):
        settings = Settings(environment="demo", db_pool_size=20)
        app = create_app(settings=settings)
        assert app.state.settings.environment == "demo"
        assert app.state.settings.db_pool_size == 20


class TestDependencies:
    """Tests for dependency injection providers."""

    def test_auth_service_configured_from_settings(self):
        settings = Settings()
        auth = AuthService(
            jwks_url=settings.cognito_jwks_url,
            client_id=settings.cognito_client_id,
            user_pool_id=settings.cognito_user_pool_id,
            region=settings.cognito_region,
        )
        assert auth._client_id == settings.cognito_client_id
        assert auth._user_pool_id == settings.cognito_user_pool_id

    def test_secrets_client_holds_settings(self):
        client = SecretsClient(
            endpoint_url="http://localhost:4566",
            region_name="eu-west-2",
            cache_ttl_seconds=7200,
        )
        assert client.endpoint_url == "http://localhost:4566"
        assert client.cache_ttl_seconds == 7200

    def test_secrets_client_uses_aws_endpoint(self):
        client = SecretsClient(endpoint_url="http://localstack:4566")
        assert client.endpoint_url == "http://localstack:4566"
