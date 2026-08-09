"""Property-based tests for KMS key policy generation logic.

**Validates: Requirements 24.1, 24.6, 24.7**

Uses Hypothesis to verify that the KMS key policy correctly maps principals
to their allowed actions, ensuring management actions go only to administrators,
encrypt/decrypt only to users, and grant operations only to grant creators,
with appropriate conditions on user and grant creator statements.
"""

import json
import pytest
from hypothesis import given, settings, strategies as st, assume


# ---------------------------------------------------------------------------
# KMS Key Policy Generation (mirrors Terraform aws_iam_policy_document logic)
# ---------------------------------------------------------------------------

# Actions assigned to each principal category (matching the Terraform module)
ADMIN_ACTIONS = [
    "kms:Create*",
    "kms:Describe*",
    "kms:Enable*",
    "kms:List*",
    "kms:Put*",
    "kms:Update*",
    "kms:Revoke*",
    "kms:Disable*",
    "kms:Delete*",
    "kms:TagResource",
    "kms:ScheduleKeyDeletion",
    "kms:CancelKeyDeletion",
]

USER_ACTIONS = [
    "kms:Encrypt",
    "kms:Decrypt",
    "kms:ReEncrypt*",
    "kms:GenerateDataKey*",
    "kms:DescribeKey",
]

GRANT_ACTIONS = [
    "kms:CreateGrant",
    "kms:ListGrants",
    "kms:RevokeGrant",
]


def generate_kms_key_policy(
    account_id: str,
    key_administrator_arns: list[str],
    key_user_arns: list[str],
    grant_creator_arns: list[str],
    project: str,
    allowed_via_services: list[str],
) -> dict:
    """Generate a KMS key policy document mirroring the Terraform module logic.

    This produces the same JSON structure that the aws_iam_policy_document data
    source generates in the KMS Terraform module.
    """
    statements = []

    # Root account statement
    statements.append({
        "Sid": "EnableRootAccountAccess",
        "Effect": "Allow",
        "Principal": {"AWS": f"arn:aws:iam::{account_id}:root"},
        "Action": "kms:*",
        "Resource": "*",
    })

    # Key Administrators statement
    statements.append({
        "Sid": "KeyAdministrators",
        "Effect": "Allow",
        "Principal": {
            "AWS": key_administrator_arns
            if len(key_administrator_arns) > 1
            else key_administrator_arns[0]
        },
        "Action": ADMIN_ACTIONS,
        "Resource": "*",
    })

    # Key Users statement (with encryption context and ViaService conditions)
    statements.append({
        "Sid": "KeyUsers",
        "Effect": "Allow",
        "Principal": {
            "AWS": key_user_arns if len(key_user_arns) > 1 else key_user_arns[0]
        },
        "Action": USER_ACTIONS,
        "Resource": "*",
        "Condition": {
            "StringEquals": {
                "kms:EncryptionContext:Project": project,
                "kms:ViaService": allowed_via_services,
            }
        },
    })

    # Grant Creators statement (with GrantIsForAWSResource condition)
    statements.append({
        "Sid": "GrantCreators",
        "Effect": "Allow",
        "Principal": {
            "AWS": grant_creator_arns
            if len(grant_creator_arns) > 1
            else grant_creator_arns[0]
        },
        "Action": GRANT_ACTIONS,
        "Resource": "*",
        "Condition": {
            "Bool": {
                "kms:GrantIsForAWSResource": "true",
            }
        },
    })

    return {
        "Version": "2012-10-17",
        "Statement": statements,
    }


# ---------------------------------------------------------------------------
# Hypothesis Strategies
# ---------------------------------------------------------------------------

def arn_strategy():
    """Generate valid IAM role/user ARNs."""
    account_ids = st.from_regex(r"[0-9]{12}", fullmatch=True)
    role_names = st.from_regex(r"[A-Za-z][A-Za-z0-9_+=,.@-]{0,63}", fullmatch=True)
    return st.builds(
        lambda acc, name: f"arn:aws:iam::{acc}:role/{name}",
        account_ids,
        role_names,
    )


def arn_list_strategy(min_size: int = 1, max_size: int = 5):
    """Generate a list of unique valid IAM ARNs."""
    return st.lists(arn_strategy(), min_size=min_size, max_size=max_size, unique=True)


def project_name_strategy():
    """Generate valid project names (1-64 chars, lowercase with hyphens)."""
    return st.from_regex(r"[a-z][a-z0-9-]{0,62}[a-z0-9]", fullmatch=True)


def via_service_strategy():
    """Generate valid AWS service principal identifiers for kms:ViaService."""
    services = st.sampled_from([
        "rds", "elasticache", "s3", "backup", "ebs", "secretsmanager"
    ])
    regions = st.sampled_from([
        "eu-west-1", "eu-west-2", "us-east-1", "us-west-2"
    ])
    return st.builds(
        lambda svc, region: f"{svc}.{region}.amazonaws.com",
        services,
        regions,
    )


