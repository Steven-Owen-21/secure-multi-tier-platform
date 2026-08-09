"""SQLAlchemy async engine and session factory.

Provides the canonical engine/session creation for the platform with:
- Connection pool: pool_size=10, max_overflow=20 (configurable via Settings)
- SSL enforcement when db_ssl_required=True
- Echo mode in DEBUG log level for development visibility
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import Settings, get_settings

# Module-level caches to ensure a single engine/factory per DSN
_engines: dict[str, AsyncEngine] = {}
_session_factories: dict[str, async_sessionmaker[AsyncSession]] = {}


def get_async_engine(settings: Settings | None = None) -> AsyncEngine:
    """Create or return a cached async engine for the configured database URL.

    Parameters
    ----------
    settings:
        Application settings instance. Defaults to get_settings() if not provided.

    Returns
    -------
    AsyncEngine configured with pool_size, max_overflow, and SSL settings.
    """
    if settings is None:
        settings = get_settings()

    dsn = settings.database_url

    if dsn not in _engines:
        connect_args: dict[str, object] = {}
        if settings.db_ssl_required:
            connect_args["ssl"] = True

        _engines[dsn] = create_async_engine(
            dsn,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            connect_args=connect_args,
            echo=(settings.log_level == "DEBUG"),
        )

    return _engines[dsn]


def get_async_session_factory(
    settings: Settings | None = None,
) -> async_sessionmaker[AsyncSession]:
    """Create or return a cached async session factory.

    Parameters
    ----------
    settings:
        Application settings instance. Defaults to get_settings() if not provided.

    Returns
    -------
    An async_sessionmaker bound to the platform's engine with
    expire_on_commit=False for safe post-commit attribute access.
    """
    if settings is None:
        settings = get_settings()

    dsn = settings.database_url

    if dsn not in _session_factories:
        engine = get_async_engine(settings)
        _session_factories[dsn] = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    return _session_factories[dsn]
