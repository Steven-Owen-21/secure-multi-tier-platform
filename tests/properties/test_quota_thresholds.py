"""Property-based tests for quota alarm threshold calculation logic.

**Validates: Requirements 27.2, 27.6**

Uses Hypothesis to verify that the quota alarm threshold calculation
produces correct alarm thresholds (at 80% of limit) for all valid
quota limit values (positive integers from 1 to 100000).

The threshold formula mirrors Terraform:
    alarm_threshold = quota_limit * 0.80
"""

import pytest
from hypothesis import given, settings, strategies as st

from infrastructure.logic.quota_thresholds import calculate_quota_alarm_threshold


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

# Strategy for valid quota limit values: positive integers from 1 to 100000
quota_limit_strategy = st.integers(min_value=1, max_value=100000)


# ---------------------------------------------------------------------------
# Property 10: Quota alarm threshold is 80% of limit
# ---------------------------------------------------------------------------


@pytest.mark.property
@settings(max_examples=200)
@given(quota_limit=quota_limit_strategy)
def test_quota_alarm_threshold_is_80_percent_of_limit(quota_limit: int):
    """Property 10: Quota alarm threshold is 80% of limit.

    For any valid quota limit value (positive integer 1 to 100000),
    the threshold calculation SHALL produce exactly 80% of the quota limit.

    **Validates: Requirements 27.2, 27.6**
    """
    threshold = calculate_quota_alarm_threshold(quota_limit, alarm_threshold_percent=80)

    # Verify the threshold is exactly 80% of the quota limit.
    # Use integer multiplication to avoid floating-point imprecision:
    # threshold == quota_limit * 80 / 100
    expected = quota_limit * 80 / 100

    assert threshold == expected, (
        f"Threshold for quota_limit={quota_limit} should be exactly 80% "
        f"of the limit ({expected}), but got {threshold}"
    )
