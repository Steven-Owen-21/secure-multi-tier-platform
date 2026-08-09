"""Unit tests for the SecretsClient implementation."""

import json
import time
from unittest.mock import MagicMock, patch

import pytest

from app.services.secrets_client import Credentials, SecretsClient, _CachedCredential


@pytest.fixture
def secrets_client() -> SecretsClient:
    """Create a SecretsClient with a short TTL for testing."""
    return SecretsClient(
        endpoint_url="http://localhost:4566",
        region_name="eu-west-2",
        cache_ttl_seconds=60,  # 60 seconds for test purposes
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )


@pytest.fixture
def sample_secret_response() -> dict:
    """Sample Secrets Manager response."""
    return {
        "SecretString": json.dumps(
            {
                "username": "db_user",
                "password": "super_secret_password",
                "host": "localhost",
                "port": "5432",
                "dbname": "platform_db",
                "engine": "postgres",
            }
        )
    }


class TestCredentials:
    """Tests for the Credentials dataclass."""

    def test_credentials_creation(self):
        creds = Credentials(
            username="user",
            password="pass",
            host="localhost",
            port=5432,
            dbname="testdb",
            engine="postgres",
        )
        assert creds.username == "user"
        assert creds.password == "pass"
        assert creds.host == "localhost"
        assert creds.port == 5432
        assert creds.dbname == "testdb"
        assert creds.engine == "postgres"

    def test_credentials_to_dict(self):
        creds = Credentials(username="user", password="pass")
        result = creds.to_dict()
        assert result["username"] == "user"
        assert result["password"] == "pass"
        assert result["host"] is None
        assert result["port"] is None

    def test_credentials_immutable(self):
        creds = Credentials(username="user", password="pass")
        with pytest.raises(AttributeError):
            creds.username = "other"  # type: ignore[misc]


class TestIsCacheValid:
    """Tests for the is_cache_valid method."""

    def test_no_cache_entry_returns_false(self, secrets_client: SecretsClient):
        assert secrets_client.is_cache_valid("arn:aws:secretsmanager:eu-west-2:000:secret:test") is False

    def test_valid_cache_returns_true(self, secrets_client: SecretsClient):
        arn = "arn:aws:secretsmanager:eu-west-2:000:secret:test"
        secrets_client._cache[arn] = _CachedCredential(
            credentials=Credentials(username="u", password="p"),
            fetched_at=time.time(),  # just now
        )
        assert secrets_client.is_cache_valid(arn) is True

    def test_expired_cache_returns_false(self, secrets_client: SecretsClient):
        arn = "arn:aws:secretsmanager:eu-west-2:000:secret:test"
        secrets_client._cache[arn] = _CachedCredential(
            credentials=Credentials(username="u", password="p"),
            fetched_at=time.time() - 120,  # 120 seconds ago, TTL is 60
        )
        assert secrets_client.is_cache_valid(arn) is False


class TestGetCredentials:
    """Tests for the get_credentials method."""

    @pytest.mark.asyncio
    async def test_returns_cached_credentials_when_valid(self, secrets_client: SecretsClient):
        arn = "arn:aws:secretsmanager:eu-west-2:000:secret:test"
        expected_creds = Credentials(username="cached_user", password="cached_pass")
        secrets_client._cache[arn] = _CachedCredential(
            credentials=expected_creds,
            fetched_at=time.time(),
        )

        result = await secrets_client.get_credentials(arn)
        assert result == expected_creds

    @pytest.mark.asyncio
    async def test_fetches_fresh_credentials_when_cache_expired(
        self, secrets_client: SecretsClient, sample_secret_response: dict
    ):
        arn = "arn:aws:secretsmanager:eu-west-2:000:secret:test"
        # Put an expired entry in cache
        secrets_client._cache[arn] = _CachedCredential(
            credentials=Credentials(username="old_user", password="old_pass"),
            fetched_at=time.time() - 120,
        )

        mock_client = MagicMock()
        mock_client.get_secret_value.return_value = sample_secret_response
        secrets_client._client = mock_client

        result = await secrets_client.get_credentials(arn)
        assert result.username == "db_user"
        assert result.password == "super_secret_password"
        mock_client.get_secret_value.assert_called_once_with(SecretId=arn)

    @pytest.mark.asyncio
    async def test_fetches_credentials_when_no_cache(
        self, secrets_client: SecretsClient, sample_secret_response: dict
    ):
        arn = "arn:aws:secretsmanager:eu-west-2:000:secret:test"

        mock_client = MagicMock()
        mock_client.get_secret_value.return_value = sample_secret_response
        secrets_client._client = mock_client

        result = await secrets_client.get_credentials(arn)
        assert result.username == "db_user"
        assert result.host == "localhost"
        assert result.port == 5432


