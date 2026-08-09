"""Unit tests for the SessionService class."""

import json
import time
from unittest.mock import AsyncMock, patch

import pytest

from app.services.session_service import SessionData, SessionService


@pytest.fixture
def mock_redis():
    """Create a mock Redis client with async methods."""
    client = AsyncMock()
    client.set = AsyncMock()
    client.get = AsyncMock(return_value=None)
    client.delete = AsyncMock()
    client.exists = AsyncMock(return_value=1)
    client.expire = AsyncMock()
    client.ttl = AsyncMock(return_value=3000)
    return client


@pytest.fixture
def session_service(mock_redis):
    """Create a SessionService with a mock Redis client."""
    return SessionService(redis_client=mock_redis, default_ttl=3600)


class TestSessionDataModel:
    """Tests for the SessionData Pydantic model."""

    def test_create_session_data_with_defaults(self):
        now = time.time()
        data = SessionData(
            user_id="user-123",
            email="test@example.com",
            role="viewer",
            groups=["users"],
            created_at=now,
            last_accessed=now,
        )
        assert data.user_id == "user-123"
        assert data.metadata == {}

    def test_create_session_data_with_metadata(self):
        now = time.time()
        data = SessionData(
            user_id="user-456",
            email="admin@example.com",
            role="admin",
            groups=["admins", "users"],
            created_at=now,
            last_accessed=now,
            metadata={"ip": "192.168.1.1", "user_agent": "Mozilla/5.0"},
        )
        assert data.metadata["ip"] == "192.168.1.1"
        assert data.role == "admin"

    def test_session_data_json_roundtrip(self):
        now = time.time()
        data = SessionData(
            user_id="user-789",
            email="test@test.com",
            role="manager",
            groups=["managers", "users"],
            created_at=now,
            last_accessed=now,
            metadata={"key": "value"},
        )
        json_str = data.model_dump_json()
        restored = SessionData.model_validate_json(json_str)
        assert restored == data


class TestSessionServiceCreate:
    """Tests for SessionService.create method."""

    async def test_create_returns_session_id(self, session_service):
        session_id = await session_service.create(
            user_id="user-123",
            data={"email": "test@example.com", "role": "viewer", "groups": ["users"]},
        )
        assert isinstance(session_id, str)
        assert len(session_id) == 32  # UUID4 hex is 32 chars

    async def test_create_stores_session_in_redis(self, session_service, mock_redis):
        session_id = await session_service.create(
            user_id="user-123",
            data={"email": "test@example.com", "role": "admin", "groups": ["admins"]},
        )

        mock_redis.set.assert_called_once()
        call_args = mock_redis.set.call_args
        key = call_args[0][0]
        value = call_args[0][1]
        ttl = call_args[1]["ex"]

        assert key == f"session:{session_id}"
        assert ttl == 3600

        stored_data = SessionData.model_validate_json(value)
        assert stored_data.user_id == "user-123"
        assert stored_data.email == "test@example.com"
        assert stored_data.role == "admin"
        assert stored_data.groups == ["admins"]

    async def test_create_uses_default_values_for_missing_data(self, session_service, mock_redis):
        await session_service.create(user_id="user-123", data={})

        call_args = mock_redis.set.call_args
        value = call_args[0][1]
        stored_data = SessionData.model_validate_json(value)
        assert stored_data.email == ""
        assert stored_data.role == "viewer"
        assert stored_data.groups == []
        assert stored_data.metadata == {}

    async def test_create_sets_timestamps(self, session_service, mock_redis):
        before = time.time()
        await session_service.create(
            user_id="user-123",
            data={"email": "test@example.com"},
        )
        after = time.time()

        call_args = mock_redis.set.call_args
        value = call_args[0][1]
        stored_data = SessionData.model_validate_json(value)
        assert before <= stored_data.created_at <= after
        assert before <= stored_data.last_accessed <= after

    async def test_create_generates_unique_ids(self, session_service):
        id1 = await session_service.create(user_id="user-1", data={})
        id2 = await session_service.create(user_id="user-2", data={})
        assert id1 != id2


