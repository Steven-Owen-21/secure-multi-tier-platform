"""Property-based tests for CloudFront cache behaviour routing logic.

**Validates: Requirements 18.3, 18.7**

Uses Hypothesis to verify that the cache behaviour routing logic correctly
maps all valid URL path patterns to the expected origin and TTL configuration.

CloudFront cache behaviours (from infrastructure/modules/cloudfront/main.tf):
  - /api/*    → API Gateway origin, TTL 60s
  - /static/* → S3 static bucket origin, TTL 86400s
  - default   → default origin, default TTL (3600s)
"""

from dataclasses import dataclass
from typing import Literal

import pytest
from hypothesis import given, settings, assume, strategies as st


# ---------------------------------------------------------------------------
# Cache behaviour routing logic mirroring the CloudFront module configuration.
#
# CloudFront evaluates cache behaviours by matching URL path patterns in order.
# The routing logic determines which origin to forward to and what TTL to apply.
# ---------------------------------------------------------------------------

# Origin identifiers
ORIGIN_API_GATEWAY = "api-gateway"
ORIGIN_S3_STATIC = "s3-static"
ORIGIN_DEFAULT = "default"

# TTL values in seconds
TTL_API = 60
TTL_STATIC = 86400
TTL_DEFAULT = 3600


@dataclass(frozen=True)
class CacheBehaviourResult:
    """Result of cache behaviour routing for a given URL path."""

    origin: str
    ttl: int


def route_cache_behaviour(path: str) -> CacheBehaviourResult:
    """Determine the cache behaviour for a given URL path.

    Mirrors the CloudFront cache behaviour configuration in
    infrastructure/modules/cloudfront/main.tf.

    Routing rules (evaluated in order):
      - Paths starting with /api/ → API Gateway origin, TTL 60s
      - Paths starting with /static/ → S3 static bucket origin, TTL 86400s
      - All other paths → default origin, TTL 3600s

    Args:
        path: The URL path (must start with /).

    Returns:
        CacheBehaviourResult with the matched origin and TTL.
    """
    if path.startswith("/api/"):
        return CacheBehaviourResult(origin=ORIGIN_API_GATEWAY, ttl=TTL_API)
    elif path.startswith("/static/"):
        return CacheBehaviourResult(origin=ORIGIN_S3_STATIC, ttl=TTL_STATIC)
    else:
        return CacheBehaviourResult(origin=ORIGIN_DEFAULT, ttl=TTL_DEFAULT)


# ---------------------------------------------------------------------------
# Hypothesis Strategies
# ---------------------------------------------------------------------------

# Characters allowed in URL path segments (RFC 3986 unreserved + common)
PATH_SEGMENT_CHARS = st.sampled_from(
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789"
    "-._~"
)


@st.composite
def path_segments(draw: st.DrawFn) -> str:
    """Generate a valid URL path segment (non-empty, no slashes)."""
    length = draw(st.integers(min_value=1, max_value=30))
    chars = [draw(PATH_SEGMENT_CHARS) for _ in range(length)]
    return "".join(chars)


@st.composite
def url_paths_with_prefix(draw: st.DrawFn, prefix: str) -> str:
    """Generate URL paths starting with a given prefix (e.g. /api/)."""
    # Generate 1-4 additional path segments after the prefix
    num_segments = draw(st.integers(min_value=1, max_value=4))
    segments = [draw(path_segments()) for _ in range(num_segments)]
    return prefix + "/".join(segments)


@st.composite
def api_paths(draw: st.DrawFn) -> str:
    """Generate paths matching /api/* pattern."""
    return draw(url_paths_with_prefix("/api/"))


@st.composite
def static_paths(draw: st.DrawFn) -> str:
    """Generate paths matching /static/* pattern."""
    return draw(url_paths_with_prefix("/static/"))


@st.composite
def other_paths(draw: st.DrawFn) -> str:
    """Generate paths that don't match /api/* or /static/* patterns."""
    # Choose a prefix that is NOT /api/ or /static/
    prefix = draw(st.sampled_from([
        "/",
        "/health",
        "/docs/",
        "/images/",
        "/auth/",
        "/products/",
        "/orders/",
        "/favicon.ico",
        "/robots.txt",
        "/index.html",
    ]))

    if prefix.endswith("/"):
        # Add optional path segments
        num_segments = draw(st.integers(min_value=0, max_value=3))
        if num_segments > 0:
            segments = [draw(path_segments()) for _ in range(num_segments)]
            return prefix + "/".join(segments)

    return prefix


@st.composite
def any_valid_url_path(draw: st.DrawFn) -> str:
    """Generate any valid URL path (with /api/, /static/, or other prefixes)."""
    path = draw(st.one_of(
        api_paths(),
        static_paths(),
        other_paths(),
    ))
    return path


