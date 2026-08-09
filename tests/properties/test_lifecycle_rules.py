"""Property-based tests for S3 lifecycle rule generation logic.

**Validates: Requirements 23.1, 23.7**

Uses Hypothesis to verify that lifecycle rule generation produces valid S3
lifecycle configurations maintaining strict ordering of tier transitions:
IA_days < Glacier_days < Expiration_days, all positive integers.

The lifecycle transition timeline is:
    Standard → 30 days → Infrequent Access → 90 days → Glacier → 365 days → Expire
"""

import pytest
from hypothesis import given, settings, strategies as st, assume

from infrastructure.logic.lifecycle_rules import (
    LifecycleRule,
    LifecycleTransition,
    generate_lifecycle_rule,
)


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

# Generate strictly ordered positive integer triples for IA, Glacier, Expiration days
@st.composite
def valid_lifecycle_days(draw):
    """Generate valid IA, Glacier, and Expiration day values that are strictly ordered.

    Constraints:
    - All values are positive integers (>= 1)
    - IA_days < Glacier_days < Expiration_days
    """
    ia_days = draw(st.integers(min_value=1, max_value=3650))
    glacier_days = draw(st.integers(min_value=ia_days + 1, max_value=3651))
    expiration_days = draw(st.integers(min_value=glacier_days + 1, max_value=3652))
    return ia_days, glacier_days, expiration_days


# Valid S3 bucket names (simplified for testing)
valid_bucket_names = st.from_regex(r"[a-z][a-z0-9.-]{2,62}", fullmatch=True).filter(
    lambda s: ".." not in s and not s.endswith("-") and not s.endswith(".")
)


# ---------------------------------------------------------------------------
# Property 6: Lifecycle rule transitions are strictly ordered
# ---------------------------------------------------------------------------


@pytest.mark.property
@settings(max_examples=100)
@given(
    days=valid_lifecycle_days(),
    bucket_name=valid_bucket_names,
)
def test_lifecycle_transitions_strictly_ordered(days, bucket_name):
    """Property 6: Lifecycle rule transitions are strictly ordered.

    For any valid combination of IA transition days, Glacier transition days,
    and expiration days, the generated lifecycle rule SHALL maintain strict
    ordering: IA_days < Glacier_days < Expiration_days, all positive integers.

    **Validates: Requirements 23.1, 23.7**
    """
    ia_days, glacier_days, expiration_days = days

    rule = generate_lifecycle_rule(
        bucket_name=bucket_name,
        ia_transition_days=ia_days,
        glacier_transition_days=glacier_days,
        expiration_days=expiration_days,
    )

    # Verify the rule is a valid LifecycleRule
    assert isinstance(rule, LifecycleRule)

    # Verify transitions are present
    assert len(rule.transitions) == 2

    # Extract transition days
    ia_transition = rule.transitions[0]
    glacier_transition = rule.transitions[1]

    # Verify storage classes
    assert ia_transition.storage_class == "STANDARD_IA"
    assert glacier_transition.storage_class == "GLACIER"

    # Verify strict ordering: IA < Glacier < Expiration
    assert ia_transition.days < glacier_transition.days, (
        f"IA transition ({ia_transition.days}) must be strictly less than "
        f"Glacier transition ({glacier_transition.days})"
    )
    assert glacier_transition.days < rule.expiration_days, (
        f"Glacier transition ({glacier_transition.days}) must be strictly less than "
        f"expiration ({rule.expiration_days})"
    )

    # Verify all values are positive integers
    assert ia_transition.days >= 1, f"IA days must be positive, got {ia_transition.days}"
    assert glacier_transition.days >= 1, (
        f"Glacier days must be positive, got {glacier_transition.days}"
    )
    assert rule.expiration_days >= 1, (
        f"Expiration days must be positive, got {rule.expiration_days}"
    )

    # Verify bucket name is preserved
    assert rule.bucket_name == bucket_name


@pytest.mark.property
@settings(max_examples=50)
@given(
    days=valid_lifecycle_days(),
    bucket_name=valid_bucket_names,
)
def test_lifecycle_rule_values_match_inputs(days, bucket_name):
    """Property: Generated lifecycle rule preserves the exact input day values.

    **Validates: Requirements 23.1, 23.7**
    """
    ia_days, glacier_days, expiration_days = days

    rule = generate_lifecycle_rule(
        bucket_name=bucket_name,
        ia_transition_days=ia_days,
        glacier_transition_days=glacier_days,
        expiration_days=expiration_days,
    )

    # Verify the exact day values are preserved
    assert rule.transitions[0].days == ia_days
    assert rule.transitions[1].days == glacier_days
    assert rule.expiration_days == expiration_days


@pytest.mark.property
@settings(max_examples=50)
@given(
    ia_days=st.integers(min_value=1, max_value=3650),
    glacier_days=st.integers(min_value=1, max_value=3650),
    expiration_days=st.integers(min_value=1, max_value=3650),
)
def test_lifecycle_rejects_non_strictly_ordered_days(ia_days, glacier_days, expiration_days):
    """Property: Lifecycle rule generation rejects inputs that violate strict ordering.

    If the ordering invariant IA < Glacier < Expiration is violated, the
    function must raise a ValueError.

    **Validates: Requirements 23.1, 23.7**
    """
    # Only test cases that violate ordering
    assume(not (ia_days < glacier_days < expiration_days))

    with pytest.raises(ValueError):
        generate_lifecycle_rule(
            bucket_name="test-bucket",
            ia_transition_days=ia_days,
            glacier_transition_days=glacier_days,
            expiration_days=expiration_days,
        )
