"""Dependency injection providers for FastAPI.

Provides request-scoped dependencies for database sessions, cache client,
authentication service, and secrets client. Each dependency is obtained via
FastAPI's Depends() mechanism.

In non-local environments the DB session factory and Redis client use
credentials dynamically retrieved from AWS Secrets Manager via SecretsClient.
In local development mode the static URLs from Settings are used directly.
"""

import logging
from typing import Annotated, AsyncGenerator
from urllib.parse import quote_plus

import redis.asyncio as aioredis
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Secrets client (declared early — used by DB and Redis providers below)
# ---------------------------------------------------------------------------

from app.services.secrets_client import Credentials, SecretsClient  # noqa: E402

_secrets_client_cache: dict[str, SecretsClient] = {}


def _get_settings(request: Request) -> Settings:
    """Extract settings from application state."""
    return request.app.state.settings


async def get_secrets_client(
    settings: Annotated[Settings, Depends(_get_settings)],
) -> SecretsClient:
    """Provide the Secrets Manager client (singleton per configuration)."""
    key = f"{settings.aws_endpoint_url}:{settings.aws_default_region}"
    if key not in _secrets_client_cache:
        _secrets_client_cache[key] = SecretsClient(
            endpoint_url=settings.aws_endpoint_url,
            region_name=settings.aws_default_region,
            cache_ttl_seconds=settings.secrets_cache_ttl,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
        )
    return _secrets_client_cache[key]


# ---------------------------------------------------------------------------
# Credential helpers — build connection URLs from Secrets Manager credentials
# ---------------------------------------------------------------------------


def _build_database_url(creds: Credentials, settings: Settings) -> str:
    """Build an asyncpg database URL from Secrets Manager credentials.

    Falls back to the static settings.database_url if credentials are
    incomplete (e.g. missing host or dbname).
    """
    if not creds.host or not creds.dbname:
        logger.warning(
            "Incomplete DB credentials from Secrets Manager; falling back to static URL"
        )
        return settings.database_url

    user = quote_plus(creds.username)
    password = quote_plus(creds.password)
    port = creds.port or 5432
    return f"postgresql+asyncpg://{user}:{password}@{creds.host}:{port}/{creds.dbname}"


def _build_redis_url(creds: Credentials, settings: Settings) -> str:
    """Build a Redis URL from Secrets Manager credentials.

    Falls back to the static settings.redis_url if credentials are
    incomplete (e.g. missing host).
    """
    if not creds.host:
        logger.warning(
            "Incomplete Redis credentials from Secrets Manager; falling back to static URL"
        )
        return settings.redis_url

    password = quote_plus(creds.password)
    port = creds.port or 6379
    scheme = "rediss" if settings.redis_ssl_enabled else "redis"
    return f"{scheme}://:{password}@{creds.host}:{port}/0"


# ---------------------------------------------------------------------------
# Database session
# ---------------------------------------------------------------------------

_engine_cache: dict[str, object] = {}
_session_factory_cache: dict[str, async_sessionmaker[AsyncSession]] = {}


def _get_session_factory(dsn: str, settings: Settings) -> async_sessionmaker[AsyncSession]:
    """Get or create a cached async session factory for the given DSN."""
    if dsn not in _session_factory_cache:
        connect_args: dict[str, object] = {}
        if settings.db_ssl_required:
            connect_args["ssl"] = True

        engine = create_async_engine(
            dsn,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            connect_args=connect_args,
            echo=settings.log_level == "DEBUG",
        )
        _engine_cache[dsn] = engine
        _session_factory_cache[dsn] = async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
    return _session_factory_cache[dsn]


async def get_db_session(
    settings: Annotated[Settings, Depends(_get_settings)],
    secrets_client: Annotated[SecretsClient, Depends(get_secrets_client)],
) -> AsyncGenerator[AsyncSession, None]:
    """Yield a request-scoped async database session.

    In non-local environments credentials are fetched from Secrets Manager
    (cached per TTL). In local mode the static database_url is used.

    The session is committed on success and rolled back on exception,
    then closed when the request finishes.
    """
    if settings.is_local:
        dsn = settings.database_url
    else:
        creds = await secrets_client.get_credentials(settings.secrets_db_arn)
        dsn = _build_database_url(creds, settings)

    factory = _get_session_factory(dsn, settings)
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ---------------------------------------------------------------------------
# Redis / cache client
# ---------------------------------------------------------------------------

_redis_cache: dict[str, aioredis.Redis] = {}


def _get_redis_client(url: str, settings: Settings) -> aioredis.Redis:
    """Get or create a cached Redis client for the given URL."""
    if url not in _redis_cache:
        _redis_cache[url] = aioredis.from_url(
            url,
            decode_responses=True,
            ssl=settings.redis_ssl_enabled,
            retry_on_timeout=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
    return _redis_cache[url]


async def get_cache_client(
    settings: Annotated[Settings, Depends(_get_settings)],
    secrets_client: Annotated[SecretsClient, Depends(get_secrets_client)],
) -> aioredis.Redis:
    """Provide a Redis client for cache and session operations.

    In non-local environments credentials are fetched from Secrets Manager
    (cached per TTL). In local mode the static redis_url is used.
    """
    if settings.is_local:
        url = settings.redis_url
    else:
        creds = await secrets_client.get_credentials(settings.secrets_redis_arn)
        url = _build_redis_url(creds, settings)

    return _get_redis_client(url, settings)


# ---------------------------------------------------------------------------
# Auth service
# ---------------------------------------------------------------------------

from app.services.auth_service import AuthService  # noqa: E402


_auth_service_cache: dict[str, AuthService] = {}


async def get_auth_service(
    settings: Annotated[Settings, Depends(_get_settings)],
) -> AuthService:
    """Provide the authentication/authorization service."""
    key = f"{settings.cognito_jwks_url}:{settings.cognito_client_id}"
    if key not in _auth_service_cache:
        _auth_service_cache[key] = AuthService(
            jwks_url=settings.cognito_jwks_url,
            client_id=settings.cognito_client_id,
            user_pool_id=settings.cognito_user_pool_id,
            region=settings.cognito_region,
        )
    return _auth_service_cache[key]


# ---------------------------------------------------------------------------
# Type aliases for use in route handlers via Annotated[..., Depends(...)]
# ---------------------------------------------------------------------------

DBSession = Annotated[AsyncSession, Depends(get_db_session)]
CacheClient = Annotated[aioredis.Redis, Depends(get_cache_client)]
Auth = Annotated[AuthService, Depends(get_auth_service)]
Secrets = Annotated[SecretsClient, Depends(get_secrets_client)]
