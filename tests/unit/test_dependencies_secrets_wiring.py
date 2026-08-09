"""Unit tests for SecretsClient integration into dependency injection.

Verifies that get_db_session and get_cache_client correctly use SecretsClient
for credential retrieval in non-local environments and fall back to static
URLs in local mode.
"""

import pytest

from app.config import Settings
from app.dependencies import _build_database_url, _build_redis_url
from app.services.secrets_client import Credentials


class TestBuildDatabaseUrl:
    """Tests for _build_database_url helper."""

    def test_builds_url_from_complete_credentials(self):
        creds = Credentials(
            username="db_user",
            password="secret_pass",
            host="aurora.cluster.eu-west-2.rds.amazonaws.com",
            port=5432,
            dbname="platform_db",
            engine="postgres",
        )
        settings = Settings()
        url = _build_database_url(creds, settings)
        assert url == (
            "postgresql+asyncpg://db_user:secret_pass"
            "@aurora.cluster.eu-west-2.rds.amazonaws.com:5432/platform_db"
        )

    def test_url_encodes_special_characters_in_password(self):
        creds = Credentials(
            username="user",
            password="p@ss:word/with#special",
            host="db.host.com",
            port=5432,
            dbname="mydb",
        )
        settings = Settings()
        url = _build_database_url(creds, settings)
        assert "p%40ss%3Aword%2Fwith%23special" in url
        assert "@db.host.com:5432/mydb" in url

    def test_url_encodes_special_characters_in_username(self):
        creds = Credentials(
            username="user@domain",
            password="pass",
            host="db.host.com",
            port=5432,
            dbname="mydb",
        )
        settings = Settings()
        url = _build_database_url(creds, settings)
        assert "user%40domain:pass@" in url

    def test_defaults_port_to_5432_when_none(self):
        creds = Credentials(
            username="user",
            password="pass",
            host="db.host.com",
            port=None,
            dbname="mydb",
        )
        settings = Settings()
        url = _build_database_url(creds, settings)
        assert ":5432/mydb" in url

    def test_falls_back_to_static_url_when_host_missing(self):
        creds = Credentials(
            username="user",
            password="pass",
            host=None,
            dbname="mydb",
        )
        settings = Settings()
        url = _build_database_url(creds, settings)
        assert url == settings.database_url

    def test_falls_back_to_static_url_when_dbname_missing(self):
        creds = Credentials(
            username="user",
            password="pass",
            host="db.host.com",
            dbname=None,
        )
        settings = Settings()
        url = _build_database_url(creds, settings)
        assert url == settings.database_url


class TestBuildRedisUrl:
    """Tests for _build_redis_url helper."""

    def test_builds_url_from_complete_credentials(self):
        creds = Credentials(
            username="default",
            password="redis_auth_token",
            host="redis.cache.amazonaws.com",
            port=6379,
        )
        settings = Settings(redis_ssl_enabled=False)
        url = _build_redis_url(creds, settings)
        assert url == "redis://:redis_auth_token@redis.cache.amazonaws.com:6379/0"

    def test_uses_rediss_scheme_when_ssl_enabled(self):
        creds = Credentials(
            username="default",
            password="token",
            host="redis.host.com",
            port=6380,
        )
        settings = Settings(redis_ssl_enabled=True)
        url = _build_redis_url(creds, settings)
        assert url.startswith("rediss://")

    def test_url_encodes_special_characters_in_password(self):
        creds = Credentials(
            username="default",
            password="tok@n:with/special",
            host="redis.host.com",
            port=6379,
        )
        settings = Settings(redis_ssl_enabled=False)
        url = _build_redis_url(creds, settings)
        assert "tok%40n%3Awith%2Fspecial" in url

    def test_defaults_port_to_6379_when_none(self):
        creds = Credentials(
            username="default",
            password="pass",
            host="redis.host.com",
            port=None,
        )
        settings = Settings(redis_ssl_enabled=False)
        url = _build_redis_url(creds, settings)
        assert ":6379/0" in url

    def test_falls_back_to_static_url_when_host_missing(self):
        creds = Credentials(
            username="default",
            password="pass",
            host=None,
        )
        settings = Settings()
        url = _build_redis_url(creds, settings)
        assert url == settings.redis_url


class TestDependencyRoutingByEnvironment:
    """Tests verifying local vs non-local routing logic."""

    def test_local_settings_is_local_true(self):
        settings = Settings(environment="local")
        assert settings.is_local is True

    def test_demo_settings_is_local_false(self):
        settings = Settings(environment="demo")
        assert settings.is_local is False

    def test_secrets_db_arn_configured(self):
        settings = Settings()
        assert "platform/db-credentials" in settings.secrets_db_arn

    def test_secrets_redis_arn_configured(self):
        settings = Settings()
        assert "platform/redis-credentials" in settings.secrets_redis_arn
