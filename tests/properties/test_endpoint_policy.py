"""Property-based tests for VPC endpoint policy generation logic.

**Validates: Requirements 11.7**

Uses Hypothesis to verify that the VPC endpoint policy generation produces
valid IAM policy documents for all valid bucket name and action combinations.

The S3 gateway endpoint policy restricts access to platform-specific buckets
only, mirroring the logic in infrastructure/modules/vpc-endpoints/main.tf
(the s3_endpoint_policy local).
"""

import json
import re
from typing import Any, Dict, List, Optional

import pytest
from hypothesis import given, settings, assume, strategies as st


# ---------------------------------------------------------------------------
# S3 endpoint policy generation logic mirroring the Terraform module.
#
# When platform bucket ARNs are provided, the endpoint policy:
#   1. Allows specific S3 actions on those bucket ARNs and their objects
#   2. Denies all S3 actions on any resource NOT in the platform bucket list
#
# When no bucket ARNs are provided, the policy is None (open/unrestricted).
# ---------------------------------------------------------------------------

# The set of S3 actions allowed through the endpoint (from Terraform module)
ALLOWED_S3_ACTIONS = [
    "s3:GetObject",
    "s3:PutObject",
    "s3:ListBucket",
    "s3:GetBucketLocation",
    "s3:DeleteObject",
    "s3:ListMultipartUploadParts",
    "s3:AbortMultipartUpload",
]


def generate_s3_endpoint_policy(
    platform_bucket_arns: List[str],
) -> Optional[Dict[str, Any]]:
    """Generate the S3 VPC endpoint policy for the given platform bucket ARNs.

    Mirrors the Terraform s3_endpoint_policy local in vpc-endpoints/main.tf.

    If platform_bucket_arns is non-empty, produces a restrictive policy that:
      - Allows specific S3 actions on the listed bucket ARNs and their objects
      - Denies all S3 actions on resources not in the platform bucket list

    If platform_bucket_arns is empty, returns None (no restrictive policy).

    Args:
        platform_bucket_arns: List of S3 bucket ARNs belonging to the platform.

    Returns:
        A dict representing the IAM policy document, or None if no restriction.
    """
    if not platform_bucket_arns:
        return None

    # Build the resource list: bucket ARNs + object-level ARNs (bucket/*)
    resources = []
    for arn in platform_bucket_arns:
        resources.append(arn)
        resources.append(f"{arn}/*")

    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "AllowPlatformBucketsOnly",
                "Effect": "Allow",
                "Principal": "*",
                "Action": list(ALLOWED_S3_ACTIONS),
                "Resource": resources,
            },
            {
                "Sid": "DenyNonPlatformBuckets",
                "Effect": "Deny",
                "Principal": "*",
                "Action": "s3:*",
                "Resource": "*",
                "Condition": {
                    "StringNotEquals": {
                        "aws:ResourceArn": resources,
                    }
                },
            },
        ],
    }

    return policy


# ---------------------------------------------------------------------------
# Hypothesis Strategies
# ---------------------------------------------------------------------------

# Valid S3 bucket name rules (simplified for ARN generation):
#   - 3-63 characters, lowercase letters, numbers, hyphens, dots
#   - Must start and end with a letter or number
#   - No consecutive dots or dot-hyphen/hyphen-dot combinations
BUCKET_NAME_CHARS = st.sampled_from(
    "abcdefghijklmnopqrstuvwxyz0123456789-."
)


@st.composite
def valid_bucket_names(draw: st.DrawFn) -> str:
    """Generate valid S3 bucket names.

    S3 bucket names must be 3-63 characters, containing lowercase letters,
    numbers, hyphens, and dots, starting/ending with a letter or number.
    """
    # Start and end with alphanumeric
    start_end_chars = st.sampled_from("abcdefghijklmnopqrstuvwxyz0123456789")
    start = draw(start_end_chars)
    end = draw(start_end_chars)

    # Middle section: 1-20 characters (keeping names reasonable for testing)
    middle_length = draw(st.integers(min_value=1, max_value=20))
    middle_chars = []
    for _ in range(middle_length):
        ch = draw(BUCKET_NAME_CHARS)
        middle_chars.append(ch)

    name = start + "".join(middle_chars) + end

    # Avoid invalid patterns: consecutive dots, ip-address-like names
    assume(".." not in name)
    assume(".-" not in name)
    assume("-." not in name)
    # Ensure minimum length
    assume(len(name) >= 3)

    return name


