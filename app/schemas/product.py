"""Pydantic schemas for Product request/response models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ProductCreate(BaseModel):
    """Schema for creating a new product."""

    name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    price_pence: int = Field(gt=0, le=100_000_00)  # Max £1000
    stock_quantity: int = Field(ge=0)
    category: str = Field(min_length=1, max_length=100)


class ProductUpdate(BaseModel):
    """Schema for updating an existing product. All fields optional."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    price_pence: Optional[int] = Field(None, gt=0, le=100_000_00)
    stock_quantity: Optional[int] = Field(None, ge=0)
    category: Optional[str] = Field(None, min_length=1, max_length=100)
    is_active: Optional[bool] = None


class ProductResponse(BaseModel):
    """Schema for product responses returned from the API."""

    id: uuid.UUID
    name: str
    description: Optional[str]
    price_pence: int
    stock_quantity: int
    category: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ProductListResponse(BaseModel):
    """Paginated list of products."""

    items: list[ProductResponse]
    total: int
    page: int
    page_size: int