class TestSessionServiceGet:
    """Tests for SessionService.get method."""

    async def test_get_returns_none_for_missing_session(self, session_service, mock_redis):
        mock_redis.get.return_value = None
        result = await session_service.get("nonexistent-id")
        assert result is None

    async def test_get_returns_session_data(self, session_service, mock_redis):
        now = time.time()
        session_data = SessionData(
            user_id="user-123",
            email="test@example.com",
            role="admin",
            groups=["admins"],
            created_at=now,
            last_accessed=now,
        )
        mock_redis.get.return_value = session_data.model_dump_json()

        result = await session_service.get("test-session-id")

        assert result is not None
        assert result.user_id == "user-123"
        assert result.email == "test@example.com"
        assert result.role == "admin"

    async def test_get_updates_last_accessed(self, session_service, mock_redis):
        old_time = time.time() - 100
        session_data = SessionData(
            user_id="user-123",
            email="test@example.com",
            role="viewer",
            groups=[],
            created_at=old_time,
            last_accessed=old_time,
        )
        mock_redis.get.return_value = session_data.model_dump_json()

        before = time.time()
        result = await session_service.get("test-session-id")
        after = time.time()

        assert result is not None
        assert result.last_accessed >= before
        assert result.last_accessed <= after

    async def test_get_preserves_remaining_ttl(self, session_service, mock_redis):
        now = time.time()
        session_data = SessionData(
            user_id="user-123",
            email="test@example.com",
            role="viewer",
            groups=[],
            created_at=now,
            last_accessed=now,
        )
        mock_redis.get.return_value = session_data.model_dump_json()
        mock_redis.ttl.return_value = 1500

        await session_service.get("test-session-id")

        # The set call should use the remaining TTL
        set_call = mock_redis.set.call_args
        assert set_call[1]["ex"] == 1500


class TestSessionServiceRefresh:
    """Tests for SessionService.refresh method."""

    async def test_refresh_extends_ttl(self, session_service, mock_redis):
        mock_redis.exists.return_value = 1
        await session_service.refresh("test-session-id", ttl=7200)
        mock_redis.expire.assert_called_once_with("session:test-session-id", 7200)

    async def test_refresh_uses_default_ttl_when_none(self, session_service, mock_redis):
        mock_redis.exists.return_value = 1
        await session_service.refresh("test-session-id")
        mock_redis.expire.assert_called_once_with("session:test-session-id", 3600)

    async def test_refresh_does_nothing_for_missing_session(self, session_service, mock_redis):
        mock_redis.exists.return_value = 0
        await session_service.refresh("nonexistent-id", ttl=7200)
        mock_redis.expire.assert_not_called()


class TestSessionServiceDestroy:
    """Tests for SessionService.destroy method."""

    async def test_destroy_deletes_session(self, session_service, mock_redis):
        await session_service.destroy("test-session-id")
        mock_redis.delete.assert_called_once_with("session:test-session-id")

    async def test_destroy_nonexistent_session_does_not_raise(self, session_service, mock_redis):
        mock_redis.delete.return_value = 0  # Key didn't exist
        await session_service.destroy("nonexistent-id")  # Should not raise


class TestSessionServiceKeyPattern:
    """Tests for the cache key pattern."""

    def test_key_prefix(self, session_service):
        key = session_service._make_key("abc123")
        assert key == "session:abc123"

    def test_key_pattern_matches_spec(self, session_service):
        assert session_service.KEY_PREFIX == "session:"


class TestSessionServiceCustomTTL:
    """Tests for custom TTL configuration."""

    async def test_custom_default_ttl(self, mock_redis):
        service = SessionService(redis_client=mock_redis, default_ttl=1800)
        await service.create(user_id="user-1", data={"email": "a@b.com"})

        call_args = mock_redis.set.call_args
        assert call_args[1]["ex"] == 1800
