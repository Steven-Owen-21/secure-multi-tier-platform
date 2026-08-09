"""Property-based tests for backup plan rule generation logic.

**Validates: Requirements 26.2, 26.7**

Uses Hypothesis to verify that backup rule generation produces valid backup
rules with correct lifecycle configurations for all valid combinations of
resource types (aurora, ebs, s3) and retention periods (1-365 days).

Property 9: Backup plan rules have valid lifecycles and schedules.
"""

import pytest
from hypothesis import given, settings, strategies as st

from infrastructure.logic.backup_rules import (
    BackupRule,
    DEFAULT_CONFIGS,
    generate_backup_rule,
)


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

# Valid resource types for AWS Backup rules
valid_resource_types = st.sampled_from(["aurora", "ebs", "s3"])

# Valid retention periods (1-365 days per requirement 26.7)
valid_retention_days = st.integers(min_value=1, max_value=365)

# Valid AWS region names for cross-region copy
valid_regions = st.sampled_from([
    "eu-west-1",
    "eu-west-2",
    "us-east-1",
    "us-west-2",
    "ap-southeast-1",
])

# Valid AWS cron expressions for backup schedules (daily and weekly patterns)
valid_cron_schedules = st.sampled_from([
    "cron(0 3 * * ? *)",   # Daily at 03:00 UTC
    "cron(0 4 * * ? *)",   # Daily at 04:00 UTC
    "cron(0 5 ? * SUN *)", # Weekly on Sunday at 05:00 UTC
    "cron(0 2 * * ? *)",   # Daily at 02:00 UTC
    "cron(30 1 * * ? *)",  # Daily at 01:30 UTC
    "cron(0 6 ? * MON *)", # Weekly on Monday at 06:00 UTC
])


# ---------------------------------------------------------------------------
# Property 9: Backup plan rules have valid lifecycles and schedules
# ---------------------------------------------------------------------------


@pytest.mark.property
@settings(max_examples=100)
@given(
    resource_type=valid_resource_types,
    retention_days=valid_retention_days,
    schedule=valid_cron_schedules,
    copy_region=valid_regions,
)
def test_backup_rule_valid_lifecycle_and_schedule(
    resource_type, retention_days, schedule, copy_region
):
    """Property 9: Backup plan rules have valid lifecycles and schedules.

    For any valid resource type (aurora, ebs, s3) and retention period (1-365
    days), the backup rule generation SHALL produce a valid cron schedule,
    retention within range, and correct cross-region copy configuration.

    **Validates: Requirements 26.2, 26.7**
    """
    rule = generate_backup_rule(
        resource_type=resource_type,
        retention_days=retention_days,
        schedule=schedule,
        copy_to_region=copy_region,
    )

    # Verify the result is a valid BackupRule
    assert isinstance(rule, BackupRule)

    # Verify resource type is preserved
    assert rule.resource_type == resource_type

    # Verify retention is within valid range (1-365 days)
    assert 1 <= rule.retention_days <= 365, (
        f"Retention days {rule.retention_days} must be between 1 and 365"
    )
    assert rule.retention_days == retention_days

    # Verify schedule is a valid cron expression
    assert rule.schedule.startswith("cron("), (
        f"Schedule must start with 'cron(', got: {rule.schedule}"
    )
    assert rule.schedule.endswith(")"), (
        f"Schedule must end with ')', got: {rule.schedule}"
    )
    # Verify cron has exactly 6 fields
    inner = rule.schedule[5:-1].strip()
    fields = inner.split()
    assert len(fields) == 6, (
        f"Cron expression must have 6 fields, got {len(fields)}: {rule.schedule}"
    )

    # Verify cross-region copy config is set
    assert rule.copy_to_region == copy_region


@pytest.mark.property
@settings(max_examples=50)
@given(resource_type=valid_resource_types)
def test_backup_rule_defaults_produce_valid_rules(resource_type):
    """Property 9: Default backup rules per resource type are valid.

    When no explicit retention or schedule is provided, each resource type
    uses its documented default configuration and still produces a valid rule.

    **Validates: Requirements 26.2, 26.7**
    """
    rule = generate_backup_rule(resource_type=resource_type)

    # Verify defaults are applied correctly
    defaults = DEFAULT_CONFIGS[resource_type]
    assert rule.schedule == defaults["schedule"]
    assert rule.retention_days == defaults["retention_days"]

    # Verify retention within valid range
    assert 1 <= rule.retention_days <= 365

    # Verify cross-region copy is enabled by default
    assert rule.copy_to_region is not None


@pytest.mark.property
@settings(max_examples=50)
@given(
    resource_type=valid_resource_types,
    retention_days=valid_retention_days,
)
def test_backup_rule_cross_region_copy_config(resource_type, retention_days):
    """Property 9: Cross-region copy is correctly configured.

    All resource types should have cross-region copy enabled by default,
    and the copy region should match the requested configuration.

    **Validates: Requirements 26.2, 26.7**
    """
    # With explicit copy region
    rule_with_copy = generate_backup_rule(
        resource_type=resource_type,
        retention_days=retention_days,
        copy_to_region="eu-west-1",
    )
    assert rule_with_copy.copy_to_region == "eu-west-1"

    # With copy disabled (None)
    rule_no_copy = generate_backup_rule(
        resource_type=resource_type,
        retention_days=retention_days,
        copy_to_region=None,
    )
    assert rule_no_copy.copy_to_region is None


@pytest.mark.property
@settings(max_examples=50)
@given(
    resource_type=valid_resource_types,
    invalid_retention=st.one_of(
        st.integers(max_value=0),
        st.integers(min_value=366),
    ),
)
def test_backup_rule_rejects_invalid_retention(resource_type, invalid_retention):
    """Property 9: Backup rule rejects retention outside valid range.

    Retention days outside 1-365 must raise a ValueError.

    **Validates: Requirements 26.2, 26.7**
    """
    with pytest.raises(ValueError):
        generate_backup_rule(
            resource_type=resource_type,
            retention_days=invalid_retention,
        )
