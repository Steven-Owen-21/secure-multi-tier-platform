"""Unit tests for the JWT token validation and permission checking service."""

import time
from unittest.mock import AsyncMock, patch

import pytest
from jose import jwt

from app.services.auth_service import (
    AuthService,
    InsufficientPermissionsError,
    InvalidTokenError,
    ROLE_PERMISSIONS,
    TokenClaims,
    TokenExpiredError,
)


# ---------------------------------------------------------------------------
# Test RSA key pair for signing JWTs in tests
# ---------------------------------------------------------------------------

# Minimal RSA key for testing (do NOT use in production)
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

_private_key = rsa.generate_private_key(
    public_exponent=65537,
    key_size=2048,
    backend=default_backend(),
)
_public_key = _private_key.public_key()

# Export to PEM for python-jose
_private_pem = _private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
)

_public_numbers = _public_key.public_numbers()


def _int_to_base64url(value: int) -> str:
    """Convert an integer to a base64url-encoded string."""
    import base64

    byte_length = (value.bit_length() + 7) // 8
    value_bytes = value.to_bytes(byte_length, byteorder="big")
    return base64.urlsafe_b64encode(value_bytes).rstrip(b"=").decode("ascii")


# JWKS key representation
TEST_KID = "test-key-id-1"
TEST_JWKS_KEY = {
    "kty": "RSA",
    "kid": TEST_KID,
    "use": "sig",
    "alg": "RS256",
    "n": _int_to_base64url(_public_numbers.n),
    "e": _int_to_base64url(_public_numbers.e),
}

TEST_CLIENT_ID = "test-client-id"
TEST_USER_POOL_ID = "eu-west-2_testpool"
TEST_REGION = "eu-west-2"
TEST_ISSUER = f"https://cognito-idp.{TEST_REGION}.amazonaws.com/{TEST_USER_POOL_ID}"
TEST_JWKS_URL = f"http://localhost:4566/{TEST_USER_POOL_ID}/.well-known/jwks.json"


def _create_token(
    sub: str = "user-123",
    email: str = "user@example.com",
    groups: list[str] | None = None,
    exp: int | None = None,
    aud: str | None = None,
    iss: str | None = None,
    kid: str | None = None,
) -> str:
    """Create a signed JWT for testing."""
    now = int(time.time())
    payload = {
        "sub": sub,
        "email": email,
        "cognito:groups": groups or ["viewer"],
        "exp": exp or (now + 3600),
        "iat": now,
        "iss": iss or TEST_ISSUER,
        "aud": aud or TEST_CLIENT_ID,
        "client_id": aud or TEST_CLIENT_ID,
        "token_use": "access",
    }
    headers = {"kid": kid or TEST_KID, "alg": "RS256"}
    return jwt.encode(payload, _private_pem.decode(), algorithm="RS256", headers=headers)


def _make_service() -> AuthService:
    """Create an AuthService configured for testing."""
    return AuthService(
        jwks_url=TEST_JWKS_URL,
        client_id=TEST_CLIENT_ID,
        user_pool_id=TEST_USER_POOL_ID,
        region=TEST_REGION,
    )


# ---------------------------------------------------------------------------
# Token validation tests
# ---------------------------------------------------------------------------


class TestValidateToken:
    """Tests for AuthService.validate_token."""

    @pytest.fixture(autouse=True)
    def _mock_jwks(self):
        """Mock the JWKS fetch to return our test key."""
        with patch.object(
            AuthService,
            "_fetch_jwks",
            new_callable=AsyncMock,
            return_value=[TEST_JWKS_KEY],
        ):
            yield

    @pytest.mark.asyncio
    async def test_valid_token_returns_claims(self):
        """A correctly signed, non-expired token returns TokenClaims."""
        service = _make_service()
        token = _create_token(
            sub="user-abc", email="alice@test.com", groups=["admin"]
        )

        claims = await service.validate_token(token)

        assert claims.sub == "user-abc"
        assert claims.email == "alice@test.com"
        assert "admin" in claims.groups

    @pytest.mark.asyncio
    async def test_valid_token_multiple_groups(self):
        """Token with multiple groups is parsed correctly."""
        service = _make_service()
        token = _create_token(groups=["admin", "manager"])

        claims = await service.validate_token(token)

        assert "admin" in claims.groups
        assert "manager" in claims.groups

    @pytest.mark.asyncio
    async def test_expired_token_raises_error(self):
        """An expired token raises TokenExpiredError."""
        service = _make_service()
        expired_time = int(time.time()) - 3600
        token = _create_token(exp=expired_time)

        with pytest.raises(TokenExpiredError):
            await service.validate_token(token)

    @pytest.mark.asyncio
    async def test_wrong_audience_raises_error(self):
        """A token with wrong audience raises InvalidTokenError."""
        service = _make_service()
        token = _create_token(aud="wrong-client-id")

        with pytest.raises(InvalidTokenError):
            await service.validate_token(token)

    @pytest.mark.asyncio
    async def test_wrong_issuer_raises_error(self):
        """A token with wrong issuer raises InvalidTokenError."""
        service = _make_service()
        token = _create_token(iss="https://evil.example.com")

        with pytest.raises(InvalidTokenError):
            await service.validate_token(token)

    @pytest.mark.asyncio
    async def test_unknown_kid_raises_error(self):
        """A token signed with an unknown key ID raises InvalidTokenError."""
        service = _make_service()
        token = _create_token(kid="unknown-key-id")

        with pytest.raises(InvalidTokenError):
            await service.validate_token(token)

    @pytest.mark.asyncio
    async def test_malformed_token_raises_error(self):
        """A structurally invalid token raises InvalidTokenError."""
        service = _make_service()

        with pytest.raises(InvalidTokenError):
            await service.validate_token("not.a.valid.token")

    @pytest.mark.asyncio
    async def test_empty_token_raises_error(self):
        """An empty string raises InvalidTokenError."""
        service = _make_service()

        with pytest.raises(InvalidTokenError):
            await service.validate_token("")


