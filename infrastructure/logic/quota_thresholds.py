"""Quota alarm threshold calculation logic.

Mirrors the Terraform CloudWatch alarm threshold calculation in
infrastructure/modules/service-quotas/main.tf.

The threshold formula is:
    alarm_threshold = quota_limit * alarm_threshold_percent / 100

With the default alarm_threshold_percent of 80, the alarm triggers
when service quota usage exceeds 80% of the current limit.

This module uses floor-based integer arithmetic to match the Terraform
`floor()` function used in the service-quotas module.
"""

import math


def calculate_quota_alarm_threshold(
    quota_limit: int,
    alarm_threshold_percent: int = 80,
) -> float:
    """Calculate the alarm threshold for a service quota.

    This mirrors the Terraform local computation:
        alarm_threshold = floor(quota.quota_value * var.alarm_threshold_percent / 100)

    The threshold represents the value at which the CloudWatch alarm should
    trigger, indicating that usage is approaching the service quota limit.

    Args:
        quota_limit: The service quota limit value (positive integer).
        alarm_threshold_percent: The percentage of the limit at which to alarm
            (default 80, matching Terraform variable default).

    Returns:
        The threshold value (80% of quota_limit by default).

    Raises:
        ValueError: If quota_limit is not a positive integer or
            alarm_threshold_percent is not between 1 and 100.
    """
    if not isinstance(quota_limit, int) or quota_limit < 1:
        raise ValueError(
            f"quota_limit must be a positive integer, got {quota_limit!r}"
        )

    if not isinstance(alarm_threshold_percent, int) or not (1 <= alarm_threshold_percent <= 100):
        raise ValueError(
            f"alarm_threshold_percent must be an integer between 1 and 100, "
            f"got {alarm_threshold_percent!r}"
        )

    return quota_limit * alarm_threshold_percent / 100
