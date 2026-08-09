"""Shared test fixtures for the Secure Multi-Tier Platform."""

from __future__ import annotations

import os
import uuid
from typing import AsyncGenerator, Generator

import boto3
import pytest
import redis
from hypothesis import settings, HealthCheck
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import Settings
from app.models import Base

# ---------------------------------------------------------------------------
# Hypothesis Profiles
# ---------------------------------------------------------------------------

# Configure Hypothesis profiles for local vs CI execution.
# Local development defaults to 10 examples for fast feedback;
# CI uses HYPOTHESIS_MAX_EXAMPLES env var (default 200) for thorough testing.
_max_examples = int(os.environ.get("HYPOTHESIS_MAX_EXAMPLES", "10"))

settings.register_profile(
    "ci",
    max_examples=200,
    suppress_health_check=[HealthCheck.too_slow],
    deadline=None,
)
settings.register_profile(
    "dev",
    max_examples=10,
    suppress_health_check=[HealthCheck.too_slow],
    deadline=None,
)
settings.register_profile(
    "default",
    max_examples=_max_examples,
    suppress_health_check=[HealthCheck.too_slow],
    deadline=None,
)

# Load CI profile when HYPOTHESIS_MAX_EXAMPLES is set (GitHub Actions),
# otherwise use dev profile for local development.
if os.environ.get("HYPOTHESIS_MAX_EXAMPLES"):
    settings.load_profile("ci")
else:
    settings.load_profile("dev")


# ---------------------------------------------------------------------------
# Test Configuration
# ---------------------------------------------------------------------------

# Use a separate test database to avoid polluting dev data.
_TEST_DB_NAME = "platform_test_db"
_POSTGRES_ADMIN_URL = os.environ.get(
    "TEST_POSTGRES_ADMIN_URL",
    "postgresql+asyncpg://platform_user:platform_local_password@localhost:5432/postgres",
)
_TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    f"postgresql+asyncpg://platform_user:platform_local_password@localhost:5432/{_TEST_DB_NAME}",
)
_TEST_REDIS_URL = os.environ.get(
    "TEST_REDIS_URL",
    "redis://:redis_local_password@localhost:6379/1",  # DB 1 for tests
)
_LOCALSTACK_ENDPOINT = os.environ.get("AWS_ENDPOINT_URL", "http://localhost:4566")
_AWS_REGION = os.environ.get("AWS_DEFAULT_REGION", "eu-west-2")


# ---------------------------------------------------------------------------
# Common Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def anyio_backend():
    """Use asyncio as the async backend for tests."""
    return "asyncio"


@pytest.fixture
def test_settings() -> Settings:
    """Return a Settings instance configured for the test environment."""
    return Settings(
        environment="local",
        database_url=_TEST_DATABASE_URL,
        redis_url=_TEST_REDIS_URL,
        aws_endpoint_url=_LOCALSTACK_ENDPOINT,
        aws_default_region=_AWS_REGION,
        aws_access_key_id="test",
        aws_secret_access_key="test",
        db_ssl_required=False,
        redis_ssl_enabled=False,
    )


# ---------------------------------------------------------------------------
# Database Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def event_loop():
    """Create a single event loop for the entire test session.

    Required for session-scoped async fixtures.
    """
    import asyncio

    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def _create_test_database() -> AsyncGenerator[None, None]:
    """Create the test database if it does not exist (session scope).

    Drops the database at the end of the session for cleanup.
    """
    engine = create_async_engine(
        _POSTGRES_ADMIN_URL,
        isolation_level="AUTOCOMMIT",
    )
    async with engine.connect() as conn:
        # Check if test DB exists
        result = await conn.execute(
            text(f"SELECT 1 FROM pg_database WHERE datname = '{_TEST_DB_NAME}'")
        )
        if not result.scalar():
            await conn.execute(text(f"CREATE DATABASE {_TEST_DB_NAME}"))

    await engine.dispose()

    yield

    # Teardown: drop the test database
    engine = create_async_engine(
        _POSTGRES_ADMIN_URL,
        isolation_level="AUTOCOMMIT",
    )
    async with engine.connect() as conn:
        # Terminate other connections before dropping
        await conn.execute(
            text(
                f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                f"WHERE datname = '{_TEST_DB_NAME}' AND pid <> pg_backend_pid()"
            )
        )
        await conn.execute(text(f"DROP DATABASE IF EXISTS {_TEST_DB_NAME}"))
    await engine.dispose()


