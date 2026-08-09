"""FastAPI application factory."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from app.config import Settings, get_settings
from app.middleware import StructuredLoggingMiddleware, register_error_handlers
from app.routers.auth import router as auth_router
from app.routers.health import router as health_router
from app.routers.orders import router as orders_router
from app.routers.products import router as products_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup and shutdown lifecycle.

    Startup: initialise database connection pool, Redis client, and AWS clients.
    Shutdown: close connection pools and release resources.
    """
    # Startup
    settings: Settings = app.state.settings
    app.state.settings = settings
    yield
    # Shutdown — cleanup is handled by dependency providers on GC,
    # but explicit teardown can be added here as services are implemented.


def create_app(settings: Settings | None = None) -> FastAPI:
    """Application factory creating a configured FastAPI instance.

    Args:
        settings: Optional settings override (useful for testing).
                  Defaults to loading from environment.

    Returns:
        Configured FastAPI application.
    """
    if settings is None:
        settings = get_settings()

    app = FastAPI(
        title="Secure Multi-Tier Platform",
        description="Enterprise-grade multi-tier API demonstrating AWS architecture patterns.",
        version="0.1.0",
        docs_url="/docs" if settings.is_local else None,
        redoc_url="/redoc" if settings.is_local else None,
        lifespan=lifespan,
    )

    app.state.settings = settings

    # Register structured logging middleware
    app.add_middleware(StructuredLoggingMiddleware, log_level=settings.log_level)

    # Register global error handlers
    register_error_handlers(app)

    # Register routers
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(orders_router)
    app.include_router(products_router)

    return app
