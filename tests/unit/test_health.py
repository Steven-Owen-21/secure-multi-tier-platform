"""Unit tests for the /health endpoint."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.main import create_app
from app.routers.health import ComponentHealth, HealthChecker, HealthResponse


@pytest.fixture
def settings() -> Settings:
    """Provide test settings."""
    return Settings(
        environment="local",
        database_url="postgresql+asyncpg://test:test@localhost:5432/test",
        redis_url="redis://localhost:6379/0",
    )


@pytest.fixture
def app(settings: Settings):
    """Create a test FastAPI app."""
    return create_app(settings=settings)


class TestHealthChecker:
    """Tests for the HealthChecker class."""

    async def test_check_database_healthy(self):
        """HealthChecker reports healthy when DB query succeeds."""
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=None)
        mock_cache = AsyncMock()

        checker = HealthChecker(db_session=mock_session, cache_client=mock_cache)
        result = await checker.check_database()

        assert result.name == "Database_Cluster"
        assert result.status == "healthy"
        assert result.latency_ms is not None
        assert result.latency_ms >= 0
        assert result.error is None

    async def test_check_database_unhealthy(self):
        """HealthChecker reports unhealthy when DB query fails."""
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=ConnectionError("Connection refused"))
        mock_cache = AsyncMock()

        checker = HealthChecker(db_session=mock_session, cache_client=mock_cache)
        result = await checker.check_database()

        assert result.name == "Database_Cluster"
        assert result.status == "unhealthy"
        assert result.error == "Connection refused"
        assert result.latency_ms is not None

    async def test_check_cache_healthy(self):
        """HealthChecker reports healthy when Redis PING succeeds."""
        mock_session = AsyncMock()
        mock_cache = AsyncMock()
        mock_cache.ping = AsyncMock(return_value=True)

        checker = HealthChecker(db_session=mock_session, cache_client=mock_cache)
        result = await checker.check_cache()

        assert result.name == "Cache_Cluster"
        assert result.status == "healthy"
        assert result.latency_ms is not None
        assert result.latency_ms >= 0
        assert result.error is None

    async def test_check_cache_unhealthy(self):
        """HealthChecker reports unhealthy when Redis PING fails."""
        mock_session = AsyncMock()
        mock_cache = AsyncMock()
        mock_cache.ping = AsyncMock(side_effect=ConnectionError("Redis unavailable"))

        checker = HealthChecker(db_session=mock_session, cache_client=mock_cache)
        result = await checker.check_cache()

        assert result.name == "Cache_Cluster"
        assert result.status == "unhealthy"
        assert result.error == "Redis unavailable"

    async def test_check_all_healthy(self):
        """check_all returns healthy when both dependencies are reachable."""
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=None)
        mock_cache = AsyncMock()
        mock_cache.ping = AsyncMock(return_value=True)

        checker = HealthChecker(db_session=mock_session, cache_client=mock_cache)
        result = await checker.check_all()

        assert result.status == "healthy"
        assert len(result.components) == 2
        assert all(c.status == "healthy" for c in result.components)
        assert result.timestamp is not None

    async def test_check_all_unhealthy_when_db_down(self):
        """check_all returns unhealthy when database is unreachable."""
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=ConnectionError("DB down"))
        mock_cache = AsyncMock()
        mock_cache.ping = AsyncMock(return_value=True)

        checker = HealthChecker(db_session=mock_session, cache_client=mock_cache)
        result = await checker.check_all()

        assert result.status == "unhealthy"
        db_component = next(c for c in result.components if c.name == "Database_Cluster")
        cache_component = next(c for c in result.components if c.name == "Cache_Cluster")
        assert db_component.status == "unhealthy"
        assert cache_component.status == "healthy"

    async def test_check_all_unhealthy_when_cache_down(self):
        """check_all returns unhealthy when cache is unreachable."""
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=None)
        mock_cache = AsyncMock()
        mock_cache.ping = AsyncMock(side_effect=ConnectionError("Cache down"))

        checker = HealthChecker(db_session=mock_session, cache_client=mock_cache)
        result = await checker.check_all()

        assert result.status == "unhealthy"
        db_component = next(c for c in result.components if c.name == "Database_Cluster")
        cache_component = next(c for c in result.components if c.name == "Cache_Cluster")
        assert db_component.status == "healthy"
        assert cache_component.status == "unhealthy"

    async def test_check_all_unhealthy_when_both_down(self):
        """check_all returns unhealthy when both dependencies are unreachable."""
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=ConnectionError("DB down"))
        mock_cache = AsyncMock()
        mock_cache.ping = AsyncMock(side_effect=ConnectionError("Cache down"))

        checker = HealthChecker(db_session=mock_session, cache_client=mock_cache)
        result = await checker.check_all()

        assert result.status == "unhealthy"
        assert all(c.status == "unhealthy" for c in result.components)


class TestHealthEndpoint:
    """Tests for the GET /health HTTP endpoint."""

    async def test_health_returns_200_when_all_healthy(self, app):
        """GET /health returns 200 with healthy status."""
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=None)
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()
        mock_session.close = AsyncMock()
        mock_cache = AsyncMock()
        mock_cache.ping = AsyncMock(return_value=True)

        from app.dependencies import get_cache_client, get_db_session

        async def override_db_session():
            yield mock_session

        async def override_cache_client():
            return mock_cache

        app.dependency_overrides[get_db_session] = override_db_session
        app.dependency_overrides[get_cache_client] = override_cache_client

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/health")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "healthy"
        assert len(body["components"]) == 2
        assert body["timestamp"] is not None

    async def test_health_returns_503_when_dependency_down(self, app):
        """GET /health returns 503 with degradation details."""
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=ConnectionError("DB unreachable"))
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()
        mock_session.close = AsyncMock()
        mock_cache = AsyncMock()
        mock_cache.ping = AsyncMock(return_value=True)

        from app.dependencies import get_cache_client, get_db_session

        async def override_db_session():
            yield mock_session

        async def override_cache_client():
            return mock_cache

        app.dependency_overrides[get_db_session] = override_db_session
        app.dependency_overrides[get_cache_client] = override_cache_client

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/health")

        assert resp.status_code == 503
        body = resp.json()
        assert body["status"] == "unhealthy"
        db_component = next(c for c in body["components"] if c["name"] == "Database_Cluster")
        assert db_component["status"] == "unhealthy"
        assert db_component["error"] == "DB unreachable"
