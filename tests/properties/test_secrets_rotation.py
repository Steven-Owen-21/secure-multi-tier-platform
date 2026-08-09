"""Property-based tests for secrets rotation caching logic.

**Validates: Requirements 21.3, 21.7**

Uses Hypothesis to verify that the credential caching logic correctly handles
all rotation scenarios: cached credential returned before TTL expiry, fresh
fetch after TTL expiry, and fallback to previous credential on rotation failure.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import pytest
from hypothesis import given, settings, assume, strategies as st


# ---------------------------------------------------------------------------
# Simplified credential cache model — mirrors SecretsClient caching logic
# ---------------------------------------------------------------------------


class RotationOutcome(Enum):
    """Possible outcomes when attempting to fetch rotated credentials."""

    SUCCESS = "success"
    FAILURE = "failure"


@dataclass
class Credentials:
    """Represents a set of credentials (e.g. database username/password)."""

    username: str
    password: str
    version: int  # Tracks which rotation cycle this credential belongs to


@dataclass
class CredentialCache:
    """A simplified model of the SecretsClient credential caching logic.

    Mirrors the application's caching behaviour:
    - Credentials are cached locally for `ttl_seconds` after fetch.
    - When TTL expires, a fresh fetch is attempted from Secrets Manager.
    - On rotation failure, the previous (cached) credential is retained as fallback.

    This model uses elapsed time tracking rather than real clocks for testability.
    """

    ttl_seconds: int
    _current_credential: Optional[Credentials] = field(default=None, repr=False)
    _previous_credential: Optional[Credentials] = field(default=None, repr=False)
    _last_fetch_time: float = 0.0
    _current_time: float = 0.0

    def set_time(self, time: float) -> None:
        """Advance the model clock to the given time."""
        self._current_time = time

    def is_cache_valid(self) -> bool:
        """Check whether the cached credential is still within its TTL.

        Returns True if a credential is cached and the time since last fetch
        is less than the configured TTL.
        """
        if self._current_credential is None:
            return False
        elapsed = self._current_time - self._last_fetch_time
        return elapsed < self.ttl_seconds

    def get_credentials(self, rotation_outcome: RotationOutcome, new_credential: Credentials) -> Credentials:
        """Retrieve credentials, respecting cache TTL and rotation state.

        Behaviour:
        - If cache is valid (TTL not expired): return cached credential.
        - If cache is expired or empty:
            - If rotation succeeds: store and return the new credential.
            - If rotation fails: fall back to the previous cached credential.
              If no previous credential exists (first ever fetch fails), raise.

        Args:
            rotation_outcome: Whether the external rotation/fetch would succeed.
            new_credential: The credential that would be returned on success.

        Returns:
            The appropriate credential based on cache state and rotation outcome.

        Raises:
            RuntimeError: If no cached credential exists and rotation fails.
        """
        if self.is_cache_valid():
            # Cache hit — return cached credential without external call
            return self._current_credential  # type: ignore[return-value]

        # Cache miss — attempt fresh fetch
        if rotation_outcome == RotationOutcome.SUCCESS:
            # Rotation succeeded: update cache with new credential
            self._previous_credential = self._current_credential
            self._current_credential = new_credential
            self._last_fetch_time = self._current_time
            return self._current_credential
        else:
            # Rotation failed: fall back to previous credential
            if self._current_credential is not None:
                # Keep existing credential as fallback (don't update fetch time
                # so next call will also attempt refresh)
                return self._current_credential
            raise RuntimeError(
                "Rotation failed and no previous credential available for fallback"
            )


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

# TTL durations (in seconds) — from 60s to 30 days
ttl_strategy = st.integers(min_value=60, max_value=30 * 24 * 3600)

# Time since last fetch (in seconds) — 0 to 60 days
time_since_fetch_strategy = st.floats(min_value=0.0, max_value=60 * 24 * 3600, allow_nan=False, allow_infinity=False)

# Credential version numbers
version_strategy = st.integers(min_value=1, max_value=1000)

# Rotation outcomes
rotation_outcome_strategy = st.sampled_from([RotationOutcome.SUCCESS, RotationOutcome.FAILURE])


@st.composite
def credential_strategy(draw, version: Optional[int] = None):
    """Generate a valid Credentials instance."""
    v = version if version is not None else draw(version_strategy)
    username = f"db_user_v{v}"
    password = draw(st.text(
        alphabet=st.characters(whitelist_categories=("L", "N", "P")),
        min_size=8,
        max_size=64,
    ))
    return Credentials(username=username, password=password, version=v)


@st.composite
def credential_state(draw):
    """Generate a complete credential state for testing.

    Produces:
    - ttl_seconds: The cache TTL configuration
    - time_since_fetch: How long since the last successful fetch
    - rotation_outcome: Whether the next rotation attempt would succeed
    - cached_credential: The currently cached credential (if any)
    - new_credential: The credential that would come from a fresh fetch
    """
    ttl = draw(ttl_strategy)
    time_since_fetch = draw(time_since_fetch_strategy)
    outcome = draw(rotation_outcome_strategy)
    cached = draw(credential_strategy(version=1))
    new_cred = draw(credential_strategy(version=2))
    return {
        "ttl_seconds": ttl,
        "time_since_fetch": time_since_fetch,
        "rotation_outcome": outcome,
        "cached_credential": cached,
        "new_credential": new_cred,
    }


# ---------------------------------------------------------------------------
# Property 4: Credential caching honours TTL and rotation state
# ---------------------------------------------------------------------------


@pytest.mark.property
@settings(max_examples=200)
@given(state=credential_state())
def test_cached_credential_returned_before_ttl(state):
    """Cached credential is returned when TTL has not expired.

    *For any* credential state where time_since_fetch < ttl_seconds,
    the secrets client SHALL return the cached credential without attempting
    a fresh fetch, regardless of what the rotation outcome would be.

    **Validates: Requirements 21.3, 21.7**
    """
    ttl = state["ttl_seconds"]
    time_since_fetch = state["time_since_fetch"]
    cached = state["cached_credential"]
    new_cred = state["new_credential"]
    outcome = state["rotation_outcome"]

    # Only test the case where TTL has NOT expired
    assume(time_since_fetch < ttl)

    # Set up cache with an existing credential
    cache = CredentialCache(ttl_seconds=ttl)
    cache._current_credential = cached
    cache._last_fetch_time = 0.0
    cache.set_time(time_since_fetch)

    # Regardless of rotation outcome, cached credential should be returned
    result = cache.get_credentials(rotation_outcome=outcome, new_credential=new_cred)

    assert result is cached, (
        f"Expected cached credential (v{cached.version}) but got v{result.version}. "
        f"time_since_fetch={time_since_fetch}, ttl={ttl}"
    )


@pytest.mark.property
@settings(max_examples=200)
@given(state=credential_state())
def test_fresh_credential_fetched_after_ttl_expiry(state):
    """Fresh credential is fetched when TTL has expired and rotation succeeds.

    *For any* credential state where time_since_fetch >= ttl_seconds and
    rotation succeeds, the secrets client SHALL fetch and return the new
    credential (not the stale cached one).

    **Validates: Requirements 21.3, 21.7**
    """
    ttl = state["ttl_seconds"]
    time_since_fetch = state["time_since_fetch"]
    cached = state["cached_credential"]
    new_cred = state["new_credential"]

    # Only test the case where TTL HAS expired
    assume(time_since_fetch >= ttl)

    # Set up cache with an existing credential whose TTL has expired
    cache = CredentialCache(ttl_seconds=ttl)
    cache._current_credential = cached
    cache._last_fetch_time = 0.0
    cache.set_time(time_since_fetch)

    # On successful rotation, new credential should be returned
    result = cache.get_credentials(
        rotation_outcome=RotationOutcome.SUCCESS,
        new_credential=new_cred,
    )

    assert result is new_cred, (
        f"Expected new credential (v{new_cred.version}) but got v{result.version}. "
        f"time_since_fetch={time_since_fetch}, ttl={ttl}"
    )


@pytest.mark.property
@settings(max_examples=200)
@given(state=credential_state())
def test_fallback_to_previous_on_rotation_failure(state):
    """Previous credential is used as fallback when rotation fails.

    *For any* credential state where time_since_fetch >= ttl_seconds and
    rotation fails, the secrets client SHALL fall back to the previously
    cached credential rather than raising an error or returning nothing.

    **Validates: Requirements 21.3, 21.7**
    """
    ttl = state["ttl_seconds"]
    time_since_fetch = state["time_since_fetch"]
    cached = state["cached_credential"]
    new_cred = state["new_credential"]

    # Only test the case where TTL HAS expired
    assume(time_since_fetch >= ttl)

    # Set up cache with an existing credential whose TTL has expired
    cache = CredentialCache(ttl_seconds=ttl)
    cache._current_credential = cached
    cache._last_fetch_time = 0.0
    cache.set_time(time_since_fetch)

    # On failed rotation, the previous (cached) credential should be returned
    result = cache.get_credentials(
        rotation_outcome=RotationOutcome.FAILURE,
        new_credential=new_cred,
    )

    assert result is cached, (
        f"Expected fallback to cached credential (v{cached.version}) "
        f"but got v{result.version}. "
        f"time_since_fetch={time_since_fetch}, ttl={ttl}"
    )


@pytest.mark.property
@settings(max_examples=200)
@given(
    ttl=ttl_strategy,
    new_cred=credential_strategy(version=1),
)
def test_first_fetch_failure_raises_error(ttl, new_cred):
    """RuntimeError is raised when first-ever fetch fails with no fallback.

    *For any* credential cache with no previously cached credential,
    if the rotation/fetch fails, the secrets client SHALL raise a RuntimeError
    because there is no fallback credential available.

    **Validates: Requirements 21.3, 21.7**
    """
    # Empty cache — no previous credential to fall back to
    cache = CredentialCache(ttl_seconds=ttl)
    cache.set_time(ttl + 1.0)  # Ensure TTL would be expired if anything was cached

    with pytest.raises(RuntimeError, match="no previous credential"):
        cache.get_credentials(
            rotation_outcome=RotationOutcome.FAILURE,
            new_credential=new_cred,
        )


@pytest.mark.property
@settings(max_examples=200)
@given(state=credential_state())
def test_successful_fetch_updates_ttl_timer(state):
    """After a successful fetch, the TTL timer resets so the new credential is cached.

    *For any* credential state where TTL has expired and rotation succeeds,
    immediately after the fetch the cache SHALL be valid (is_cache_valid returns True)
    indicating the new credential is now cached with a fresh TTL window.

    **Validates: Requirements 21.3, 21.7**
    """
    ttl = state["ttl_seconds"]
    time_since_fetch = state["time_since_fetch"]
    cached = state["cached_credential"]
    new_cred = state["new_credential"]

    # Only test the case where TTL HAS expired
    assume(time_since_fetch >= ttl)

    cache = CredentialCache(ttl_seconds=ttl)
    cache._current_credential = cached
    cache._last_fetch_time = 0.0
    cache.set_time(time_since_fetch)

    # Perform the fetch
    cache.get_credentials(
        rotation_outcome=RotationOutcome.SUCCESS,
        new_credential=new_cred,
    )

    # After successful fetch, cache should be valid
    assert cache.is_cache_valid(), (
        f"Cache should be valid immediately after successful fetch. "
        f"current_time={cache._current_time}, last_fetch_time={cache._last_fetch_time}, ttl={ttl}"
    )
