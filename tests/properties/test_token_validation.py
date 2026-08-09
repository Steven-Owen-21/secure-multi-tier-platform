"""Property-based tests for JWT token validation logic.

**Validates: Requirements 5.8**

Uses Hypothesis to generate structurally valid JWTs and tokens with invalid
signatures, expired timestamps, or incorrect audience claims. Verifies that
valid tokens are accepted and all invalid token variants are correctly rejected.
"""

from __future__ import annotations

import time
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from hypothesis import given, settings, strategies as st
from jose import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

from app.services.auth_service import (
    AuthService,
    InvalidTokenError,
    TokenClaims,
    TokenExpiredError,
)


# ---------------------------------------------------------------------------
# RSA key pair generation helpers
# ---------------------------------------------------------------------------


def generate_rsa_key_pair():
    """Generate a fresh RSA key pair for test JWT signing."""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend(),
    )
    public_key = private_key.public_key()
    return private_key, public_key


def private_key_to_pem(private_key) -> str:
    """Serialize RSA private key to PEM string."""
    return private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")


def public_key_to_jwk(public_key, kid: str = "test-kid-1") -> dict:
    """Convert RSA public key to JWK format compatible with python-jose."""
    from jose.utils import long_to_base64
    from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicNumbers

    pub_numbers: RSAPublicNumbers = public_key.public_numbers()
    return {
        "kty": "RSA",
        "kid": kid,
        "use": "sig",
        "alg": "RS256",
        "n": long_to_base64(pub_numbers.n).decode("utf-8"),
        "e": long_to_base64(pub_numbers.e).decode("utf-8"),
    }


# ---------------------------------------------------------------------------
# Test fixtures - module-level key pairs (generated once for performance)
# ---------------------------------------------------------------------------

# Primary key pair used for signing valid tokens
_PRIMARY_PRIVATE_KEY, _PRIMARY_PUBLIC_KEY = generate_rsa_key_pair()
_PRIMARY_PEM = private_key_to_pem(_PRIMARY_PRIVATE_KEY)
_PRIMARY_JWK = public_key_to_jwk(_PRIMARY_PUBLIC_KEY, kid="test-kid-1")

# Secondary key pair used for simulating invalid signatures
_WRONG_PRIVATE_KEY, _WRONG_PUBLIC_KEY = generate_rsa_key_pair()
_WRONG_PEM = private_key_to_pem(_WRONG_PRIVATE_KEY)

# Test configuration
_TEST_CLIENT_ID = "test-client-id-12345"
_TEST_USER_POOL_ID = "eu-west-2_TestPool1"
_TEST_REGION = "eu-west-2"
_TEST_ISSUER = f"https://cognito-idp.{_TEST_REGION}.amazonaws.com/{_TEST_USER_POOL_ID}"
_TEST_JWKS_URL = f"{_TEST_ISSUER}/.well-known/jwks.json"


# ---------------------------------------------------------------------------
# Helper to create AuthService with mocked JWKS fetching
# ---------------------------------------------------------------------------


def create_test_auth_service() -> AuthService:
    """Create an AuthService configured for testing with known JWKS keys."""
    service = AuthService(
        jwks_url=_TEST_JWKS_URL,
        client_id=_TEST_CLIENT_ID,
        user_pool_id=_TEST_USER_POOL_ID,
        region=_TEST_REGION,
    )
    # Pre-populate the JWKS cache so we don't need real HTTP calls
    service._jwks_cache.update([_PRIMARY_JWK])
    return service


def create_valid_token(
    sub: str = "user-123",
    email: str = "user@example.com",
    groups: list[str] | None = None,
    exp_offset: int = 3600,
    audience: str | None = None,
    issuer: str | None = None,
    kid: str = "test-kid-1",
    private_key_pem: str | None = None,
) -> str:
    """Create a JWT token with configurable claims."""
    now = int(time.time())
    payload = {
        "sub": sub,
        "email": email,
        "cognito:groups": groups or ["viewer"],
        "exp": now + exp_offset,
        "iat": now,
        "iss": issuer or _TEST_ISSUER,
        "client_id": audience or _TEST_CLIENT_ID,
        "aud": audience or _TEST_CLIENT_ID,
        "token_use": "access",
    }
    headers = {"kid": kid, "alg": "RS256"}
    key = private_key_pem or _PRIMARY_PEM
    return jwt.encode(payload, key, algorithm="RS256", headers=headers)


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

# Valid user subject IDs
sub_strategy = st.text(
    min_size=1,
    max_size=64,
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_"),
)

# Valid email-like strings
email_strategy = st.emails()

# Valid Cognito group names
group_strategy = st.lists(
    st.sampled_from(["admin", "manager", "viewer"]),
    min_size=1,
    max_size=3,
    unique=True,
)

# Token expiry offsets - positive values mean token is still valid
valid_exp_offset = st.integers(min_value=60, max_value=7200)

# Token expiry offsets - negative values mean token is expired
expired_exp_offset = st.integers(min_value=-86400, max_value=-1)

