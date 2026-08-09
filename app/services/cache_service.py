"""Cache service implementing the cache-aside pattern.

Provides a CacheService class for transparent caching of database query results
with automatic cache invalidation on write operations. Falls through to the
database when the cache cluster is unavailable.
"""

import hashlib
import json
import logging
from typing import Any, Callable, Coroutine, Optional

import redis.asyncio as aioredis
from redis.exceptions import ConnectionError, RedisError, TimeoutError

logger = logging.getLogger(__name__)

# Maximum retry attempts for Redis connection failures
_MAX_RETRIES = 3
# Base delay in seconds for exponential backoff
_BASE_DELAY = 0.1


class CacheService:
    """Cache-aside pattern implementation backed by Redis.

    The service wraps a Redis client and provides:
    - get/set for explicit key-value caching
    - invalidate for pattern-based cache clearing
    - generate_key for deterministic cache key derivation
    - get_or_fetch for the full cache-aside pattern (cache miss → DB read → cache store)

    When the Redis cluster is unavailable, all operations gracefully degrade:
    - get returns None (cache miss)
    - set/invalidate are silently skipped with a warning log
    - get_or_fetch falls through to the database callback
    """

    def __init__(self, redis_client: aioredis.Redis, default_ttl: int = 300) -> None:
        """Initialise the cache service.

        Args:
            redis_client: An async Redis client configured with TLS and retry logic.
            default_ttl: Default time-to-live in seconds for cached entries.
        """
        self._redis = redis_client
        self._default_ttl = default_ttl

    async def get(self, key: str) -> Optional[Any]:
        """Retrieve a value from the cache.

        Args:
            key: The cache key to look up.

        Returns:
            The deserialised cached value, or None on cache miss or unavailability.
        """
        try:
            raw = await self._execute_with_retry(self._redis.get, key)
            if raw is None:
                return None
            return json.loads(raw)
        except (ConnectionError, TimeoutError, RedisError) as exc:
            logger.warning(
                "Cache unavailable during GET for key=%s: %s. Falling through to database.",
                key,
                exc,
            )
            return None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Store a value in the cache with a TTL.

        Args:
            key: The cache key.
            value: The value to cache (must be JSON-serialisable).
            ttl: Time-to-live in seconds. Uses default_ttl if not provided.
        """
        effective_ttl = ttl if ttl is not None else self._default_ttl
        try:
            serialised = json.dumps(value, default=str)
            await self._execute_with_retry(self._redis.set, key, serialised, ex=effective_ttl)
        except (ConnectionError, TimeoutError, RedisError) as exc:
            logger.warning(
                "Cache unavailable during SET for key=%s: %s. Write skipped.",
                key,
                exc,
            )

    async def invalidate(self, pattern: str) -> None:
        """Invalidate all cache entries matching a pattern.

        Uses Redis SCAN + DELETE to avoid blocking the server with KEYS.

        Args:
            pattern: A glob-style pattern (e.g. 'cache:products:*').
        """
        try:
            cursor = 0
            while True:
                cursor, keys = await self._execute_with_retry(
                    self._redis.scan, cursor=cursor, match=pattern, count=100
                )
                if keys:
                    await self._execute_with_retry(self._redis.delete, *keys)
                if cursor == 0:
                    break
        except (ConnectionError, TimeoutError, RedisError) as exc:
            logger.warning(
                "Cache unavailable during INVALIDATE for pattern=%s: %s. Invalidation skipped.",
                pattern,
                exc,
            )

    def generate_key(self, resource: str, params: dict) -> str:
        """Generate a deterministic cache key from a resource type and parameters.

        The key is constructed as:
            cache:{resource}:{hash_of_sorted_params}

        Params are sorted by key to ensure determinism regardless of insertion order.

        Args:
            resource: The resource type (e.g. 'products:list', 'products:detail:uuid').
            params: Query parameters that affect the cached result.

        Returns:
            A deterministic, unique cache key string.
        """
        # Sort params for deterministic ordering; stringify all values
        normalised = {k: str(v) for k, v in sorted(params.items())}
        params_json = json.dumps(normalised, sort_keys=True, separators=(",", ":"))
        params_hash = hashlib.sha256(params_json.encode()).hexdigest()[:16]
        return f"cache:{resource}:{params_hash}"

    async def get_or_fetch(
        self,
        key: str,
        fetch_fn: Callable[[], Coroutine[Any, Any, Any]],
        ttl: int | None = None,
    ) -> Any:
        """Cache-aside pattern: try cache first, fall through to DB on miss.

        1. Attempt to read from cache.
        2. On cache hit, return the cached value.
        3. On cache miss (or cache unavailability), call fetch_fn to read from DB.
        4. Store the fetched result in cache for future requests.
        5. Return the result to the caller.

        Args:
            key: The cache key.
            fetch_fn: An async callable that fetches the data from the database.
            ttl: Optional TTL override for this entry.

        Returns:
            The cached or freshly fetched value.
        """
        # Step 1: Try cache
        cached = await self.get(key)
        if cached is not None:
            logger.debug("Cache HIT for key=%s", key)
            return cached

        # Step 2: Cache miss → fetch from database
        logger.debug("Cache MISS for key=%s, fetching from database", key)
        result = await fetch_fn()

        # Step 3: Store in cache (non-blocking on failure)
        if result is not None:
            await self.set(key, result, ttl)

        return result

    async def invalidate_on_write(self, resource: str) -> None:
        """Invalidate all cache entries for a resource after a write operation.

        Convenience method that constructs the invalidation pattern from the
        resource name and clears all related cache entries.

        Args:
            resource: The resource type (e.g. 'products', 'orders:user:uuid').
        """
        pattern = f"cache:{resource}:*"
        await self.invalidate(pattern)

    async def _execute_with_retry(self, fn: Callable, *args: Any, **kwargs: Any) -> Any:
        """Execute a Redis command with exponential backoff retry logic.

        Retries up to _MAX_RETRIES times on connection/timeout errors.
        Uses exponential backoff: delay = _BASE_DELAY * 2^attempt.

        Args:
            fn: The Redis command to execute.
            *args: Positional arguments for the command.
            **kwargs: Keyword arguments for the command.

        Returns:
            The result of the Redis command.

        Raises:
            ConnectionError | TimeoutError: If all retries are exhausted.
        """
        import asyncio

        last_exc: BaseException | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                return await fn(*args, **kwargs)
            except (ConnectionError, TimeoutError) as exc:
                last_exc = exc
                if attempt < _MAX_RETRIES - 1:
                    delay = _BASE_DELAY * (2**attempt)
                    logger.warning(
                        "Redis connection attempt %d/%d failed: %s. Retrying in %.2fs...",
                        attempt + 1,
                        _MAX_RETRIES,
                        exc,
                        delay,
                    )
                    await asyncio.sleep(delay)
        raise last_exc  # type: ignore[misc]
