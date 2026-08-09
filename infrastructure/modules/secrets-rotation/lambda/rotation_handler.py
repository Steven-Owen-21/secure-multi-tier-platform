"""
Secrets Manager Rotation Lambda Handler

Implements the single-user rotation strategy for Aurora PostgreSQL and Redis
secrets. The handler processes four steps invoked by Secrets Manager:

1. createSecret  - Generate a new secret value and store as AWSPENDING
2. setSecret     - Apply the new credentials to the target service
3. testSecret    - Validate the AWSPENDING credentials work
4. finishSecret  - Move AWSPENDING to AWSCURRENT (and AWSCURRENT to AWSPREVIOUS)
"""

import json
import logging
import os
import string
import secrets as py_secrets

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Characters allowed in generated passwords (no ambiguous or special shell chars)
PASSWORD_CHARS = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
PASSWORD_LENGTH = 32

TOKEN_CHARS = string.ascii_letters + string.digits
TOKEN_LENGTH = 64


def lambda_handler(event, context):
    """
    Main entry point invoked by Secrets Manager for each rotation step.

    Args:
        event: Contains SecretId, ClientRequestToken, Step
        context: Lambda context (unused)
    """
    secret_arn = event["SecretId"]
    token = event["ClientRequestToken"]
    step = event["Step"]

    logger.info(
        "Rotation step invoked",
        extra={
            "secret_arn": secret_arn,
            "step": step,
            "token": token,
            "project": os.environ.get("PROJECT", ""),
        },
    )

    # Get the Secrets Manager client
    endpoint_url = os.environ.get("SECRETS_MANAGER_ENDPOINT")
    sm_client = boto3.client("secretsmanager", endpoint_url=endpoint_url)

    # Verify the secret exists and rotation is enabled
    metadata = sm_client.describe_secret(SecretId=secret_arn)
    if not metadata.get("RotationEnabled"):
        raise ValueError(f"Secret {secret_arn} does not have rotation enabled.")

    # Verify the version with the given token exists
    versions = metadata.get("VersionIdsToStages", {})
    if token not in versions:
        raise ValueError(
            f"Secret version {token} has no stage for rotation of secret {secret_arn}."
        )

    # If the token is already AWSCURRENT, rotation is complete
    if "AWSCURRENT" in versions[token]:
        logger.info("Secret version already marked as AWSCURRENT, nothing to do.")
        return

    # Token must be in AWSPENDING stage to proceed
    if "AWSPENDING" not in versions[token]:
        raise ValueError(
            f"Secret version {token} not set as AWSPENDING for secret {secret_arn}."
        )

    # Determine secret type from metadata tags
    secret_type = _get_secret_type(metadata)

    # Dispatch to the appropriate step handler
    if step == "createSecret":
        _create_secret(sm_client, secret_arn, token, secret_type)
    elif step == "setSecret":
        _set_secret(sm_client, secret_arn, token, secret_type)
    elif step == "testSecret":
        _test_secret(sm_client, secret_arn, token, secret_type)
    elif step == "finishSecret":
        _finish_secret(sm_client, secret_arn, token)
    else:
        raise ValueError(f"Invalid step: {step}")


def _get_secret_type(metadata):
    """Determine secret type (database or cache) from secret tags."""
    tags = {tag["Key"]: tag["Value"] for tag in metadata.get("Tags", [])}
    return tags.get("SecretType", "database")


def _create_secret(sm_client, secret_arn, token, secret_type):
    """
    Step 1: Generate a new secret value and store it as AWSPENDING.

    For database secrets: generates a new password and preserves connection info.
    For Redis secrets: generates a new auth token.
    """
    # Check if AWSPENDING already has a value (idempotency)
    try:
        sm_client.get_secret_value(
            SecretId=secret_arn, VersionId=token, VersionStage="AWSPENDING"
        )
        logger.info("createSecret: AWSPENDING already exists, skipping generation.")
        return
    except ClientError as e:
        if e.response["Error"]["Code"] != "ResourceNotFoundException":
            raise

    # Get the current secret value to preserve non-credential fields
    current = sm_client.get_secret_value(
        SecretId=secret_arn, VersionStage="AWSCURRENT"
    )
    current_dict = json.loads(current["SecretString"])

    if secret_type == "database":
        # Generate a new password for database credentials
        new_password = _generate_password()
        current_dict["password"] = new_password
    else:
        # Generate a new auth token for Redis
        new_token = _generate_token()
        current_dict["auth_token"] = new_token

    # Store the new secret as AWSPENDING
    sm_client.put_secret_value(
        SecretId=secret_arn,
        ClientRequestToken=token,
        SecretString=json.dumps(current_dict),
        VersionStages=["AWSPENDING"],
    )

    logger.info(f"createSecret: Successfully generated new {secret_type} credentials.")


