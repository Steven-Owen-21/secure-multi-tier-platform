"""Property-based tests for security group rule generation logic.

**Validates: Requirements 2.7**

Uses Hypothesis to verify that the security group rule generation logic
produces rules referencing only permitted source groups for all valid tier
combinations.
"""

import pytest
from hypothesis import given, settings, strategies as st

from infrastructure.logic.security_group_rules import (
    ALL_TIERS,
    DATA_TIERS,
    PERMITTED_SOURCES,
    TIER_PORTS,
    IngressRule,
    generate_security_group_rules,
)


# ---------------------------------------------------------------------------
# Hypothesis Strategies
# ---------------------------------------------------------------------------


@st.composite
def valid_tier_combinations(draw: st.DrawFn) -> frozenset:
    """Generate a non-empty subset of valid tier names.

    Produces combinations like {"alb"}, {"app", "db"}, {"alb", "app", "db",
    "cache", "endpoint"}, etc.
    """
    tiers = draw(
        st.frozensets(
            st.sampled_from(sorted(ALL_TIERS)),
            min_size=1,
            max_size=len(ALL_TIERS),
        )
    )
    return tiers


# ---------------------------------------------------------------------------
# Property Tests
# ---------------------------------------------------------------------------


@pytest.mark.property
@settings(max_examples=50)
@given(tiers=valid_tier_combinations())
def test_rules_reference_only_permitted_sources(tiers: frozenset):
    """Property: generated rules only reference permitted sources for each tier.

    For any valid combination of tier names, every generated ingress rule
    must use the exact permitted source for that tier and no other.

    **Validates: Requirements 2.7**
    """
    rules = generate_security_group_rules(tiers)

    for rule in rules:
        expected_source = PERMITTED_SOURCES[rule.tier]
        assert rule.source == expected_source, (
            f"Tier '{rule.tier}' has source '{rule.source}', "
            f"but only '{expected_source}' is permitted"
        )


@pytest.mark.property
@settings(max_examples=50)
@given(tiers=valid_tier_combinations())
def test_rules_use_correct_ports(tiers: frozenset):
    """Property: generated rules use the correct port for each tier.

    Each tier must expose only its designated port:
    - alb: 443, app: 8000, db: 5432, cache: 6379, endpoint: 443

    **Validates: Requirements 2.7**
    """
    rules = generate_security_group_rules(tiers)

    for rule in rules:
        expected_port = TIER_PORTS[rule.tier]
        assert rule.port == expected_port, (
            f"Tier '{rule.tier}' has port {rule.port}, "
            f"but expected port {expected_port}"
        )


@pytest.mark.property
@settings(max_examples=50)
@given(tiers=valid_tier_combinations())
def test_no_tier_references_itself_as_source(tiers: frozenset):
    """Property: no tier's ingress rule references its own security group.

    A security group must never allow ingress from itself unless explicitly
    designed to do so (none in this platform do).

    **Validates: Requirements 2.7**
    """
    rules = generate_security_group_rules(tiers)

    for rule in rules:
        # The source naming convention is "{tier}_sg" for security group refs
        self_reference = f"{rule.tier}_sg"
        assert rule.source != self_reference, (
            f"Tier '{rule.tier}' references itself as ingress source"
        )


@pytest.mark.property
@settings(max_examples=50)
@given(tiers=valid_tier_combinations())
def test_exactly_one_rule_per_tier(tiers: frozenset):
    """Property: exactly one ingress rule is generated per requested tier.

    The module produces precisely one ingress rule per tier — no more, no less.

    **Validates: Requirements 2.7**
    """
    rules = generate_security_group_rules(tiers)

    assert len(rules) == len(tiers), (
        f"Expected {len(tiers)} rules for tiers {tiers}, got {len(rules)}"
    )

    rule_tiers = frozenset(rule.tier for rule in rules)
    assert rule_tiers == tiers, (
        f"Rules cover tiers {rule_tiers}, but requested tiers {tiers}"
    )


@pytest.mark.property
@settings(max_examples=50)
@given(tiers=valid_tier_combinations())
def test_data_tier_sources_are_never_internet(tiers: frozenset):
    """Property: data-tier groups (db, cache, endpoint) never allow internet ingress.

    Only the ALB tier is permitted to accept traffic from the internet.
    Database, cache, and endpoint tiers must always reference a security
    group, never a CIDR/internet source.

    **Validates: Requirements 2.7**
    """
    rules = generate_security_group_rules(tiers)

    for rule in rules:
        if rule.tier in DATA_TIERS:
            assert rule.source != "internet", (
                f"Data tier '{rule.tier}' has internet as source, "
                f"which violates least-privilege network access"
            )
