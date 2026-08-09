"""Authentication router with user registration and login endpoints.

Provides POST /auth/register and POST /auth/login endpoints.
Wires Cognito integration for token exchange — uses LocalStack in local dev.
"""

from __future__ import annotations

import logging
from typing import Annotated

import boto3
from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

from app.config import Settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Request/Response schemas
# ---------------------------------------------------------------------------


class RegisterRequest(BaseModel):
    """User registration request payload."""

    email: EmailStr = Field(max_length=255, description="User email address")
    password: str = Field(
        min_length=12,
        max_length=128,
        description="Password (min 12 chars, must include uppercase, lowercase, number, symbol)",
    )
    full_name: str = Field(min_length=1, max_length=255, description="Full name")


class RegisterResponse(BaseModel):
    """User registration response."""

    message: str
    user_sub: str
    email: str


class LoginRequest(BaseModel):
    """User login request payload."""

    email: EmailStr = Field(max_length=255, description="User email address")
    password: str = Field(min_length=1, max_length=128, description="User password")


class LoginResponse(BaseModel):
    """Login response with tokens."""

    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_settings(request: Request) -> Settings:
    """Extract settings from application state."""
    return request.app.state.settings


def _get_cognito_client(settings: Settings):
    """Create a Cognito Identity Provider client.

    Uses LocalStack endpoint in local development.
    """
    kwargs = {
        "service_name": "cognito-idp",
        "region_name": settings.cognito_region,
    }
    if settings.is_local and settings.aws_endpoint_url:
        kwargs["endpoint_url"] = settings.aws_endpoint_url
        kwargs["aws_access_key_id"] = settings.aws_access_key_id or "test"
        kwargs["aws_secret_access_key"] = settings.aws_secret_access_key or "test"
    return boto3.client(**kwargs)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/register", response_model=RegisterResponse, status_code=201)
async def register(
    body: RegisterRequest,
    settings: Annotated[Settings, Depends(_get_settings)],
) -> RegisterResponse:
    """Register a new user via Cognito.

    Creates the user in the Cognito user pool with email as the username.
    In local development this hits the LocalStack Cognito emulation.
    """
    client = _get_cognito_client(settings)

    try:
        response = client.sign_up(
            ClientId=settings.cognito_client_id,
            Username=body.email,
            Password=body.password,
            UserAttributes=[
                {"Name": "email", "Value": body.email},
                {"Name": "name", "Value": body.full_name},
            ],
        )
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]

        if error_code == "UsernameExistsException":
            raise HTTPException(
                status_code=409,
                detail={
                    "error_code": "USER_EXISTS",
                    "message": "A user with this email already exists",
                },
            )
        elif error_code == "InvalidPasswordException":
            raise HTTPException(
                status_code=422,
                detail={
                    "error_code": "INVALID_PASSWORD",
                    "message": error_message,
                },
            )
        elif error_code == "InvalidParameterException":
            raise HTTPException(
                status_code=422,
                detail={
                    "error_code": "INVALID_PARAMETER",
                    "message": error_message,
                },
            )
        else:
            logger.error(
                "Cognito sign_up failed",
                extra={"error_code": error_code, "message": error_message},
            )
            raise HTTPException(
                status_code=500,
                detail={
                    "error_code": "REGISTRATION_FAILED",
                    "message": "An unexpected error occurred during registration",
                },
            )

    user_sub = response.get("UserSub", "")

    # In local dev, auto-confirm the user for convenience
    if settings.is_local:
        try:
            client.admin_confirm_sign_up(
                UserPoolId=settings.cognito_user_pool_id,
                Username=body.email,
            )
        except ClientError:
            logger.warning("Auto-confirm failed in local mode — user may need manual confirmation")

    return RegisterResponse(
        message="User registered successfully",
        user_sub=user_sub,
        email=body.email,
    )


@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    settings: Annotated[Settings, Depends(_get_settings)],
) -> LoginResponse:
    """Authenticate a user and return tokens via Cognito.

    Uses USER_PASSWORD_AUTH flow for simplicity in the demo.
    In production, Authorization Code flow with PKCE is preferred.
    """
    client = _get_cognito_client(settings)

    try:
        response = client.initiate_auth(
            ClientId=settings.cognito_client_id,
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={
                "USERNAME": body.email,
                "PASSWORD": body.password,
            },
        )
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]

        if error_code in ("NotAuthorizedException", "UserNotFoundException"):
            raise HTTPException(
                status_code=401,
                detail={
                    "error_code": "INVALID_CREDENTIALS",
                    "message": "Invalid email or password",
                },
            )
        elif error_code == "UserNotConfirmedException":
            raise HTTPException(
                status_code=403,
                detail={
                    "error_code": "USER_NOT_CONFIRMED",
                    "message": "User email has not been confirmed",
                },
            )
        else:
            logger.error(
                "Cognito initiate_auth failed",
                extra={"error_code": error_code, "message": error_message},
            )
            raise HTTPException(
                status_code=500,
                detail={
                    "error_code": "LOGIN_FAILED",
                    "message": "An unexpected error occurred during login",
                },
            )

    auth_result = response.get("AuthenticationResult", {})

    access_token = auth_result.get("AccessToken", "")
    refresh_token = auth_result.get("RefreshToken", "")
    expires_in = auth_result.get("ExpiresIn", 3600)

    if not access_token:
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": "TOKEN_ERROR",
                "message": "Failed to obtain access token",
            },
        )

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="Bearer",
        expires_in=expires_in,
    )
