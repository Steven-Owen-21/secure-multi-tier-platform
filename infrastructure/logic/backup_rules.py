"""Backup plan rule generation logic.

Mirrors the Terraform backup module (infrastructure/modules/backup/) that defines
AWS Backup plans with rules for Aurora, EBS, and S3 resources.

Default schedules per resource type:
    - Aurora: daily (cron 0 3 * * ? *) - 7 day retention
    - EBS: daily (cron 0 4 * * ? *) - 14 day retention
    - S3: weekly (cron 0 5 ? * SUN *) - 30 day retention

All resource types have cross-region copy enabled for disaster recovery.
"""

from dataclasses import dataclass
from typing import Literal, Optional

# Valid AWS cron expression pattern for backup schedules
# AWS cron: minute hour day-of-month month day-of-week year
# We support daily and weekly patterns used by backup plans
VALID_CRON_FIELDS = 6

# Default configurations per resource type
DEFAULT_CONFIGS: dict[str, dict] = {
    "aurora": {
        "schedule": "cron(0 3 * * ? *)",
        "retention_days": 7,
    },
    "ebs": {
        "schedule": "cron(0 4 * * ? *)",
        "retention_days": 14,
    },
    "s3": {
        "schedule": "cron(0 5 ? * SUN *)",
        "retention_days": 30,
    },
}

ResourceType = Literal["aurora", "ebs", "s3"]


@dataclass(frozen=True)
class BackupRule:
    """A single AWS Backup plan rule configuration."""

    resource_type: ResourceType
    schedule: str  # AWS cron expression
    retention_days: int
    copy_to_region: Optional[str]


def _validate_cron_expression(schedule: str) -> bool:
    """Validate that a schedule string is a valid AWS cron expression.

    AWS Backup cron format: cron(minute hour day-of-month month day-of-week year)
    Exactly 6 fields inside cron(...).

    Returns:
        True if the expression is valid, False otherwise.
    """
    if not schedule.startswith("cron(") or not schedule.endswith(")"):
        return False

    inner = schedule[5:-1].strip()
    fields = inner.split()

    if len(fields) != VALID_CRON_FIELDS:
        return False

    # Basic field validation
    # minute: 0-59 or *
    # hour: 0-23 or *
    # day-of-month: 1-31 or * or ?
    # month: 1-12 or * or JAN-DEC
    # day-of-week: 1-7 or SUN-SAT or * or ?
    # year: * or specific year
    minute, hour, dom, month, dow, year = fields

    # Exactly one of day-of-month or day-of-week must be '?'
    if not ((dom == "?" and dow != "?") or (dom != "?" and dow == "?")):
        return False

    return True


def generate_backup_rule(
    resource_type: ResourceType,
    retention_days: int | None = None,
    schedule: str | None = None,
    copy_to_region: str | None = "eu-west-1",
) -> BackupRule:
    """Generate an AWS Backup rule for the given resource type.

    This mirrors the Terraform aws_backup_plan resource logic in
    infrastructure/modules/backup/main.tf.

    Args:
        resource_type: The type of resource to back up (aurora, ebs, s3).
        retention_days: Retention period in days (1-365). Defaults per resource type.
        schedule: AWS cron expression for the backup schedule. Defaults per resource type.
        copy_to_region: Target region for cross-region copy. None to disable.

    Returns:
        A BackupRule with validated schedule, retention, and copy configuration.

    Raises:
        ValueError: If retention_days is out of range or schedule is invalid.
    """
    if resource_type not in DEFAULT_CONFIGS:
        raise ValueError(
            f"Invalid resource_type '{resource_type}'. "
            f"Must be one of: aurora, ebs, s3"
        )

    # Use defaults if not specified
    defaults = DEFAULT_CONFIGS[resource_type]
    effective_retention = retention_days if retention_days is not None else defaults["retention_days"]
    effective_schedule = schedule if schedule is not None else defaults["schedule"]

    # Validate retention days range
    if not (1 <= effective_retention <= 365):
        raise ValueError(
            f"retention_days must be between 1 and 365, got {effective_retention}"
        )

    # Validate cron expression
    if not _validate_cron_expression(effective_schedule):
        raise ValueError(
            f"Invalid cron expression: '{effective_schedule}'. "
            f"Expected format: cron(minute hour day-of-month month day-of-week year)"
        )

    return BackupRule(
        resource_type=resource_type,
        schedule=effective_schedule,
        retention_days=effective_retention,
        copy_to_region=copy_to_region,
    )
