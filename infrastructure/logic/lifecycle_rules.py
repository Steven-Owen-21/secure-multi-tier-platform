"""S3 lifecycle rule generation logic.

Mirrors the Terraform S3 lifecycle module (infrastructure/modules/s3-lifecycle/)
that defines lifecycle policies for transitioning objects between storage tiers.

The lifecycle transition timeline is:
    Standard → IA_days → Infrequent Access → Glacier_days → Glacier → Expiration_days → Expire

Transitions must be strictly ordered: IA_days < Glacier_days < Expiration_days,
and all values must be positive integers.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class LifecycleTransition:
    """A single S3 lifecycle transition rule."""

    storage_class: str
    days: int


@dataclass(frozen=True)
class LifecycleRule:
    """A complete S3 lifecycle rule configuration for a bucket."""

    bucket_name: str
    transitions: list[LifecycleTransition]
    expiration_days: int | None


def generate_lifecycle_rule(
    bucket_name: str,
    ia_transition_days: int,
    glacier_transition_days: int,
    expiration_days: int,
) -> LifecycleRule:
    """Generate an S3 lifecycle rule configuration with tier transitions.

    This mirrors the Terraform aws_s3_bucket_lifecycle_configuration resource
    logic in infrastructure/modules/s3-lifecycle/main.tf.

    The function enforces the strict ordering invariant:
        ia_transition_days < glacier_transition_days < expiration_days

    All day values must be positive integers.

    Args:
        bucket_name: Name of the S3 bucket.
        ia_transition_days: Days before transitioning to Infrequent Access.
        glacier_transition_days: Days before transitioning to Glacier.
        expiration_days: Days before objects expire (are deleted).

    Returns:
        A LifecycleRule with ordered transitions and expiration.

    Raises:
        ValueError: If days are not positive or ordering is violated.
    """
    # Validate all values are positive integers
    if ia_transition_days < 1:
        raise ValueError(
            f"ia_transition_days must be a positive integer, got {ia_transition_days}"
        )
    if glacier_transition_days < 1:
        raise ValueError(
            f"glacier_transition_days must be a positive integer, got {glacier_transition_days}"
        )
    if expiration_days < 1:
        raise ValueError(
            f"expiration_days must be a positive integer, got {expiration_days}"
        )

    # Validate strict ordering
    if not (ia_transition_days < glacier_transition_days < expiration_days):
        raise ValueError(
            f"Lifecycle transitions must be strictly ordered: "
            f"IA ({ia_transition_days}) < Glacier ({glacier_transition_days}) "
            f"< Expiration ({expiration_days})"
        )

    transitions = [
        LifecycleTransition(storage_class="STANDARD_IA", days=ia_transition_days),
        LifecycleTransition(storage_class="GLACIER", days=glacier_transition_days),
    ]

    return LifecycleRule(
        bucket_name=bucket_name,
        transitions=transitions,
        expiration_days=expiration_days,
    )