@pytest.fixture(scope="session")
async def db_engine(_create_test_database: None) -> AsyncGenerator[AsyncEngine, None]:
    """Provide a SQLAlchemy async engine connected to the test database.

    Creates all tables at start and disposes engine on teardown.
    """
    engine = create_async_engine(_TEST_DATABASE_URL, echo=False)

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Drop all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
async def db_session(db_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Provide a transactional database session that rolls back after each test.

    Each test gets a clean slate without persisting data.
    """
    async with db_engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False)

        yield session

        await session.close()
        await transaction.rollback()


@pytest.fixture
async def db_session_factory(
    db_engine: AsyncEngine,
) -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    """Provide a session factory for tests that need multiple sessions."""
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    yield factory


# ---------------------------------------------------------------------------
# Cache (Redis) Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def redis_client() -> Generator[redis.Redis, None, None]:
    """Provide a Redis client connected to the test database (DB 1).

    Flushes the test database before and after each test.
    """
    client = redis.Redis.from_url(_TEST_REDIS_URL, decode_responses=True)
    client.flushdb()

    yield client

    client.flushdb()
    client.close()


@pytest.fixture
async def async_redis_client() -> AsyncGenerator[redis.asyncio.Redis, None]:
    """Provide an async Redis client for tests requiring async cache access.

    Flushes the test database before and after each test.
    """
    client = redis.asyncio.Redis.from_url(_TEST_REDIS_URL, decode_responses=True)
    await client.flushdb()

    yield client

    await client.flushdb()
    await client.aclose()


# ---------------------------------------------------------------------------
# LocalStack (AWS) Fixtures
# ---------------------------------------------------------------------------


def _boto3_client(service_name: str) -> boto3.client:
    """Create a boto3 client pointing at LocalStack."""
    return boto3.client(
        service_name,
        endpoint_url=_LOCALSTACK_ENDPOINT,
        region_name=_AWS_REGION,
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )


@pytest.fixture
def localstack_kms() -> Generator[boto3.client, None, None]:
    """Provide a KMS client against LocalStack.

    Creates a test key and cleans up afterwards.
    """
    client = _boto3_client("kms")
    yield client


@pytest.fixture
def kms_test_key(localstack_kms) -> Generator[str, None, None]:
    """Create a KMS key in LocalStack and return its ARN.

    Schedules deletion on teardown.
    """
    response = localstack_kms.create_key(
        Description="Test key for platform tests",
        KeyUsage="ENCRYPT_DECRYPT",
        Tags=[{"TagKey": "Project", "TagValue": "secure-multi-tier-platform"}],
    )
    key_id = response["KeyMetadata"]["KeyId"]
    key_arn = response["KeyMetadata"]["Arn"]

    yield key_arn

    localstack_kms.schedule_key_deletion(KeyId=key_id, PendingWindowInDays=7)


@pytest.fixture
def localstack_secrets_manager() -> Generator[boto3.client, None, None]:
    """Provide a Secrets Manager client against LocalStack."""
    client = _boto3_client("secretsmanager")
    yield client


@pytest.fixture
def test_secret(localstack_secrets_manager) -> Generator[str, None, None]:
    """Create a test secret in LocalStack and return its ARN.

    Deletes the secret on teardown.
    """
    secret_name = f"test/platform-secret-{uuid.uuid4().hex[:8]}"
    response = localstack_secrets_manager.create_secret(
        Name=secret_name,
        SecretString='{"username": "test_user", "password": "test_password"}',
    )
    secret_arn = response["ARN"]

    yield secret_arn

    localstack_secrets_manager.delete_secret(
        SecretId=secret_arn, ForceDeleteWithoutRecovery=True
    )


@pytest.fixture
def localstack_backup() -> Generator[boto3.client, None, None]:
    """Provide an AWS Backup client against LocalStack."""
    client = _boto3_client("backup")
    yield client


@pytest.fixture
def test_backup_vault(localstack_backup) -> Generator[str, None, None]:
    """Create a test backup vault in LocalStack and return its name.

    Deletes the vault on teardown.
    """
    vault_name = f"test-vault-{uuid.uuid4().hex[:8]}"
    localstack_backup.create_backup_vault(BackupVaultName=vault_name)

    yield vault_name

    try:
        localstack_backup.delete_backup_vault(BackupVaultName=vault_name)
    except Exception:
        pass  # Vault may already be deleted or not supported fully


@pytest.fixture
def localstack_service_quotas() -> Generator[boto3.client, None, None]:
    """Provide a Service Quotas client against LocalStack."""
    client = _boto3_client("service-quotas")
    yield client


@pytest.fixture
def localstack_s3() -> Generator[boto3.client, None, None]:
    """Provide an S3 client against LocalStack with automatic cleanup."""
    client = _boto3_client("s3")
    created_buckets: list[str] = []

    # Monkey-patch create_bucket to track buckets for cleanup
    original_create = client.create_bucket

    def tracked_create(*args, **kwargs):
        response = original_create(*args, **kwargs)
        bucket_name = kwargs.get("Bucket") or (args[0] if args else None)
        if bucket_name:
            created_buckets.append(bucket_name)
        return response

    client.create_bucket = tracked_create

    yield client

    # Cleanup: empty and delete created buckets
    for bucket in created_buckets:
        try:
            objects = client.list_objects_v2(Bucket=bucket).get("Contents", [])
            if objects:
                client.delete_objects(
                    Bucket=bucket,
                    Delete={"Objects": [{"Key": obj["Key"]} for obj in objects]},
                )
            client.delete_bucket(Bucket=bucket)
        except Exception:
            pass


@pytest.fixture
def localstack_sns() -> Generator[boto3.client, None, None]:
    """Provide an SNS client against LocalStack."""
    client = _boto3_client("sns")
    yield client


@pytest.fixture
def test_sns_topic(localstack_sns) -> Generator[str, None, None]:
    """Create a test SNS topic and return its ARN. Deletes on teardown."""
    topic_name = f"test-topic-{uuid.uuid4().hex[:8]}"
    response = localstack_sns.create_topic(Name=topic_name)
    topic_arn = response["TopicArn"]

    yield topic_arn

    localstack_sns.delete_topic(TopicArn=topic_arn)


@pytest.fixture
def localstack_iam() -> Generator[boto3.client, None, None]:
    """Provide an IAM client against LocalStack."""
    client = _boto3_client("iam")
    yield client


@pytest.fixture
def localstack_cloudwatch_logs() -> Generator[boto3.client, None, None]:
    """Provide a CloudWatch Logs client against LocalStack."""
    client = _boto3_client("logs")
    yield client
