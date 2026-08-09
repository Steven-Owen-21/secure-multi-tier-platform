"""JWT token validation and role-based access control service.

Validates JWT tokens issued by AWS Cognito against the JWKS endpoint,
checks expiry and audience claims, and enforces role-based permissions.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import httpx
from jose import JWTError, jwk, jwt
from jose.utils import base64url_decode


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TokenClaims:
    """Validated claims extracted from a JWT access token."""

    sub: str
    email: str
    groups: list[str] = field(default_factory=list)
    exp: int = 0
    iss: str = ""
    client_id: str = ""
    token_use: str = ""


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class AuthError(Exception):
    """Base authentication/authorization error."""

    def __init__(self, detail: str, status_code: int = 401) -> None:
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


class TokenExpiredError(AuthError):
    """Raised when the token has expired."""

    def __init__(self) -> None:
        super().__init__("Token has expired", status_code=401)


class InvalidTokenError(AuthError):
    """Raised when the token is structurally invalid or signature fails."""

    def __init__(self, detail: str = "Invalid token") -> None:
        super().__init__(detail, status_code=401)


class InsufficientPermissionsError(AuthError):
    """Raised when the user lacks required permissions."""

    def __init__(self, detail: str = "Insufficient permissions") -> None:
        super().__init__(detail, status_code=403)


# ---------------------------------------------------------------------------
# Permission model
# ---------------------------------------------------------------------------

# Role → set of allowed actions per resource type.
# admin: full access (read, write, delete)
# manager: read + write
# viewer: read only
ROLE_PERMISSIONS: dict[str, set[str]] = {
    "admin": {"read", "write", "delete"},
    "manager": {"read", "write"},
    "viewer": {"read"},
}


# ---------------------------------------------------------------------------
# JWKS cache
# ---------------------------------------------------------------------------


class JWKSCache:
    """In-memory cache for Cognito JWKS keys with TTL-based expiry."""

    def __init__(self, ttl_seconds: int = 3600) -> None:
        self._keys: list[dict[str, Any]] = []
        self._fetched_at: float = 0.0
        self._ttl = ttl_seconds

    @property
    def is_expired(self) -> bool:
        """Check if the cached keys have expired."""
        return (time.time() - self._fetched_at) >= self._ttl

    @property
    def keys(self) -> list[dict[str, Any]]:
        """Return the cached JWKS keys."""
        return self._keys

    def update(self, keys: list[dict[str, Any]]) -> None:
        """Update the cached keys and reset the TTL timer."""
        self._keys = keys
        self._fetched_at = time.time()


# ---------------------------------------------------------------------------
# AuthService
# ---------------------------------------------------------------------------


class AuthService:
    """JWT validation and role-based permission checking service.

    Validates tokens by:
    1. Fetching and caching JWKS keys from the Cognito endpoint
    2. Verifying the token signature against the matching key
    3. Checking token expiry
    4. Confirming the audience (client_id) claim matches the configured client

    Checks permissions by:
    - Mapping the user's Cognito group membership to role permissions
    - Verifying the requested action is permitted for the user's highest role
    """

    def __init__(
        self,
        jwks_url: str,
        client_id: str,
        user_pool_id: str,
        region: str = "eu-west-2",
        jwks_ttl: int = 3600,
    ) -> None:
        self._jwks_url = jwks_url
        self._client_id = client_id
        self._user_pool_id = user_pool_id
        self._region = region
        self._jwks_cache = JWKSCache(ttl_seconds=jwks_ttl)
        self._issuer = f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}"

    async def _fetch_jwks(self) -> list[dict[str, Any]]:
        """Fetch JWKS keys from the Cognito well-known endpoint."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(self._jwks_url)
            response.raise_for_status()
            data = response.json()
            return data.get("keys", [])

    async def _get_signing_keys(self) -> list[dict[str, Any]]:
        """Return JWKS keys, refreshing the cache if expired."""
        if self._jwks_cache.is_expired or not self._jwks_cache.keys:
            keys = await self._fetch_jwks()
            self._jwks_cache.update(keys)
        return self._jwks_cache.keys

    def _find_key_by_kid(
        self, token_headers: dict[str, Any], keys: list[dict[str, Any]]
    ) -> dict[str, Any] | None:
        """Find the JWKS key matching the token's kid header."""
        kid = token_headers.get("kid")
        if not kid:
            return None
        for key in keys:
            if key.get("kid") == kid:
                return key
        return None

    async def validate_token(self, token: str) -> TokenClaims:
        """Validate a JWT token and return extracted claims.

        Raises:
            InvalidTokenError: If token structure, signature, or audience is invalid.
            TokenExpiredError: If the token has expired.
        """
        # Decode headers without verification to find the kid
        try:
            unverified_headers = jwt.get_unverified_headers(token)
        except JWTError as e:
            raise InvalidTokenError(f"Malformed token: {e}")

        # Fetch matching key
        keys = await self._get_signing_keys()
        signing_key = self._find_key_by_kid(unverified_headers, keys)
        if signing_key is None:
            raise InvalidTokenError("Token signing key not found in JWKS")

        # Verify and decode the token
        try:
            payload = jwt.decode(
                token,
                signing_key,
                algorithms=["RS256"],
                audience=self._client_id,
                issuer=self._issuer,
                options={
                    "verify_exp": True,
                    "verify_aud": True,
                    "verify_iss": True,
                },
            )
        except jwt.ExpiredSignatureError:
            raise TokenExpiredError()
        except JWTError as e:
            error_msg = str(e).lower()
            if "expired" in error_msg:
                raise TokenExpiredError()
            raise InvalidTokenError(f"Token verification failed: {e}")

        # Extract claims
        groups = payload.get("cognito:groups", [])
        if isinstance(groups, str):
            groups = [groups]

        return TokenClaims(
            sub=payload.get("sub", ""),
            email=payload.get("email", ""),
            groups=groups,
            exp=payload.get("exp", 0),
            iss=payload.get("iss", ""),
            client_id=payload.get("client_id", payload.get("aud", "")),
            token_use=payload.get("token_use", ""),
        )

    def check_permission(
        self, claims: TokenClaims, resource: str, action: str
    ) -> bool:
        """Check if the user has permission to perform the action on the resource.

        Permission is granted if any of the user's groups/roles includes the
        requested action. The role hierarchy is:
        - admin: read, write, delete
        - manager: read, write
        - viewer: read

        Args:
            claims: Validated token claims containing user groups.
            resource: The resource being accessed (e.g. "products", "orders").
            action: The action being performed ("read", "write", "delete").

        Returns:
            True if the action is permitted, False otherwise.
        """
        action_lower = action.lower()

        for group in claims.groups:
            role = group.lower()
            allowed_actions = ROLE_PERMISSIONS.get(role, set())
            if action_lower in allowed_actions:
                return True

        return False
