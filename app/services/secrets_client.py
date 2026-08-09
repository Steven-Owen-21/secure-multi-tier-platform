"""Secrets Manager client with credential caching and rotation fallback.

Retrieves database and Redis credentials from AWS Secrets Manager,
caches them locally with a configurable TTL (default 30 days) to minimise
API calls, and falls back to previous credentials on rotation failure.
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Credentials:
    """Represents a set of credentials retrieved from Secrets Manager."""

    username: str
    password: str
    host: str | None = None
    port: int | None = None
    dbname: str | None = None
    engine: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert credentials to a dictionary."""
        return {
            "username": self.username,
            "password": self.password,
            "host": self.host,
            "port": self.port,
            "dbname": self.dbname,
            "engine": self.engine,
        }


@dataclass
class _CachedCredential:
    """Internal cache entry holding credentials and fetch timestamp."""

    credentials: Credentials
    fetched_at: float  # Unix timestamp when credentials were fetched


@dataclass
class SecretsClient:
    """Client for retrieving credentials from AWS Secrets Manager.

    Caches credentials locally with a configurable TTL matching the rotation
    schedule (default 30 days). Falls back to previous credentials on rotation
    failure to ensure zero-downtime operation.
    """

    endpoint_url: str | None = None
    region_name: str = "eu-west-2"
    cache_ttl_seconds: int = 86400 * 30  # 30 days default
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None

    # Internal state
    _cache: dict[str, _CachedCredential] = field(default_factory=dict, init=False, repr=False)
    _previous: dict[str, Credentials] = field(default_factory=dict, init=False, repr=False)
    _client: Any = field(default=None, init=False, repr=False)

    def _get_boto_client(self) -> Any:
        """Lazily create and return the boto3 Secrets Manager client."""
        if self._client is None:
            kwargs: dict[str, Any] = {
                "service_name": "secretsmanager",
                "region_name": self.region_name,
            }
            if self.endpoint_url:
                kwargs["endpoint_url"] = self.endpoint_url
            if self.aws_access_key_id:
                kwargs["aws_access_key_id"] = self.aws_access_key_id
            if self.aws_secret_access_key:
                kwargs["aws_secret_access_key"] = self.aws_secret_access_key
            self._client = boto3.client(**kwargs)
        return self._client

    def is_cache_valid(self, secret_arn: str) -> bool:
        """Check whether cached credentials for the given ARN are still within TTL.

        Returns True if credentials are cached and the time elapsed since fetch
        is less than cache_ttl_seconds.
        """
        entry = self._cache.get(secret_arn)
        if entry is None:
            return False
        elapsed = time.time() - entry.fetched_at
        return elapsed < self.cache_ttl_seconds

    async def get_credentials(self, secret_arn: str) -> Credentials:
        """Retrieve credentials for the given secret ARN.

        Returns cached credentials if TTL has not expired. Otherwise fetches
        fresh credentials from Secrets Manager. On fetch failure, falls back
        to the previous credentials if available.
        """
        if self.is_cache_valid(secret_arn):
            logger.debug("Returning cached credentials for %s", secret_arn)
            return self._cache[secret_arn].credentials

        # TTL expired or no cache — fetch fresh credentials
        return await self.refresh_credentials(secret_arn)

    async def refresh_credentials(self, secret_arn: str) -> Credentials:
        """Force-fetch fresh credentials from Secrets Manager.

        On success, updates the cache and stores the previous credentials
        for fallback. On failure, falls back to the previous credentials
        if available, otherwise raises the original exception.
        """
        try:
            credentials = await self._fetch_secret(secret_arn)

            # Preserve old credentials as fallback before updating cache
            old_entry = self._cache.get(secret_arn)
            if old_entry is not None:
                self._previous[secret_arn] = old_entry.credentials

            self._cache[secret_arn] = _CachedCredential(
                credentials=credentials,
                fetched_at=time.time(),
            )

            logger.info("Successfully refreshed credentials for %s", secret_arn)
            return credentials

        except (ClientError, Exception) as exc:
            logger.warning(
                "Failed to refresh credentials for %s: %s. Attempting fallback.",
                secret_arn,
                exc,
            )
            return self._fallback(secret_arn, exc)

    def _fallback(self, secret_arn: str, original_error: Exception) -> Credentials:
        """Fall back to previous credentials on rotation/fetch failure.

        Priority:
        1. Previously cached credentials (from _previous map)
        2. Current cache entry (even if expired)
        3. Raise the original error if no fallback available
        """
        # Try previous credentials first (stored before last successful refresh)
        if secret_arn in self._previous:
            logger.warning(
                "Falling back to previous credentials for %s",
                secret_arn,
            )
            return self._previous[secret_arn]

        # Try expired cache entry as last resort
        if secret_arn in self._cache:
            logger.warning(
                "Falling back to expired cached credentials for %s",
                secret_arn,
            )
            return self._cache[secret_arn].credentials

        # No fallback available
        logger.error(
            "No fallback credentials available for %s",
            secret_arn,
        )
        raise original_error

    async def _fetch_secret(self, secret_arn: str) -> Credentials:
        """Fetch and parse secret value from Secrets Manager.

        Runs the synchronous boto3 call in an executor to avoid blocking
        the async event loop.
        """
        loop = asyncio.get_event_loop()
        client = self._get_boto_client()

        response = await loop.run_in_executor(
            None,
            lambda: client.get_secret_value(SecretId=secret_arn),
        )

        secret_string = response.get("SecretString")
        if not secret_string:
            raise ValueError(f"Secret {secret_arn} has no SecretString value")

        secret_data = json.loads(secret_string)
        return Credentials(
            username=secret_data.get("username", ""),
            password=secret_data.get("password", ""),
            host=secret_data.get("host"),
            port=int(secret_data["port"]) if secret_data.get("port") else None,
            dbname=secret_data.get("dbname"),
            engine=secret_data.get("engine"),
        )
