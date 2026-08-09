"""Property-based tests for health check response logic.

**Validates: Requirements 10.7**

Uses Hypothesis to verify that the aggregate health status correctly reflects
all valid combinations of dependency availability states.
"""

import pytest
from hypothesis import given, settings, strategies as st
from unittest.mock import AsyncMock, MagicMock

from app.routers.health import HealthChecker


@st.composite
def dependency_states(draw):
    """Generate all valid combinations of dependency availability states.

    Each dependency (database, cache) can be either healthy or unhealthy.
    """
    db_healthy = draw(st.booleans())
    cache_healthy = draw(st.booleans())
    return db_healthy, cache_healthy


def make_db_session(healthy: bool) -> AsyncMock:
    """Create a mock DB session that is healthy or raises on execute."""
    session = AsyncMock()
    if healthy:
        session.execute = AsyncMock(return_value=MagicMock())
    else:
        session.execute = AsyncMock(side_effect=ConnectionError("Database unreachable"))
    return session


def make_cache_client(healthy: bool) -> AsyncMock:
    """Create a mock Redis client that is healthy or raises on ping."""
    client = AsyncMock()
    if healthy:
        client.ping = AsyncMock(return_value=True)
    else:
        client.ping = AsyncMock(side_effect=ConnectionError("Cache unreachable"))
    return client


@pytest.mark.property
@settings(max_examples=50)
@given(states=dependency_states())
async def test_aggregate_health_status_reflects_component_states(states):
    """Property: aggregate status is 'healthy' iff ALL components are healthy.

    For any combination of (db_healthy, cache_healthy):
    - If all are True → status == "healthy"
    - If any is False → status == "unhealthy"

    **Validates: Requirements 10.7**
    """
    db_healthy, cache_healthy = states

    db_session = make_db_session(db_healthy)
    cache_client = make_cache_client(cache_healthy)

    checker = HealthChecker(db_session=db_session, cache_client=cache_client)
    response = await checker.check_all()

    if db_healthy and cache_healthy:
        assert response.status == "healthy"
    else:
        assert response.status == "unhealthy"


@pytest.mark.property
@settings(max_examples=50)
@given(states=dependency_states())
async def test_component_count_matches_dependency_count(states):
    """Property: response always contains exactly 2 components (Database_Cluster, Cache_Cluster).

    **Validates: Requirements 10.7**
    """
    db_healthy, cache_healthy = states

    db_session = make_db_session(db_healthy)
    cache_client = make_cache_client(cache_healthy)

    checker = HealthChecker(db_session=db_session, cache_client=cache_client)
    response = await checker.check_all()

    assert len(response.components) == 2


@pytest.mark.property
@settings(max_examples=50)
@given(states=dependency_states())
async def test_individual_component_status_matches_availability(states):
    """Property: each component's individual status matches its availability state.

    - Healthy dependency → component status == "healthy"
    - Unhealthy dependency → component status == "unhealthy"

    **Validates: Requirements 10.7**
    """
    db_healthy, cache_healthy = states

    db_session = make_db_session(db_healthy)
    cache_client = make_cache_client(cache_healthy)

    checker = HealthChecker(db_session=db_session, cache_client=cache_client)
    response = await checker.check_all()

    # Find each component by name
    db_component = next(c for c in response.components if c.name == "Database_Cluster")
    cache_component = next(c for c in response.components if c.name == "Cache_Cluster")

    if db_healthy:
        assert db_component.status == "healthy"
        assert db_component.error is None
    else:
        assert db_component.status == "unhealthy"
        assert db_component.error is not None

    if cache_healthy:
        assert cache_component.status == "healthy"
        assert cache_component.error is None
    else:
        assert cache_component.status == "unhealthy"
        assert cache_component.error is not None


@pytest.mark.property
@settings(max_examples=50)
@given(states=dependency_states())
async def test_unhealthy_components_provide_degradation_details(states):
    """Property: when status is 'unhealthy', at least one component has error details.

    This validates the 503 response includes degradation details as required.

    **Validates: Requirements 10.7**
    """
    db_healthy, cache_healthy = states

    db_session = make_db_session(db_healthy)
    cache_client = make_cache_client(cache_healthy)

    checker = HealthChecker(db_session=db_session, cache_client=cache_client)
    response = await checker.check_all()

    if response.status == "unhealthy":
        unhealthy_components = [c for c in response.components if c.status == "unhealthy"]
        assert len(unhealthy_components) >= 1
        # Each unhealthy component must have error details
        for component in unhealthy_components:
            assert component.error is not None
            assert len(component.error) > 0
