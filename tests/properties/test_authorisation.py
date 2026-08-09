"""Property-based tests for authorisation logic (role-to-permission mapping).

**Validates: Requirements 5.9**

Uses Hypothesis to generate all valid role (admin, manager, viewer) and
resource/action combinations. Verifies the correct permit/deny decision
for each combination. The check is case-insensitive on action.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings, strategies as st

from app.services.auth_service import (
    AuthService,
    ROLE_PERMISSIONS,
    TokenClaims,
)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# All defined roles
roles_strategy = st.sampled_from(["admin", "manager", "viewer"])

# Actions that are defined in the permission model
valid_actions = st.sampled_from(["read", "write", "delete"])

# Resource names — authorisation is resource-agnostic in the current model,
# but we generate diverse resource names to confirm this property.
resource_strategy = st.sampled_from(
    ["products", "orders", "users", "reports", "settings", "inventory"]
)

# Case variations of actions to verify case-insensitivity
case_varied_actions = valid_actions.flatmap(
    lambda action: st.sampled_from(
        [action.lower(), action.upper(), action.capitalize(), action.swapcase()]
    )
)

# Groups containing one or more valid roles (user may belong to multiple groups)
groups_strategy = st.lists(
    roles_strategy,
    min_size=1,
    max_size=3,
    unique=True,
)

# Actions that no role has permission for
undefined_actions = st.sampled_from(["execute", "admin", "purge", "escalate", "transfer"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_claims(groups: list[str]) -> TokenClaims:
    """Create a minimal TokenClaims with the given groups."""
    return TokenClaims(
        sub="test-user",
        email="test@example.com",
        groups=groups,
    )


def _expected_permitted(groups: list[str], action: str) -> bool:
    """Compute the expected permission decision from the ROLE_PERMISSIONS model.

    A user is permitted if ANY of their groups/roles allows the action.
    """
    action_lower = action.lower()
    for group in groups:
        role = group.lower()
        if action_lower in ROLE_PERMISSIONS.get(role, set()):
            return True
    return False


# ---------------------------------------------------------------------------
# Property: Single role permits/denies correctly
# ---------------------------------------------------------------------------


@pytest.mark.property
@settings(max_examples=200)
@given(
    role=roles_strategy,
    resource=resource_strategy,
    action=valid_actions,
)
def test_single_role_permission_decision(role: str, resource: str, action: str):
    """Property: for a single role and action, check_permission returns the
    correct permit/deny decision based on ROLE_PERMISSIONS.

    - admin: read ✓, write ✓, delete ✓
    - manager: read ✓, write ✓, delete ✗
    - viewer: read ✓, write ✗, delete ✗

    **Validates: Requirements 5.9**
    """
    claims = _make_claims([role])
    service = AuthService(
        jwks_url="http://unused",
        client_id="unused",
        user_pool_id="unused",
    )

    result = service.check_permission(claims, resource, action)
    expected = action in ROLE_PERMISSIONS[role]

    assert result == expected, (
        f"Role '{role}' action '{action}': expected {expected}, got {result}"
    )


# ---------------------------------------------------------------------------
# Property: Case-insensitive action matching
# ---------------------------------------------------------------------------


@pytest.mark.property
@settings(max_examples=200)
@given(
    role=roles_strategy,
    resource=resource_strategy,
    action=case_varied_actions,
)
def test_action_case_insensitive(role: str, resource: str, action: str):
    """Property: check_permission is case-insensitive on the action parameter.

    Any casing of a valid action (READ, Read, rEaD, etc.) produces the same
    decision as the lowercase version.

    **Validates: Requirements 5.9**
    """
    claims = _make_claims([role])
    service = AuthService(
        jwks_url="http://unused",
        client_id="unused",
        user_pool_id="unused",
    )

    result = service.check_permission(claims, resource, action)
    expected = action.lower() in ROLE_PERMISSIONS[role]

    assert result == expected, (
        f"Role '{role}' action '{action}' (case variant): expected {expected}, got {result}"
    )


# ---------------------------------------------------------------------------
# Property: Multi-role users get the union of permissions
# ---------------------------------------------------------------------------


@pytest.mark.property
@settings(max_examples=200)
@given(
    groups=groups_strategy,
    resource=resource_strategy,
    action=valid_actions,
)
def test_multi_role_permission_is_union(groups: list[str], resource: str, action: str):
    """Property: a user with multiple roles is permitted if ANY role allows
    the action (effective permissions are the union of all role permissions).

    **Validates: Requirements 5.9**
    """
    claims = _make_claims(groups)
    service = AuthService(
        jwks_url="http://unused",
        client_id="unused",
        user_pool_id="unused",
    )

    result = service.check_permission(claims, resource, action)
    expected = _expected_permitted(groups, action)

    assert result == expected, (
        f"Groups {groups} action '{action}': expected {expected}, got {result}"
    )


# ---------------------------------------------------------------------------
# Property: Unknown actions are always denied
# ---------------------------------------------------------------------------


@pytest.mark.property
@settings(max_examples=100)
@given(
    groups=groups_strategy,
    resource=resource_strategy,
    action=undefined_actions,
)
def test_undefined_actions_always_denied(groups: list[str], resource: str, action: str):
    """Property: actions not defined in any role's permission set are always denied,
    regardless of the user's roles.

    **Validates: Requirements 5.9**
    """
    claims = _make_claims(groups)
    service = AuthService(
        jwks_url="http://unused",
        client_id="unused",
        user_pool_id="unused",
    )

    result = service.check_permission(claims, resource, action)

    assert result is False, (
        f"Groups {groups} undefined action '{action}': should be denied but was permitted"
    )


# ---------------------------------------------------------------------------
# Property: No groups means always denied
# ---------------------------------------------------------------------------


@pytest.mark.property
@settings(max_examples=100)
@given(
    resource=resource_strategy,
    action=valid_actions,
)
def test_no_groups_always_denied(resource: str, action: str):
    """Property: a user with no groups/roles is denied all actions.

    **Validates: Requirements 5.9**
    """
    claims = _make_claims([])
    service = AuthService(
        jwks_url="http://unused",
        client_id="unused",
        user_pool_id="unused",
    )

    result = service.check_permission(claims, resource, action)

    assert result is False, (
        f"No groups, action '{action}': should be denied but was permitted"
    )


# ---------------------------------------------------------------------------
# Property: Resource name does not affect permission decision
# ---------------------------------------------------------------------------


@pytest.mark.property
@settings(max_examples=100)
@given(
    role=roles_strategy,
    action=valid_actions,
    resource_a=resource_strategy,
    resource_b=resource_strategy,
)
def test_resource_independent(role: str, action: str, resource_a: str, resource_b: str):
    """Property: the permission decision is independent of the resource name.

    The current model uses a flat role→actions mapping without per-resource
    scoping, so the same role+action must yield the same result regardless
    of which resource is being accessed.

    **Validates: Requirements 5.9**
    """
    claims = _make_claims([role])
    service = AuthService(
        jwks_url="http://unused",
        client_id="unused",
        user_pool_id="unused",
    )

    result_a = service.check_permission(claims, resource_a, action)
    result_b = service.check_permission(claims, resource_b, action)

    assert result_a == result_b, (
        f"Role '{role}' action '{action}': different result for "
        f"resource '{resource_a}' ({result_a}) vs '{resource_b}' ({result_b})"
    )
