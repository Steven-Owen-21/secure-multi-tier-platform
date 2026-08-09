"""Pydantic schemas for Order request/response models."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class OrderItemCreate(BaseModel):
    """Schema for creating an order line item."""

    product_id: uuid.UUID
    quantity: int = Field(gt=0, le=100)


class OrderCreate(BaseModel):
    """Schema for creating a new order."""

    items: list[OrderItemCreate] = Field(min_length=1, max_length=50)


class OrderItemResponse(BaseModel):
    """Schema for order item responses returned from the API."""

    id: uuid.UUID
    product_id: uuid.UUID
    quantity: int
    unit_price_pence: int

    model_config = {"from_attributes": True}


class OrderResponse(BaseModel):
    """Schema for order responses returned from the API."""

    id: uuid.UUID
    user_id: uuid.UUID
    status: str
    total_pence: int
    items: list[OrderItemResponse]
    created_at: datetime

    model_config = {"from_attributes": True}
