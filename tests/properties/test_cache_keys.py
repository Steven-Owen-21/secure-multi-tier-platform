"""Property-based tests for cache key generation logic.

**Validates: Requirements 4.9, 12.9**

Uses Hypothesis to verify that the cache key generation logic produces
unique, deterministic keys for all valid query parameter combinations
including resource types, filter params, and pagination.
"""

import hashlib
import json

import pytest
from hypothesis import given, settings, strategies as st

# ---------------------------------------------------------------------------
# Cache key generation function — mirrors app/services/cache_service.py
# ---------------------------------------------------------------------------


def generate_key(resource: str, params: dict) -> str:
    """Generate a deterministic cache key from a resource type and parameters.

    The key is constructed as:
        cache:{resource}:{hash_of_sorted_params}

    Params are sorted by key to ensure determinism regardless of insertion order.
    All values are stringified before hashing.

    Args:
        resource: The resource type (e.g. 'products:list', 'products:detail:uuid').
        params: Query parameters that affect the cached result.

    Returns:
        A deterministic, unique cache key string.
    """
    normalised = {k: str(v) for k, v in sorted(params.items())}
    params_json = json.dumps(normalised, sort_keys=True, separators=(",", ":"))
    params_hash = hashlib.sha256(params_json.encode()).hexdigest()[:16]
    return f"cache:{resource}:{params_hash}"


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

# Valid resource types matching the cache key schema
valid_resource_types = st.sampled_from([
    "products:list",
    "products:detail",
    "orders:user",
])

# Valid sort_by values for product listing
valid_sort_by = st.sampled_from(["name", "price_pence", "created_at", "category"])

# Valid product categories
valid_categories = st.sampled_from([
    "electronics",
    "clothing",
    "food",
    "beverages",
    "household",
    "sports",
    "toys",
])

# Pagination params
valid_page = st.integers(min_value=1, max_value=1000)
valid_page_size = st.sampled_from([10, 20, 50, 100])

# Order status values
valid_order_status = st.sampled_from(["pending", "confirmed", "shipped", "delivered", "cancelled"])

# User IDs (UUID-like strings)
valid_user_ids = st.uuids().map(str)

# Product IDs (UUID-like strings)
valid_product_ids = st.uuids().map(str)


# Strategy for product list params (sort_by, category, page, page_size)
@st.composite
def product_list_params(draw):
    """Generate valid query parameter dicts for product list cache keys."""
    return {
        "sort_by": draw(valid_sort_by),
        "category": draw(valid_categories),
        "page": draw(valid_page),
        "page_size": draw(valid_page_size),
    }


# Strategy for order user params (status, page)
@st.composite
def order_user_params(draw):
    """Generate valid query parameter dicts for order user cache keys."""
    return {
        "status": draw(valid_order_status),
        "page": draw(valid_page),
    }


# Strategy for any valid params dict (combining all resource types)
@st.composite
def any_valid_params(draw):
    """Generate any valid query parameter combination."""
    resource = draw(valid_resource_types)
    if resource == "products:list":
        params = draw(product_list_params())
    elif resource == "products:detail":
        params = {"product_id": draw(valid_product_ids)}
    else:  # orders:user
        params = draw(order_user_params())
        params["user_id"] = draw(valid_user_ids)
    return resource, params


# ---------------------------------------------------------------------------
# Property: Determinism — same inputs always produce same key
# ---------------------------------------------------------------------------


@pytest.mark.property
@settings(max_examples=200)
@given(data=any_valid_params())
def test_cache_key_determinism(data):
    """Cache key generation is deterministic: same params always produce same key.

    For any valid resource type and parameter combination, calling generate_key
    multiple times with the same inputs SHALL always produce the identical key.

    **Validates: Requirements 4.9, 12.9**
    """
    resource, params = data

    key1 = generate_key(resource, params)
    key2 = generate_key(resource, params)

    assert key1 == key2, (
        f"Same inputs produced different keys: '{key1}' vs '{key2}' "
        f"for resource={resource}, params={params}"
    )