@st.composite
def kms_policy_inputs(draw):
    """Generate valid KMS key policy inputs."""
    account_id = draw(st.from_regex(r"[0-9]{12}", fullmatch=True))
    admin_arns = draw(arn_list_strategy(min_size=1, max_size=3))
    user_arns = draw(arn_list_strategy(min_size=1, max_size=4))
    grant_arns = draw(arn_list_strategy(min_size=1, max_size=3))
    project = draw(project_name_strategy())
    services = draw(st.lists(via_service_strategy(), min_size=1, max_size=4, unique=True))

    # Ensure no overlap between principal categories
    all_arns = set(admin_arns + user_arns + grant_arns)
    assume(
        len(all_arns) == len(admin_arns) + len(user_arns) + len(grant_arns)
    )

    return {
        "account_id": account_id,
        "key_administrator_arns": admin_arns,
        "key_user_arns": user_arns,
        "grant_creator_arns": grant_arns,
        "project": project,
        "allowed_via_services": services,
    }


# ---------------------------------------------------------------------------
# Helper functions for extracting statement data
# ---------------------------------------------------------------------------

def find_statement(policy: dict, sid: str) -> dict | None:
    """Find a statement by Sid in the policy document."""
    for stmt in policy["Statement"]:
        if stmt.get("Sid") == sid:
            return stmt
    return None


def get_actions(statement: dict) -> list[str]:
    """Extract actions from a statement as a list."""
    actions = statement.get("Action", [])
    if isinstance(actions, str):
        return [actions]
    return actions


def get_principals(statement: dict) -> list[str]:
    """Extract AWS principals from a statement as a list."""
    principal = statement.get("Principal", {})
    if isinstance(principal, dict):
        aws_principals = principal.get("AWS", [])
    else:
        aws_principals = principal
    if isinstance(aws_principals, str):
        return [aws_principals]
    return aws_principals


# ---------------------------------------------------------------------------
# Property Tests
# ---------------------------------------------------------------------------


@pytest.mark.property
@settings(max_examples=50)
@given(inputs=kms_policy_inputs())
def test_management_actions_only_in_administrators_statement(inputs):
    """Property: Management actions (kms:Create*, kms:Describe*, etc.) appear
    ONLY in the KeyAdministrators statement, never in KeyUsers or GrantCreators.

    **Validates: Requirements 24.1, 24.6, 24.7**
    """
    policy = generate_kms_key_policy(**inputs)

    admin_stmt = find_statement(policy, "KeyAdministrators")
    user_stmt = find_statement(policy, "KeyUsers")
    grant_stmt = find_statement(policy, "GrantCreators")

    assert admin_stmt is not None
    assert user_stmt is not None
    assert grant_stmt is not None

    admin_actions = get_actions(admin_stmt)
    user_actions = get_actions(user_stmt)
    grant_actions = get_actions(grant_stmt)

    # All admin actions must be in the administrators statement
    for action in ADMIN_ACTIONS:
        assert action in admin_actions

    # No admin actions in user or grant statements
    for action in ADMIN_ACTIONS:
        assert action not in user_actions
        assert action not in grant_actions


@pytest.mark.property
@settings(max_examples=50)
@given(inputs=kms_policy_inputs())
def test_encrypt_decrypt_actions_only_in_users_statement(inputs):
    """Property: Encrypt/decrypt actions appear ONLY in the KeyUsers statement,
    never in KeyAdministrators or GrantCreators.

    **Validates: Requirements 24.1, 24.6, 24.7**
    """
    policy = generate_kms_key_policy(**inputs)

    admin_stmt = find_statement(policy, "KeyAdministrators")
    user_stmt = find_statement(policy, "KeyUsers")
    grant_stmt = find_statement(policy, "GrantCreators")

    admin_actions = get_actions(admin_stmt)
    user_actions = get_actions(user_stmt)
    grant_actions = get_actions(grant_stmt)

    # All user actions must be in the users statement
    for action in USER_ACTIONS:
        assert action in user_actions

    # No user actions in admin or grant statements
    for action in USER_ACTIONS:
        assert action not in admin_actions
        assert action not in grant_actions