@st.composite
def valid_bucket_arns(draw: st.DrawFn) -> str:
    """Generate valid S3 bucket ARNs from bucket names."""
    name = draw(valid_bucket_names())
    return f"arn:aws:s3:::{name}"


@st.composite
def valid_action_subsets(draw: st.DrawFn) -> List[str]:
    """Generate non-empty subsets of valid S3 actions.

    Used to verify the policy always includes the full action set
    regardless of what actions are requested (the endpoint policy
    is not parameterised by actions in the Terraform — it always
    includes the fixed set).
    """
    actions = draw(
        st.lists(
            st.sampled_from(ALLOWED_S3_ACTIONS),
            min_size=1,
            max_size=len(ALLOWED_S3_ACTIONS),
            unique=True,
        )
    )
    return actions


@st.composite
def platform_bucket_arn_lists(draw: st.DrawFn) -> List[str]:
    """Generate non-empty lists of unique platform bucket ARNs."""
    arns = draw(
        st.lists(
            valid_bucket_arns(),
            min_size=1,
            max_size=5,
            unique=True,
        )
    )
    return arns


# ---------------------------------------------------------------------------
# Property Tests
# ---------------------------------------------------------------------------


@pytest.mark.property
@settings(max_examples=100)
@given(bucket_arns=platform_bucket_arn_lists())
def test_policy_has_valid_iam_structure(bucket_arns: List[str]):
    """Property: generated policy is a structurally valid IAM policy document.

    For any non-empty list of platform bucket ARNs, the generated policy must:
    - Have a "Version" field equal to "2012-10-17"
    - Have a "Statement" field that is a non-empty list
    - Each statement must have Sid, Effect, Principal, Action, Resource fields

    **Validates: Requirements 11.7**
    """
    policy = generate_s3_endpoint_policy(bucket_arns)

    assert policy is not None
    assert policy["Version"] == "2012-10-17"
    assert isinstance(policy["Statement"], list)
    assert len(policy["Statement"]) == 2

    for stmt in policy["Statement"]:
        assert "Sid" in stmt
        assert "Effect" in stmt
        assert stmt["Effect"] in ("Allow", "Deny")
        assert "Principal" in stmt
        assert "Action" in stmt
        assert "Resource" in stmt


@pytest.mark.property
@settings(max_examples=100)
@given(bucket_arns=platform_bucket_arn_lists())
def test_allow_statement_covers_bucket_and_object_resources(bucket_arns: List[str]):
    """Property: Allow statement includes both bucket ARN and bucket/* for each bucket.

    For any combination of bucket ARNs, the Allow statement's Resource list
    must contain both the bucket-level ARN and the object-level ARN (arn/*).

    **Validates: Requirements 11.7**
    """
    policy = generate_s3_endpoint_policy(bucket_arns)
    assert policy is not None

    allow_stmt = policy["Statement"][0]
    assert allow_stmt["Sid"] == "AllowPlatformBucketsOnly"
    assert allow_stmt["Effect"] == "Allow"

    resources = allow_stmt["Resource"]

    for arn in bucket_arns:
        assert arn in resources, f"Bucket ARN {arn} missing from Allow resources"
        object_arn = f"{arn}/*"
        assert object_arn in resources, (
            f"Object ARN {object_arn} missing from Allow resources"
        )

    # Total resources should be exactly 2 per bucket (bucket + objects)
    assert len(resources) == len(bucket_arns) * 2