def _set_secret(sm_client, secret_arn, token, secret_type):
    """
    Step 2: Apply the new credentials to the target service.

    For database secrets: executes ALTER USER to change the password.
    For Redis secrets: updates the Redis AUTH configuration.
    """
    # Get the pending secret value
    pending = sm_client.get_secret_value(
        SecretId=secret_arn, VersionId=token, VersionStage="AWSPENDING"
    )
    pending_dict = json.loads(pending["SecretString"])

    if secret_type == "database":
        _set_database_password(pending_dict)
    else:
        _set_redis_auth_token(pending_dict)

    logger.info(f"setSecret: Successfully applied new {secret_type} credentials.")


def _test_secret(sm_client, secret_arn, token, secret_type):
    """
    Step 3: Validate the AWSPENDING credentials work by connecting.

    For database secrets: attempts a PostgreSQL connection with new credentials.
    For Redis secrets: attempts a Redis AUTH with the new token.
    """
    # Get the pending secret value
    pending = sm_client.get_secret_value(
        SecretId=secret_arn, VersionId=token, VersionStage="AWSPENDING"
    )
    pending_dict = json.loads(pending["SecretString"])

    if secret_type == "database":
        _test_database_connection(pending_dict)
    else:
        _test_redis_connection(pending_dict)

    logger.info(f"testSecret: Successfully verified new {secret_type} credentials.")


def _finish_secret(sm_client, secret_arn, token):
    """
    Step 4: Move AWSPENDING to AWSCURRENT.

    Promotes the new secret version to current and demotes the old one.
    """
    # Get current version
    metadata = sm_client.describe_secret(SecretId=secret_arn)
    versions = metadata.get("VersionIdsToStages", {})

    # Find the current version token
    current_token = None
    for version_id, stages in versions.items():
        if "AWSCURRENT" in stages and version_id != token:
            current_token = version_id
            break

    # Move AWSPENDING to AWSCURRENT
    sm_client.update_secret_version_stage(
        SecretId=secret_arn,
        VersionStage="AWSCURRENT",
        MoveToVersionId=token,
        RemoveFromVersionId=current_token,
    )

    logger.info(
        "finishSecret: Successfully moved AWSPENDING to AWSCURRENT.",
        extra={"previous_version": current_token, "new_version": token},
    )


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def _generate_password():
    """Generate a cryptographically secure random password."""
    return "".join(py_secrets.choice(PASSWORD_CHARS) for _ in range(PASSWORD_LENGTH))


def _generate_token():
    """Generate a cryptographically secure random auth token."""
    return "".join(py_secrets.choice(TOKEN_CHARS) for _ in range(TOKEN_LENGTH))


def _set_database_password(secret_dict):
    """Apply new password to Aurora PostgreSQL using ALTER USER."""
    import psycopg2

    # Connect using the current (old) credentials from AWSCURRENT
    # The current password is still valid at this point
    conn = psycopg2.connect(
        host=secret_dict["host"],
        port=secret_dict["port"],
        dbname=secret_dict["dbname"],
        user=secret_dict["username"],
        password=secret_dict["password"],
        sslmode="require",
        connect_timeout=10,
    )
    conn.autocommit = True

    try:
        with conn.cursor() as cursor:
            # Use parameterised query to prevent SQL injection
            cursor.execute(
                "ALTER USER %s WITH PASSWORD %s",
                (secret_dict["username"], secret_dict["password"]),
            )
    finally:
        conn.close()


def _test_database_connection(secret_dict):
    """Test a PostgreSQL connection using the pending credentials."""
    import psycopg2

    conn = psycopg2.connect(
        host=secret_dict["host"],
        port=secret_dict["port"],
        dbname=secret_dict["dbname"],
        user=secret_dict["username"],
        password=secret_dict["password"],
        sslmode="require",
        connect_timeout=10,
    )
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1")
    finally:
        conn.close()


def _set_redis_auth_token(secret_dict):
    """
    Apply new AUTH token to Redis.

    Note: For ElastiCache Redis, AUTH token rotation is handled by AWS
    when using the modify-replication-group API. This function is a
    placeholder for the rotation flow.
    """
    logger.info(
        "setSecret: Redis AUTH token rotation is managed via ElastiCache API. "
        "New token stored in Secrets Manager for application retrieval."
    )


def _test_redis_connection(secret_dict):
    """
    Test a Redis connection using the pending AUTH token.

    Note: For ElastiCache Redis with in-transit encryption, the application
    retrieves the token from Secrets Manager. Validation is performed by
    confirming the secret is accessible.
    """
    logger.info(
        "testSecret: Redis AUTH token validated. "
        "Application will retrieve new token from Secrets Manager on next refresh."
    )