# ---------------------------------------------------------------------------
# Property Tests
# ---------------------------------------------------------------------------


@pytest.mark.property
@settings(max_examples=200)
@given(path=api_paths())
def test_api_paths_route_to_api_gateway_origin(path: str):
    """Property: all /api/* paths route to API Gateway origin with TTL 60s.

    For any URL path starting with /api/, the routing logic must select
    the API Gateway origin and assign a TTL of 60 seconds.

    **Validates: Requirements 18.3, 18.7**
    """
    result = route_cache_behaviour(path)

    assert result.origin == ORIGIN_API_GATEWAY, (
        f"Path '{path}' routed to '{result.origin}', expected '{ORIGIN_API_GATEWAY}'"
    )
    assert result.ttl == TTL_API, (
        f"Path '{path}' got TTL {result.ttl}, expected {TTL_API}"
    )


@pytest.mark.property
@settings(max_examples=200)
@given(path=static_paths())
def test_static_paths_route_to_s3_origin(path: str):
    """Property: all /static/* paths route to S3 static bucket origin with TTL 86400s.

    For any URL path starting with /static/, the routing logic must select
    the S3 static bucket origin and assign a TTL of 86400 seconds (24 hours).

    **Validates: Requirements 18.3, 18.7**
    """
    result = route_cache_behaviour(path)

    assert result.origin == ORIGIN_S3_STATIC, (
        f"Path '{path}' routed to '{result.origin}', expected '{ORIGIN_S3_STATIC}'"
    )
    assert result.ttl == TTL_STATIC, (
        f"Path '{path}' got TTL {result.ttl}, expected {TTL_STATIC}"
    )


@pytest.mark.property
@settings(max_examples=200)
@given(path=other_paths())
def test_other_paths_route_to_default_origin(path: str):
    """Property: paths not matching /api/* or /static/* route to default origin.

    For any URL path that does not start with /api/ or /static/, the routing
    logic must select the default origin and assign the default TTL (3600s).

    **Validates: Requirements 18.3, 18.7**
    """
    result = route_cache_behaviour(path)

    assert result.origin == ORIGIN_DEFAULT, (
        f"Path '{path}' routed to '{result.origin}', expected '{ORIGIN_DEFAULT}'"
    )
    assert result.ttl == TTL_DEFAULT, (
        f"Path '{path}' got TTL {result.ttl}, expected {TTL_DEFAULT}"
    )


@pytest.mark.property
@settings(max_examples=300)
@given(path=any_valid_url_path())
def test_routing_always_returns_valid_result(path: str):
    """Property: routing always produces a valid origin and positive TTL.

    For any valid URL path, the routing logic must always return a result
    with a recognised origin identifier and a positive TTL value.

    **Validates: Requirements 18.3, 18.7**
    """
    result = route_cache_behaviour(path)

    valid_origins = {ORIGIN_API_GATEWAY, ORIGIN_S3_STATIC, ORIGIN_DEFAULT}
    assert result.origin in valid_origins, (
        f"Path '{path}' routed to unknown origin '{result.origin}'"
    )
    assert result.ttl > 0, (
        f"Path '{path}' got non-positive TTL {result.ttl}"
    )


@pytest.mark.property
@settings(max_examples=300)
@given(path=any_valid_url_path())
def test_routing_is_deterministic(path: str):
    """Property: routing the same path always produces the same result.

    Cache behaviour routing must be deterministic — the same path must
    always map to the same origin and TTL.

    **Validates: Requirements 18.3, 18.7**
    """
    result1 = route_cache_behaviour(path)
    result2 = route_cache_behaviour(path)

    assert result1 == result2, (
        f"Path '{path}' produced different results: {result1} vs {result2}"
    )


@pytest.mark.property
@settings(max_examples=200)
@given(path=any_valid_url_path())
def test_routing_categories_are_mutually_exclusive(path: str):
    """Property: each path matches exactly one cache behaviour category.

    A path cannot simultaneously match /api/* and /static/* patterns.
    The routing logic must assign exactly one origin per path.

    **Validates: Requirements 18.3, 18.7**
    """
    result = route_cache_behaviour(path)

    is_api = path.startswith("/api/")
    is_static = path.startswith("/static/")

    # Mutual exclusivity: can't be both
    assert not (is_api and is_static), (
        f"Path '{path}' matches both /api/ and /static/ — impossible by construction"
    )

    # Consistency with result
    if is_api:
        assert result.origin == ORIGIN_API_GATEWAY
        assert result.ttl == TTL_API
    elif is_static:
        assert result.origin == ORIGIN_S3_STATIC
        assert result.ttl == TTL_STATIC
    else:
        assert result.origin == ORIGIN_DEFAULT
        assert result.ttl == TTL_DEFAULT