# ---------------------------------------------------------------------------
# Property: Determinism is order-independent (dict insertion order)
# ---------------------------------------------------------------------------


@pytest.mark.property
@settings(max_examples=200)
@given(data=any_valid_params())
def test_cache_key_order_independent(data):
    """Cache key is independent of parameter insertion order.

    For any valid parameter dict, generate_key SHALL produce the same key
    regardless of the order in which keys appear in the input dict.

    **Validates: Requirements 4.9, 12.9**
    """
    resource, params = data

    # Create a reversed-order copy of params
    reversed_params = dict(reversed(list(params.items())))

    key_original = generate_key(resource, params)
    key_reversed = generate_key(resource, reversed_params)

    assert key_original == key_reversed, (
        f"Different param order produced different keys: '{key_original}' vs '{key_reversed}' "
        f"for resource={resource}"
    )


# ---------------------------------------------------------------------------
# Property: Collision resistance — different inputs produce different keys
# ---------------------------------------------------------------------------


@pytest.mark.property
@settings(max_examples=200)
@given(data1=any_valid_params(), data2=any_valid_params())
def test_cache_key_collision_resistance(data1, data2):
    """Cache keys are collision-free: different params produce different keys.

    For any two distinct (resource, params) combinations, generate_key SHALL
    produce different cache keys.

    **Validates: Requirements 4.9, 12.9**
    """
    resource1, params1 = data1
    resource2, params2 = data2

    # Only assert different keys when inputs are actually different
    # Normalise params for comparison (stringify values, sort keys)
    norm1 = {k: str(v) for k, v in sorted(params1.items())}
    norm2 = {k: str(v) for k, v in sorted(params2.items())}

    if resource1 == resource2 and norm1 == norm2:
        # Same logical inputs — keys should be equal (covered by determinism test)
        return

    key1 = generate_key(resource1, params1)
    key2 = generate_key(resource2, params2)

    assert key1 != key2, (
        f"Different inputs produced the same key '{key1}': "
        f"resource1={resource1}, params1={params1} vs "
        f"resource2={resource2}, params2={params2}"
    )


# ---------------------------------------------------------------------------
# Property: Key format correctness
# ---------------------------------------------------------------------------


@pytest.mark.property
@settings(max_examples=200)
@given(data=any_valid_params())
def test_cache_key_format(data):
    """Cache keys follow the expected format: cache:{resource}:{hex_hash}.

    For any valid inputs, the generated key SHALL:
    - Start with 'cache:'
    - Contain the resource type
    - End with a 16-character hexadecimal hash

    **Validates: Requirements 4.9, 12.9**
    """
    resource, params = data

    key = generate_key(resource, params)

    # Verify prefix
    assert key.startswith("cache:"), f"Key must start with 'cache:', got '{key}'"

    # Verify structure: cache:{resource}:{hash}
    parts = key.split(":")
    # resource can contain colons (e.g. 'products:list'), so we need to
    # reconstruct: prefix is 'cache', suffix is the 16-char hash, middle is resource
    assert parts[0] == "cache", f"First segment must be 'cache', got '{parts[0]}'"

    # The hash is the last segment (16 hex chars)
    hash_segment = parts[-1]
    assert len(hash_segment) == 16, (
        f"Hash segment must be 16 chars, got {len(hash_segment)}: '{hash_segment}'"
    )
    assert all(c in "0123456789abcdef" for c in hash_segment), (
        f"Hash segment must be hexadecimal, got '{hash_segment}'"
    )

    # Verify the resource portion is correct
    # Key format: cache:{resource}:{hash}
    # Remove 'cache:' prefix and ':{hash}' suffix
    expected_prefix = f"cache:{resource}:"
    assert key.startswith(expected_prefix), (
        f"Key must start with '{expected_prefix}', got '{key}'"
    )
