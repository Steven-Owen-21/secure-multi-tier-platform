"""Security group rule generation logic.

Mirrors the Terraform security-groups module at
infrastructure/modules/security-groups/main.tf.

The platform defines five tiers with strict ingress rules following the
principle of least privilege (defence-in-depth):

    - alb:      inbound HTTPS (443) from 0.0.0.0/0 (internet)
    - app:      inbound on port 8000 from ALB security group only
    - db:       inbound PostgreSQL (5432) from App security group only
    - cache:    inbound Redis (6379) from App security group only
    - endpoint: inbound HTTPS (443) from App security group only

No tier may reference an unpermitted source. Data tiers (db, cache,
endpoint) must never accept traffic directly from the internet.
"""

from dataclasses import dataclass
from typing import Dict, FrozenSet, List


# All valid tier names in the platform
ALL_TIERS: FrozenSet[str] = frozenset({"alb", "app", "db", "cache", "endpoint"})

# Permitted ingress source per tier.
# "internet" represents 0.0.0.0/0 CIDR (not a security group reference).
PERMITTED_SOURCES: Dict[str, str] = {
    "alb": "internet",
    "app": "alb_sg",
    "db": "app_sg",
    "cache": "app_sg",
    "endpoint": "app_sg",
}

# Expected ingress port per tier.
TIER_PORTS: Dict[str, int] = {
    "alb": 443,
    "app": 8000,
    "db": 5432,
    "cache": 6379,
    "endpoint": 443,
}

# Tiers that must never accept traffic directly from the internet
DATA_TIERS: FrozenSet[str] = frozenset({"db", "cache", "endpoint"})


@dataclass(frozen=True)
class IngressRule:
    """Represents a single ingress rule for a security group.

    Attributes:
        tier: The security group tier this rule belongs to.
        port: The TCP port number allowed for inbound traffic.
        source: The permitted source — either a security group reference
                (e.g. "alb_sg", "app_sg") or "internet" for 0.0.0.0/0.
    """

    tier: str
    port: int
    source: str


def generate_security_group_rules(tiers: FrozenSet[str]) -> List[IngressRule]:
    """Generate ingress rules for the given set of tiers.

    Given a set of tier names, produces the ingress rules that should be
    applied to each tier's security group. This mirrors the logic in the
    Terraform security-groups module.

    Args:
        tiers: A frozenset of tier names to generate rules for.
               Valid values: "alb", "app", "db", "cache", "endpoint".

    Returns:
        List of IngressRule instances describing permitted ingress,
        sorted alphabetically by tier name.

    Raises:
        ValueError: If any tier name is not recognised.
    """
    invalid_tiers = tiers - ALL_TIERS
    if invalid_tiers:
        raise ValueError(f"Unrecognised tier(s): {invalid_tiers}")

    rules: List[IngressRule] = []

    for tier in sorted(tiers):
        source = PERMITTED_SOURCES[tier]
        port = TIER_PORTS[tier]
        rules.append(IngressRule(tier=tier, port=port, source=source))

    return rules