# Wrong audience strings that don't match the configured client ID
wrong_audience_strategy = st.text(
    min_size=5,
    max_size=50,
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_"),
).filter(lambda x: x != _TEST_CLIENT_ID)


# ---------------------------------------------------------------------------
# Property tests: Valid tokens are accepted
# ---------------------------------------------------------------------------


@pytest.mark.property
@settings(max_examples=100)
@given(
    sub=sub_strategy,
    email=email_strategy,
    groups=group_strategy,
    exp_offset=valid_exp_offset,
)
@pytest.mark.asyncio
async def test_valid_tokens_are_accepted(
    sub: str, email: str, groups: list[str], exp_offset: int
):
    """Property: structurally valid JWTs signed with the correct key are accepted.

    For any valid combination of subject, email, groups, and non-expired
    timestamp, validate_token must return TokenClaims with the correct values.

    **Validates: Requirements 5.8**
    """
    service = create_test_auth_service()
    token = create_valid_token(
        sub=sub,
        email=email,
        groups=groups,
        exp_offset=exp_offset,
    )

    claims = await service.validate_token(token)

    assert isinstance(claims, TokenClaims)
    assert claims.sub == sub
    assert claims.email == email
    assert set(claims.groups) == set(groups)


# ---------------------------------------------------------------------------
# Property tests: Expired tokens are rejected
# ---------------------------------------------------------------------------


@pytest.mark.property
@settings(max_examples=100)
@given(
    sub=sub_strategy,
    email=email_strategy,
    groups=group_strategy,
    exp_offset=expired_exp_offset,
)
@pytest.mark.asyncio
async def test_expired_tokens_are_rejected(
    sub: str, email: str, groups: list[str], exp_offset: int
):
    """Property: tokens with expired timestamps are rejected with TokenExpiredError.

    For any valid token structure where the expiry timestamp is in the past,
    validate_token must raise TokenExpiredError.

    **Validates: Requirements 5.8**
    """
    service = create_test_auth_service()
    token = create_valid_token(
        sub=sub,
        email=email,
        groups=groups,
        exp_offset=exp_offset,
    )

    with pytest.raises(TokenExpiredError):
        await service.validate_token(token)


# ---------------------------------------------------------------------------
# Property tests: Invalid signatures are rejected
# ---------------------------------------------------------------------------


@pytest.mark.property
@settings(max_examples=100)
@given(
    sub=sub_strategy,
    email=email_strategy,
    groups=group_strategy,
    exp_offset=valid_exp_offset,
)
@pytest.mark.asyncio
async def test_invalid_signature_tokens_are_rejected(
    sub: str, email: str, groups: list[str], exp_offset: int
):
    """Property: tokens signed with a wrong key are rejected with InvalidTokenError.

    For any valid token structure signed with a different RSA key than the one
    in the JWKS cache, validate_token must raise InvalidTokenError.

    **Validates: Requirements 5.8**
    """
    service = create_test_auth_service()
    # Sign with the wrong private key but use the correct kid
    token = create_valid_token(
        sub=sub,
        email=email,
        groups=groups,
        exp_offset=exp_offset,
        private_key_pem=_WRONG_PEM,
    )

    with pytest.raises(InvalidTokenError):
        await service.validate_token(token)


# ---------------------------------------------------------------------------
# Property tests: Incorrect audience is rejected
# ---------------------------------------------------------------------------


@pytest.mark.property
@settings(max_examples=100)
@given(
    sub=sub_strategy,
    email=email_strategy,
    groups=group_strategy,
    exp_offset=valid_exp_offset,
    wrong_audience=wrong_audience_strategy,
)
@pytest.mark.asyncio
async def test_wrong_audience_tokens_are_rejected(
    sub: str,
    email: str,
    groups: list[str],
    exp_offset: int,
    wrong_audience: str,
):
    """Property: tokens with incorrect audience claim are rejected with InvalidTokenError.

    For any valid token structure where the audience claim does not match the
    configured client ID, validate_token must raise InvalidTokenError.

    **Validates: Requirements 5.8**
    """
    service = create_test_auth_service()
    token = create_valid_token(
        sub=sub,
        email=email,
        groups=groups,
        exp_offset=exp_offset,
        audience=wrong_audience,
    )

    with pytest.raises(InvalidTokenError):
        await service.validate_token(token)


# ---------------------------------------------------------------------------
# Property tests: Unknown kid is rejected
# ---------------------------------------------------------------------------


@pytest.mark.property
@settings(max_examples=50)
@given(
    sub=sub_strategy,
    email=email_strategy,
    exp_offset=valid_exp_offset,
)
@pytest.mark.asyncio
async def test_unknown_kid_tokens_are_rejected(
    sub: str, email: str, exp_offset: int
):
    """Property: tokens with a kid not present in JWKS are rejected.

    For any valid token structure where the kid header references a key
    not in the cached JWKS, validate_token must raise InvalidTokenError.

    **Validates: Requirements 5.8**
    """
    service = create_test_auth_service()
    token = create_valid_token(
        sub=sub,
        email=email,
        exp_offset=exp_offset,
        kid="unknown-kid-999",
    )

    with pytest.raises(InvalidTokenError):
        await service.validate_token(token)
