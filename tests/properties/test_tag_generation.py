"""Property-based tests for tag generation logic.

**Validates: Requirements 25.1, 25.6, 25.7**

Uses Hypothesis to verify that the tag generation logic always produces all
required mandatory tags with non-empty valid values for all valid input
combinations of environment, component, and owner values.
"""

import pytest
from hypothesis import given, settings, strategies as st

# ---------------------------------------------------------------------------
# Tag generation function — mirrors infrastructure/modules/tagging/main.tf
# ---------------------------------------------------------------------------

MANDATORY_TAGS = frozenset(
    ["Project", "Environment", "Owner", "CostCentre", "ManagedBy", "Component"]
)


def generate_tags(
    environment: str,
    component: str,
    owner: str,
    cost_centre: str = "engineering",
) -> dict[str, str]:
    """Generate the complete mandatory tag set for a platform resource.

    This mirrors the Terraform tagging module locals.tags map defined in
    infrastructure/modules/tagging/main.tf.

    Args:
        environment: Deployment environment — must be "local" or "demo".
        component: Component name (non-empty, max 64 characters).
        owner: Resource owner (non-empty, max 128 characters).
        cost_centre: Cost centre for billing (default "engineering").

    Returns:
        A dict with exactly 6 keys matching the mandatory tag set.
    """
    return {
        "Project": "secure-multi-tier-platform",
        "Environment": environment,
        "Owner": owner,
        "CostCentre": cost_centre,
        "ManagedBy": "terraform",
        "Component": component,
    }


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

# Valid environments as defined in the tag policy
valid_environments = st.sampled_from(["local", "demo"])

# Valid component names: non-empty printable text, max 64 chars
# Using characters suitable for AWS tag values (printable ASCII, no leading/trailing whitespace)
valid_components = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "S"),
        blacklist_characters="\x00",
    ),
    min_size=1,
    max_size=64,
).filter(lambda s: s.strip() == s and len(s.strip()) > 0)

# Valid owners: non-empty text, max 128 chars
valid_owners = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "S"),
        blacklist_characters="\x00",
    ),
    min_size=1,
    max_size=128,
).filter(lambda s: s.strip() == s and len(s.strip()) > 0)


# ---------------------------------------------------------------------------
# Property 8: Tag generation always produces complete mandatory tag set
# ---------------------------------------------------------------------------


@pytest.mark.property
@settings(max_examples=50)
@given(
    environment=valid_environments,
    component=valid_components,
    owner=valid_owners,
)
def test_tag_generation_produces_all_mandatory_tags(environment, component, owner):
    """Property 8: Tag generation always produces complete mandatory tag set.

    For any valid combination of environment, component, and owner inputs,
    the tag generation logic SHALL produce a dict containing ALL six mandatory
    tags (Project, Environment, Owner, CostCentre, ManagedBy, Component)
    with non-empty valid values.

    **Validates: Requirements 25.1, 25.6, 25.7**
    """
    tags = generate_tags(environment=environment, component=component, owner=owner)

    # 1. Verify ALL 6 mandatory keys are present
    assert set(tags.keys()) == MANDATORY_TAGS, (
        f"Expected exactly {MANDATORY_TAGS}, got {set(tags.keys())}"
    )

    # 2. Verify no values are empty strings
    for key, value in tags.items():
        assert isinstance(value, str), f"Tag '{key}' must be a string, got {type(value)}"
        assert len(value) > 0, f"Tag '{key}' must not be empty"

    # 3. Verify Project is always the fixed platform name
    assert tags["Project"] == "secure-multi-tier-platform", (
        f"Project tag must be 'secure-multi-tier-platform', got '{tags['Project']}'"
    )

    # 4. Verify ManagedBy is always "terraform"
    assert tags["ManagedBy"] == "terraform", (
        f"ManagedBy tag must be 'terraform', got '{tags['ManagedBy']}'"
    )

    # 5. Verify Environment matches the input
    assert tags["Environment"] == environment, (
        f"Environment tag must match input '{environment}', got '{tags['Environment']}'"
    )

    # 6. Verify Component matches the input
    assert tags["Component"] == component, (
        f"Component tag must match input '{component}', got '{tags['Component']}'"
    )

    # 7. Verify Owner matches the input
    assert tags["Owner"] == owner, (
        f"Owner tag must match input '{owner}', got '{tags['Owner']}'"
    )