# ---------------------------------------------------------------------------
# Permission checking tests
# ---------------------------------------------------------------------------


class TestCheckPermission:
    """Tests for AuthService.check_permission."""

    def _make_claims(self, groups: list[str]) -> TokenClaims:
        """Create TokenClaims with specified groups."""
        return TokenClaims(
            sub="user-123",
            email="user@test.com",
            groups=groups,
            exp=int(time.time()) + 3600,
            iss=TEST_ISSUER,
            client_id=TEST_CLIENT_ID,
            token_use="access",
        )

    def test_admin_has_full_access(self):
        """Admin role can read, write, and delete any resource."""
        service = _make_service()
        claims = self._make_claims(["admin"])

        assert service.check_permission(claims, "products", "read") is True
        assert service.check_permission(claims, "products", "write") is True
        assert service.check_permission(claims, "products", "delete") is True
        assert service.check_permission(claims, "orders", "read") is True
        assert service.check_permission(claims, "orders", "write") is True
        assert service.check_permission(claims, "orders", "delete") is True

    def test_manager_has_read_write(self):
        """Manager role can read and write but not delete."""
        service = _make_service()
        claims = self._make_claims(["manager"])

        assert service.check_permission(claims, "products", "read") is True
        assert service.check_permission(claims, "products", "write") is True
        assert service.check_permission(claims, "products", "delete") is False

    def test_viewer_has_read_only(self):
        """Viewer role can only read."""
        service = _make_service()
        claims = self._make_claims(["viewer"])

        assert service.check_permission(claims, "products", "read") is True
        assert service.check_permission(claims, "products", "write") is False
        assert service.check_permission(claims, "products", "delete") is False

    def test_no_groups_denies_all(self):
        """User with no groups is denied all actions."""
        service = _make_service()
        claims = self._make_claims([])

        assert service.check_permission(claims, "products", "read") is False
        assert service.check_permission(claims, "products", "write") is False
        assert service.check_permission(claims, "products", "delete") is False

    def test_unknown_role_denies_all(self):
        """An unrecognised group/role is denied all actions."""
        service = _make_service()
        claims = self._make_claims(["unknown_role"])

        assert service.check_permission(claims, "products", "read") is False
        assert service.check_permission(claims, "products", "write") is False

    def test_multiple_roles_uses_highest_privilege(self):
        """If a user has multiple roles, the most permissive one applies."""
        service = _make_service()
        claims = self._make_claims(["viewer", "manager"])

        # Manager grants write
        assert service.check_permission(claims, "products", "write") is True
        # Neither viewer nor manager grants delete
        assert service.check_permission(claims, "products", "delete") is False

    def test_action_case_insensitive(self):
        """Action matching is case-insensitive."""
        service = _make_service()
        claims = self._make_claims(["admin"])

        assert service.check_permission(claims, "products", "READ") is True
        assert service.check_permission(claims, "products", "Write") is True
        assert service.check_permission(claims, "products", "DELETE") is True

    def test_permission_applies_to_any_resource(self):
        """Permissions apply regardless of resource type."""
        service = _make_service()
        claims = self._make_claims(["viewer"])

        assert service.check_permission(claims, "products", "read") is True
        assert service.check_permission(claims, "orders", "read") is True
        assert service.check_permission(claims, "users", "read") is True