@pytest.mark.property
@settings(max_examples=50)
@given(inputs=kms_policy_inputs())
def test_grant_actions_only_in_grant_creators_statement(inputs):
    """Property: Grant actions appear ONLY in the GrantCreators statement,
    never in KeyAdministrators or KeyUsers.

    **Validates: Requirements 24.1, 24.6, 24.7**
    """
    policy = generate_kms_key_policy(**inputs)

    admin_stmt = find_statement(policy, "KeyAdministrators")
    user_stmt = find_statement(policy, "KeyUsers")
    grant_stmt = find_statement(policy, "GrantCreators")

    admin_actions = get_actions(admin_stmt)
    user_actions = get_actions(user_stmt)
    grant_actions_actual = get_actions(grant_stmt)

    # All grant actions must be in the grant creators statement
    for action in GRANT_ACTIONS:
        assert action in grant_actions_actual

    # No grant actions in admin or user statements
    for action in GRANT_ACTIONS:
        assert action not in admin_actions
        assert action not in user_actions


@pytest.mark.property
@settings(max_examples=50)
@given(inputs=kms_policy_inputs())
def test_key_users_statement_has_encryption_context_condition(inputs):
    """Property: The KeyUsers statement always has the encryption context condition
    (kms:EncryptionContext:Project) matching the project name.

    **Validates: Requirements 24.1, 24.6, 24.7**
    """
    policy = generate_kms_key_policy(**inputs)

    user_stmt = find_statement(policy, "KeyUsers")
    assert user_stmt is not None

    # Must have a Condition block
    assert "Condition" in user_stmt
    condition = user_stmt["Condition"]

    # Must have StringEquals with encryption context
    assert "StringEquals" in condition
    string_equals = condition["StringEquals"]
    assert "kms:EncryptionContext:Project" in string_equals
    assert string_equals["kms:EncryptionContext:Project"] == inputs["project"]

    # Must also have ViaService condition
    assert "kms:ViaService" in string_equals
    assert string_equals["kms:ViaService"] == inputs["allowed_via_services"]


@pytest.mark.property
@settings(max_examples=50)
@given(inputs=kms_policy_inputs())
def test_grant_creators_statement_has_grant_is_for_aws_resource_condition(inputs):
    """Property: The GrantCreators statement always has the GrantIsForAWSResource
    condition set to 'true'.

    **Validates: Requirements 24.1, 24.6, 24.7**
    """
    policy = generate_kms_key_policy(**inputs)

    grant_stmt = find_statement(policy, "GrantCreators")
    assert grant_stmt is not None

    # Must have a Condition block
    assert "Condition" in grant_stmt
    condition = grant_stmt["Condition"]

    # Must have Bool condition with GrantIsForAWSResource
    assert "Bool" in condition
    bool_condition = condition["Bool"]
    assert "kms:GrantIsForAWSResource" in bool_condition
    assert bool_condition["kms:GrantIsForAWSResource"] == "true"


@pytest.mark.property
@settings(max_examples=50)
@given(inputs=kms_policy_inputs())
def test_policy_is_valid_json_structure(inputs):
    """Property: The generated policy is always a valid JSON-serialisable
    IAM policy document with correct structure.

    **Validates: Requirements 24.1, 24.6, 24.7**
    """
    policy = generate_kms_key_policy(**inputs)

    # Must be JSON-serialisable
    policy_json = json.dumps(policy)
    parsed = json.loads(policy_json)

    # Must have required top-level keys
    assert parsed["Version"] == "2012-10-17"
    assert "Statement" in parsed
    assert isinstance(parsed["Statement"], list)

    # Must have exactly 4 statements (root, admin, users, grant creators)
    assert len(parsed["Statement"]) == 4

    # All statements must have required fields
    for stmt in parsed["Statement"]:
        assert "Sid" in stmt
        assert "Effect" in stmt
        assert "Principal" in stmt
        assert "Action" in stmt
        assert "Resource" in stmt
        assert stmt["Effect"] == "Allow"
        assert stmt["Resource"] == "*"


@pytest.mark.property
@settings(max_examples=50)
@given(inputs=kms_policy_inputs())
def test_principals_correctly_assigned_to_statements(inputs):
    """Property: Each principal category is assigned only to its own statement,
    with no cross-contamination of principals between statements.

    **Validates: Requirements 24.1, 24.6, 24.7**
    """
    policy = generate_kms_key_policy(**inputs)

    admin_stmt = find_statement(policy, "KeyAdministrators")
    user_stmt = find_statement(policy, "KeyUsers")
    grant_stmt = find_statement(policy, "GrantCreators")

    admin_principals = get_principals(admin_stmt)
    user_principals = get_principals(user_stmt)
    grant_principals = get_principals(grant_stmt)

    # Admin principals match input
    assert set(admin_principals) == set(inputs["key_administrator_arns"])

    # User principals match input
    assert set(user_principals) == set(inputs["key_user_arns"])

    # Grant creator principals match input
    assert set(grant_principals) == set(inputs["grant_creator_arns"])

    # No overlap (enforced by assume in strategy, but verify in output)
    assert not set(admin_principals) & set(user_principals)
    assert not set(admin_principals) & set(grant_principals)
    assert not set(user_principals) & set(grant_principals)