@pytest.mark.property
@settings(max_examples=100)
@given(bucket_arns=platform_bucket_arn_lists())
def test_deny_statement_excludes_platform_buckets(bucket_arns: List[str]):
    """Property: Deny statement uses StringNotEquals condition for platform ARNs.

    The deny statement must deny s3:* on all resources EXCEPT the platform
    bucket ARNs, using a StringNotEquals condition on aws:ResourceArn.

    **Validates: Requirements 11.7**
    """
    policy = generate_s3_endpoint_policy(bucket_arns)
    assert policy is not None

    deny_stmt = policy["Statement"][1]
    assert deny_stmt["Sid"] == "DenyNonPlatformBuckets"
    assert deny_stmt["Effect"] == "Deny"
    assert deny_stmt["Action"] == "s3:*"
    assert deny_stmt["Resource"] == "*"

    # Check condition
    assert "Condition" in deny_stmt
    condition = deny_stmt["Condition"]
    assert "StringNotEquals" in condition
    excluded_arns = condition["StringNotEquals"]["aws:ResourceArn"]

    # The condition must list the same ARNs as the Allow statement resources
    for arn in bucket_arns:
        assert arn in excluded_arns, (
            f"Bucket ARN {arn} not excluded from deny condition"
        )
        object_arn = f"{arn}/*"
        assert object_arn in excluded_arns, (
            f"Object ARN {object_arn} not excluded from deny condition"
        )


@pytest.mark.property
@settings(max_examples=100)
@given(bucket_arns=platform_bucket_arn_lists())
def test_allow_statement_contains_all_required_actions(bucket_arns: List[str]):
    """Property: Allow statement always includes the full set of S3 actions.

    The endpoint policy must permit exactly the defined set of S3 actions
    for platform buckets, regardless of which buckets are specified.

    **Validates: Requirements 11.7**
    """
    policy = generate_s3_endpoint_policy(bucket_arns)
    assert policy is not None

    allow_stmt = policy["Statement"][0]
    actions = allow_stmt["Action"]

    assert set(actions) == set(ALLOWED_S3_ACTIONS), (
        f"Allow actions {actions} don't match expected {ALLOWED_S3_ACTIONS}"
    )


@pytest.mark.property
@settings(max_examples=50)
@given(data=st.data())
def test_empty_bucket_list_returns_none(data: st.DataObject):
    """Property: empty bucket ARN list produces no restrictive policy.

    When no platform buckets are specified, the endpoint policy should be
    None (unrestricted), matching Terraform's conditional logic.

    **Validates: Requirements 11.7**
    """
    policy = generate_s3_endpoint_policy([])
    assert policy is None


@pytest.mark.property
@settings(max_examples=100)
@given(bucket_arns=platform_bucket_arn_lists())
def test_policy_serialises_to_valid_json(bucket_arns: List[str]):
    """Property: generated policy can be serialised to valid JSON.

    The Terraform jsonencode() function requires the policy to be a valid
    JSON-serialisable structure. This verifies round-trip serialisation.

    **Validates: Requirements 11.7**
    """
    policy = generate_s3_endpoint_policy(bucket_arns)
    assert policy is not None

    # Must serialise without error
    json_str = json.dumps(policy)
    assert isinstance(json_str, str)
    assert len(json_str) > 0

    # Must deserialise back to the same structure
    roundtripped = json.loads(json_str)
    assert roundtripped == policy


@pytest.mark.property
@settings(max_examples=100)
@given(bucket_arns=platform_bucket_arn_lists())
def test_principal_is_always_wildcard(bucket_arns: List[str]):
    """Property: both statements use Principal "*" (VPC endpoint-level control).

    VPC endpoint policies apply to all principals traversing the endpoint.
    Both Allow and Deny statements must use "*" as the principal.

    **Validates: Requirements 11.7**
    """
    policy = generate_s3_endpoint_policy(bucket_arns)
    assert policy is not None

    for stmt in policy["Statement"]:
        assert stmt["Principal"] == "*", (
            f"Statement '{stmt['Sid']}' has Principal '{stmt['Principal']}', "
            f"expected '*'"
        )
