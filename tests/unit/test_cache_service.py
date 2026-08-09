"""Unit tests for the CacheService class."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from redis.exceptions import ConnectionError, TimeoutError

from app.services.cache_service import CacheService


@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    client = AsyncMock()
    client.get = AsyncMock(return_value=None)
    client.set = AsyncMock(return_value=True)
    client.delete = AsyncMock(return_value=1)
    client.scan = AsyncMock(return_value=(0, []))
    return client


@pytest.fixture
def cache_service(mock_redis):
    """Create a CacheService instance with mock Redis."""
    return CacheService(redis_client=mock_redis, default_ttl=300)


class TestCacheGet:
    """Tests for CacheService.get method."""

    async def test_get_returns_none_on_cache_miss(self, cache_service, mock_redis):
        mock_redis.get = AsyncMock(return_value=None)
        result = await cache_service.get("cache:products:list:abc123")
        assert result is None

    async def test_get_returns_deserialised_value_on_hit(self, cache_service, mock_redis):
        data = {"id": "123", "name": "Widget", "price_pence": 999}
        mock_redis.get = AsyncMock(return_value=json.dumps(data))
        result = await cache_service.get("cache:products:detail:123")
        assert result == data

    async def test_get_returns_none_on_connection_error(self, cache_service, mock_redis):
        mock_redis.get = AsyncMock(side_effect=ConnectionError("Connection refused"))
        result = await cache_service.get("cache:products:detail:123")
        assert result is None

    async def test_get_returns_none_on_timeout(self, cache_service, mock_redis):
        mock_redis.get = AsyncMock(side_effect=TimeoutError("Timeout"))
        result = await cache_service.get("cache:products:detail:123")
        assert result is None


class TestCacheSet:
    """Tests for CacheService.set method."""

    async def test_set_stores_serialised_value_with_default_ttl(self, cache_service, mock_redis):
        await cache_service.set("cache:products:detail:123", {"name": "Widget"})
        mock_redis.set.assert_called_once_with(
            "cache:products:detail:123",
            json.dumps({"name": "Widget"}),
            ex=300,
        )

    async def test_set_uses_custom_ttl(self, cache_service, mock_redis):
        await cache_service.set("cache:products:detail:123", {"name": "Widget"}, ttl=600)
        mock_redis.set.assert_called_once_with(
            "cache:products:detail:123",
            json.dumps({"name": "Widget"}),
            ex=600,
        )

    async def test_set_handles_connection_error_gracefully(self, cache_service, mock_redis):
        mock_redis.set = AsyncMock(side_effect=ConnectionError("Connection refused"))
        # Should not raise
        await cache_service.set("cache:products:detail:123", {"name": "Widget"})

    async def test_set_handles_timeout_gracefully(self, cache_service, mock_redis):
        mock_redis.set = AsyncMock(side_effect=TimeoutError("Timeout"))
        await cache_service.set("cache:products:detail:123", {"name": "Widget"})


class TestCacheInvalidate:
    """Tests for CacheService.invalidate method."""

    async def test_invalidate_deletes_matching_keys(self, cache_service, mock_redis):
        mock_redis.scan = AsyncMock(
            return_value=(0, ["cache:products:list:a", "cache:products:list:b"])
        )
        await cache_service.invalidate("cache:products:*")
        mock_redis.delete.assert_called_once_with("cache:products:list:a", "cache:products:list:b")

    async def test_invalidate_handles_no_matching_keys(self, cache_service, mock_redis):
        mock_redis.scan = AsyncMock(return_value=(0, []))
        await cache_service.invalidate("cache:nonexistent:*")
        mock_redis.delete.assert_not_called()

    async def test_invalidate_handles_connection_error(self, cache_service, mock_redis):
        mock_redis.scan = AsyncMock(side_effect=ConnectionError("Connection refused"))
        # Should not raise
        await cache_service.invalidate("cache:products:*")


class TestGenerateKey:
    """Tests for CacheService.generate_key method."""

    def test_generate_key_is_deterministic(self, cache_service):
        params = {"category": "electronics", "page": "1", "page_size": "20"}
        key1 = cache_service.generate_key("products:list", params)
        key2 = cache_service.generate_key("products:list", params)
        assert key1 == key2

    def test_generate_key_different_params_produce_different_keys(self, cache_service):
        key1 = cache_service.generate_key("products:list", {"category": "electronics"})
        key2 = cache_service.generate_key("products:list", {"category": "clothing"})
        assert key1 != key2

    def test_generate_key_order_independent(self, cache_service):
        key1 = cache_service.generate_key("products:list", {"a": "1", "b": "2"})
        key2 = cache_service.generate_key("products:list", {"b": "2", "a": "1"})
        assert key1 == key2

    def test_generate_key_format(self, cache_service):
        key = cache_service.generate_key("products:list", {"page": "1"})
        assert key.startswith("cache:products:list:")
        # Hash portion should be 16 hex chars
        hash_part = key.split(":")[-1]
        assert len(hash_part) == 16

    def test_generate_key_empty_params(self, cache_service):
        key = cache_service.generate_key("products:list", {})
        assert key.startswith("cache:products:list:")


class TestGetOrFetch:
    """Tests for the cache-aside pattern via get_or_fetch."""

    async def test_returns_cached_value_on_hit(self, cache_service, mock_redis):
        data = {"id": "123", "name": "Widget"}
        mock_redis.get = AsyncMock(return_value=json.dumps(data))
        fetch_fn = AsyncMock()

        result = await cache_service.get_or_fetch("cache:products:detail:123", fetch_fn)

        assert result == data
        fetch_fn.assert_not_called()

    async def test_calls_fetch_fn_on_cache_miss(self, cache_service, mock_redis):
        mock_redis.get = AsyncMock(return_value=None)
        data = {"id": "123", "name": "Widget"}
        fetch_fn = AsyncMock(return_value=data)

        result = await cache_service.get_or_fetch("cache:products:detail:123", fetch_fn)

        assert result == data
        fetch_fn.assert_called_once()

    async def test_stores_fetched_value_in_cache(self, cache_service, mock_redis):
        mock_redis.get = AsyncMock(return_value=None)
        data = {"id": "123", "name": "Widget"}
        fetch_fn = AsyncMock(return_value=data)

        await cache_service.get_or_fetch("cache:products:detail:123", fetch_fn, ttl=600)

        mock_redis.set.assert_called_once_with(
            "cache:products:detail:123",
            json.dumps(data),
            ex=600,
        )

    async def test_does_not_cache_none_result(self, cache_service, mock_redis):
        mock_redis.get = AsyncMock(return_value=None)
        fetch_fn = AsyncMock(return_value=None)

        result = await cache_service.get_or_fetch("cache:products:detail:999", fetch_fn)

        assert result is None
        mock_redis.set.assert_not_called()

    async def test_falls_through_to_db_on_cache_unavailability(self, cache_service, mock_redis):
        mock_redis.get = AsyncMock(side_effect=ConnectionError("Connection refused"))
        data = {"id": "123", "name": "Widget"}
        fetch_fn = AsyncMock(return_value=data)

        result = await cache_service.get_or_fetch("cache:products:detail:123", fetch_fn)

        assert result == data
        fetch_fn.assert_called_once()


class TestInvalidateOnWrite:
    """Tests for cache invalidation on write operations."""

    async def test_invalidate_on_write_uses_correct_pattern(self, cache_service, mock_redis):
        mock_redis.scan = AsyncMock(return_value=(0, []))
        await cache_service.invalidate_on_write("products")
        mock_redis.scan.assert_called_once_with(cursor=0, match="cache:products:*", count=100)


class TestRetryLogic:
    """Tests for the exponential backoff retry logic."""

    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_retries_on_connection_error(self, mock_sleep, mock_redis):
        mock_redis.get = AsyncMock(
            side_effect=[ConnectionError("fail"), ConnectionError("fail"), json.dumps({"ok": True})]
        )
        service = CacheService(redis_client=mock_redis, default_ttl=300)

        result = await service.get("test-key")

        assert result == {"ok": True}
        assert mock_sleep.call_count == 2

    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_raises_after_max_retries_exhausted(self, mock_sleep, mock_redis):
        mock_redis.get = AsyncMock(
            side_effect=[
                ConnectionError("fail"),
                ConnectionError("fail"),
                ConnectionError("fail"),
            ]
        )
        service = CacheService(redis_client=mock_redis, default_ttl=300)

        # The outer get() catches the re-raised error and returns None
        result = await service.get("test-key")
        assert result is None

    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_exponential_backoff_delays(self, mock_sleep, mock_redis):
        mock_redis.get = AsyncMock(
            side_effect=[ConnectionError("fail"), ConnectionError("fail"), json.dumps({"ok": True})]
        )
        service = CacheService(redis_client=mock_redis, default_ttl=300)

        await service.get("test-key")

        # Backoff: 0.1 * 2^0 = 0.1, 0.1 * 2^1 = 0.2
        mock_sleep.assert_any_call(0.1)
        mock_sleep.assert_any_call(0.2)
