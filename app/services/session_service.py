"""Redis-backed session management service.

Provides create, get, refresh, and destroy operations for user sessions
stored in Redis with configurable TTL. Sessions are stored as JSON-serialised
SessionData objects keyed by `session:{session_id}`.
"""

import time
import uuid
from typing import Any, Optional

import redis.asyncio as aioredis
from pydantic import BaseModel


class SessionData(BaseModel):
    """Data stored in a user session."""

    user_id: str
    email: str
    role: str
    groups: list[str]
    created_at: float  # Unix timestamp
    last_accessed: float
    metadata: dict[str, Any] = {}


class SessionService:
    """Manages user sessions in Redis.

    Sessions are stored with the key pattern `session:{session_id}` and
    automatically expire after the configured TTL (default 3600 seconds).
    """

    KEY_PREFIX = "session:"

    def __init__(self, redis_client: aioredis.Redis, default_ttl: int = 3600) -> None:
        """Initialise the session service.

        Args:
            redis_client: An async Redis client instance.
            default_ttl: Default session time-to-live in seconds.
        """
        self._redis = redis_client
        self._default_ttl = default_ttl

    def _make_key(self, session_id: str) -> str:
        """Build the Redis key for a given session ID."""
        return f"{self.KEY_PREFIX}{session_id}"

    async def create(self, user_id: str, data: dict) -> str:
        """Create a new session and store it in Redis.

        Args:
            user_id: The ID of the user owning this session.
            data: Additional session data (email, role, groups, metadata).

        Returns:
            The generated session ID (UUID4 hex string).
        """
        session_id = uuid.uuid4().hex
        now = time.time()

        session_data = SessionData(
            user_id=user_id,
            email=data.get("email", ""),
            role=data.get("role", "viewer"),
            groups=data.get("groups", []),
            created_at=now,
            last_accessed=now,
            metadata=data.get("metadata", {}),
        )

        key = self._make_key(session_id)
        await self._redis.set(
            key,
            session_data.model_dump_json(),
            ex=self._default_ttl,
        )

        return session_id

    async def get(self, session_id: str) -> Optional[SessionData]:
        """Retrieve a session by ID.

        Updates the last_accessed timestamp on successful retrieval.

        Args:
            session_id: The session identifier.

        Returns:
            SessionData if the session exists, None otherwise.
        """
        key = self._make_key(session_id)
        raw = await self._redis.get(key)

        if raw is None:
            return None

        session_data = SessionData.model_validate_json(raw)
        # Update last_accessed timestamp
        session_data.last_accessed = time.time()
        # Persist updated timestamp without resetting TTL
        ttl = await self._redis.ttl(key)
        if ttl > 0:
            await self._redis.set(key, session_data.model_dump_json(), ex=ttl)
        else:
            await self._redis.set(key, session_data.model_dump_json(), ex=self._default_ttl)

        return session_data

    async def refresh(self, session_id: str, ttl: Optional[int] = None) -> None:
        """Refresh the TTL on an existing session.

        Args:
            session_id: The session identifier.
            ttl: New TTL in seconds. Uses default_ttl if not specified.
        """
        key = self._make_key(session_id)
        effective_ttl = ttl if ttl is not None else self._default_ttl
        # Only refresh if the session exists
        exists = await self._redis.exists(key)
        if exists:
            await self._redis.expire(key, effective_ttl)

    async def destroy(self, session_id: str) -> None:
        """Delete a session from Redis.

        Args:
            session_id: The session identifier to remove.
        """
        key = self._make_key(session_id)
        await self._redis.delete(key)
