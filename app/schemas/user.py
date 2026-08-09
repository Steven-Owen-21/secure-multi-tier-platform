"""Pydantic schemas for User request/response models."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    """Schema for creating a new user."""

    cognito_sub: str = Field(min_length=1, max_length=255)
    email: EmailStr = Field(max_length=255)
    full_name: str = Field(min_length=1, max_length=255)
    role: str = Field(default="viewer", min_length=1, max_length=50)


class UserResponse(BaseModel):
    """Schema for user responses returned from the API."""

    id: uuid.UUID
    cognito_sub: str
    email: str
    full_name: str
    role: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
