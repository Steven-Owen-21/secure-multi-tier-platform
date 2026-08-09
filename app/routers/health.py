"""Health check endpoint verifying platform dependency connectivity.

Returns HTTP 200 when all dependencies (Database_Cluster, Cache_Cluster)
are reachable, and HTTP 503 with degradation details when any dependency
is unreachable.
"""

import time
from datetime import datetime, timezone
from typing import Literal, Optional

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_cache_client, get_db_session

router = APIRouter()


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class ComponentHealth(BaseModel):
    """Health status for an individual platform component."""

    name: str
    status: Literal["healthy", "unhealthy", "degraded"]
    latency_ms: Optional[float] = None
    error: Optional[str] = None


class HealthResponse(BaseModel):
    """Aggregate health response for the platform."""

    status: Literal["healthy", "unhealthy", "degraded"]
    components: list[ComponentHealth]
    timestamp: datetime


# ---------------------------------------------------------------------------
# Health checker
# ---------------------------------------------------------------------------


class HealthChecker:
    """Verifies connectivity to Database_Cluster and Cache_Cluster.

    Each check measures latency and captures errors. The aggregate status
    is 'healthy' only when all components report healthy; otherwise it is
    'unhealthy'.
    """

    def __init__(
        self,
        db_session: AsyncSession,
        cache_client: aioredis.Redis,
    ) -> None:
        self._db_session = db_session
        self._cache_client = cache_client

    async def check_database(self) -> ComponentHealth:
        """Verify Database_Cluster connectivity with a lightweight query."""
        start = time.perf_counter()
        try:
            await self._db_session.execute(text("SELECT 1"))
            latency = (time.perf_counter() - start) * 1000
            return ComponentHealth(
                name="Database_Cluster",
                status="healthy",
                latency_ms=round(latency, 2),
            )
        except Exception as exc:
            latency = (time.perf_counter() - start) * 1000
            return ComponentHealth(
                name="Database_Cluster",
                status="unhealthy",
                latency_ms=round(latency, 2),
                error=str(exc),
            )

    async def check_cache(self) -> ComponentHealth:
        """Verify Cache_Cluster connectivity with a PING command."""
        start = time.perf_counter()
        try:
            await self._cache_client.ping()
            latency = (time.perf_counter() - start) * 1000
            return ComponentHealth(
                name="Cache_Cluster",
                status="healthy",
                latency_ms=round(latency, 2),
            )
        except Exception as exc:
            latency = (time.perf_counter() - start) * 1000
            return ComponentHealth(
                name="Cache_Cluster",
                status="unhealthy",
                latency_ms=round(latency, 2),
                error=str(exc),
            )

    async def check_all(self) -> HealthResponse:
        """Run all dependency checks and produce an aggregate response."""
        db_health = await self.check_database()
        cache_health = await self.check_cache()

        components = [db_health, cache_health]

        all_healthy = all(c.status == "healthy" for c in components)
        aggregate_status: Literal["healthy", "unhealthy", "degraded"] = (
            "healthy" if all_healthy else "unhealthy"
        )

        return HealthResponse(
            status=aggregate_status,
            components=components,
            timestamp=datetime.now(timezone.utc),
        )


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Platform health check",
    description=(
        "Verifies connectivity to Database_Cluster and Cache_Cluster. "
        "Returns 200 when all healthy, 503 when any dependency is unreachable."
    ),
)
async def health_check(
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
    cache_client: aioredis.Redis = Depends(get_cache_client),
) -> HealthResponse:
    """GET /health — verify platform dependency health."""
    checker = HealthChecker(db_session=db_session, cache_client=cache_client)
    result = await checker.check_all()

    if result.status != "healthy":
        response.status_code = 503

    return result
