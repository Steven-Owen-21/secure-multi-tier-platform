"""Application configuration using Pydantic Settings for environment-based config."""

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    All values have sensible defaults for local development with docker-compose.
    In AWS, environment variables are injected via ECS task definition.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application ---
    environment: Literal["local", "demo"] = "local"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "DEBUG"
    app_port: int = 8000
    app_host: str = "0.0.0.0"

    # --- Database (PostgreSQL) ---
    database_url: str = (
        "postgresql+asyncpg://platform_user:platform_local_password@localhost:5432/platform_db"
    )
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_ssl_required: bool = False

    # --- Cache (Redis) ---
    redis_url: str = "redis://:redis_local_password@localhost:6379/0"
    redis_ssl_enabled: bool = False
    redis_session_ttl: int = 3600
    redis_cache_default_ttl: int = 300

    # --- AWS / LocalStack ---
    aws_endpoint_url: str | None = "http://localhost:4566"
    aws_default_region: str = "eu-west-2"
    aws_access_key_id: str | None = "test"
    aws_secret_access_key: str | None = "test"

    # --- Cognito Authentication ---
    cognito_user_pool_id: str = "local_user_pool"
    cognito_client_id: str = "local_client_id"
    cognito_region: str = "eu-west-2"
    cognito_jwks_url: str = (
        "http://localhost:4566/eu-west-2_local/.well-known/jwks.json"
    )

    # --- Secrets Manager ---
    secrets_db_arn: str = (
        "arn:aws:secretsmanager:eu-west-2:000000000000:secret:platform/db-credentials"
    )
    secrets_redis_arn: str = (
        "arn:aws:secretsmanager:eu-west-2:000000000000:secret:platform/redis-credentials"
    )
    secrets_cache_ttl: int = 86400

    # --- SNS Notifications ---
    sns_alerts_topic_arn: str = "arn:aws:sns:eu-west-2:000000000000:platform-alerts"

    # --- KMS ---
    kms_key_arn: str = "arn:aws:kms:eu-west-2:000000000000:key/local-key-id"

    @property
    def is_local(self) -> bool:
        """Check if running in local development mode."""
        return self.environment == "local"


def get_settings() -> Settings:
    """Create and return application settings singleton."""
    return Settings()