class TestRefreshCredentials:
    """Tests for the refresh_credentials method."""

    @pytest.mark.asyncio
    async def test_successful_refresh_updates_cache(
        self, secrets_client: SecretsClient, sample_secret_response: dict
    ):
        arn = "arn:aws:secretsmanager:eu-west-2:000:secret:test"

        mock_client = MagicMock()
        mock_client.get_secret_value.return_value = sample_secret_response
        secrets_client._client = mock_client

        result = await secrets_client.refresh_credentials(arn)
        assert result.username == "db_user"
        assert arn in secrets_client._cache
        assert secrets_client._cache[arn].credentials == result

    @pytest.mark.asyncio
    async def test_refresh_preserves_previous_credentials(
        self, secrets_client: SecretsClient, sample_secret_response: dict
    ):
        arn = "arn:aws:secretsmanager:eu-west-2:000:secret:test"
        old_creds = Credentials(username="old", password="old_pass")
        secrets_client._cache[arn] = _CachedCredential(
            credentials=old_creds,
            fetched_at=time.time() - 120,
        )

        mock_client = MagicMock()
        mock_client.get_secret_value.return_value = sample_secret_response
        secrets_client._client = mock_client

        await secrets_client.refresh_credentials(arn)
        # Previous credentials should be stored for fallback
        assert secrets_client._previous[arn] == old_creds

    @pytest.mark.asyncio
    async def test_refresh_failure_falls_back_to_previous(
        self, secrets_client: SecretsClient
    ):
        arn = "arn:aws:secretsmanager:eu-west-2:000:secret:test"
        previous_creds = Credentials(username="prev", password="prev_pass")
        secrets_client._previous[arn] = previous_creds

        mock_client = MagicMock()
        mock_client.get_secret_value.side_effect = Exception("Rotation in progress")
        secrets_client._client = mock_client

        result = await secrets_client.refresh_credentials(arn)
        assert result == previous_creds

    @pytest.mark.asyncio
    async def test_refresh_failure_falls_back_to_expired_cache(
        self, secrets_client: SecretsClient
    ):
        arn = "arn:aws:secretsmanager:eu-west-2:000:secret:test"
        cached_creds = Credentials(username="cached", password="cached_pass")
        secrets_client._cache[arn] = _CachedCredential(
            credentials=cached_creds,
            fetched_at=time.time() - 120,  # expired
        )

        mock_client = MagicMock()
        mock_client.get_secret_value.side_effect = Exception("Service unavailable")
        secrets_client._client = mock_client

        result = await secrets_client.refresh_credentials(arn)
        assert result == cached_creds

    @pytest.mark.asyncio
    async def test_refresh_failure_raises_when_no_fallback(
        self, secrets_client: SecretsClient
    ):
        arn = "arn:aws:secretsmanager:eu-west-2:000:secret:test"

        mock_client = MagicMock()
        mock_client.get_secret_value.side_effect = Exception("No access")
        secrets_client._client = mock_client

        with pytest.raises(Exception, match="No access"):
            await secrets_client.refresh_credentials(arn)


class TestDefaultTTL:
    """Test the default TTL value matches the 30-day rotation schedule."""

    def test_default_ttl_is_30_days(self):
        client = SecretsClient()
        assert client.cache_ttl_seconds == 86400 * 30  # 30 days in seconds
