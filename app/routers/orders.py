"""Orders router — POST /orders, GET /orders, GET /orders/{id}.

Handles order creation with stock validation, order listing for the
authenticated user, and individual order retrieval. Applies role-based
access control via the AuthService dependency.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.dependencies import Auth, DBSession
from app.models.order import Order, OrderItem
from app.models.product import Product
from app.schemas.order import OrderCreate, OrderResponse
from app.services.auth_service import (
    AuthError,
    InsufficientPermissionsError,
    TokenClaims,
)

router = APIRouter(prefix="/orders", tags=["orders"])


# ---------------------------------------------------------------------------
# Auth helper — extracts and validates the Bearer token, checks permissions
# ---------------------------------------------------------------------------


async def _get_current_user(
    auth_service: Auth,
    authorization: Annotated[str | None, Header()] = None,
) -> TokenClaims:
    """Extract and validate Bearer token from the Authorization header."""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "missing_token", "message": "Authorization header required"},
        )

    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "invalid_scheme", "message": "Bearer token required"},
        )

    token = parts[1]
    try:
        claims = await auth_service.validate_token(token)
    except AuthError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"error": "auth_error", "message": exc.detail},
        )

    return claims


CurrentUser = Annotated[TokenClaims, Depends(_get_current_user)]


def _require_permission(claims: TokenClaims, auth_service_instance: object, action: str) -> None:
    """Raise 403 if user lacks the required permission on the orders resource."""
    # We use the AuthService.check_permission logic inline since we have claims
    from app.services.auth_service import ROLE_PERMISSIONS

    action_lower = action.lower()
    for group in claims.groups:
        role = group.lower()
        allowed_actions = ROLE_PERMISSIONS.get(role, set())
        if action_lower in allowed_actions:
            return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "error": "insufficient_permissions",
            "message": f"Permission denied: requires '{action}' access on orders",
        },
    )


# ---------------------------------------------------------------------------
# POST /orders — create a new order with stock validation
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new order",
    description="Creates an order after validating stock availability for all items.",
)
async def create_order(
    order_in: OrderCreate,
    current_user: CurrentUser,
    db: DBSession,
    auth_service: Auth,
) -> Order:
    """Create an order, computing total from product prices and validating stock."""
    # Require write permission
    _require_permission(current_user, auth_service, "write")

    # Gather unique product IDs from the order request
    product_ids = [item.product_id for item in order_in.items]

    # Fetch products from the database
    result = await db.execute(
        select(Product).where(Product.id.in_(product_ids))
    )
    products = {p.id: p for p in result.scalars().all()}

    # Validate all products exist
    missing = [str(pid) for pid in product_ids if pid not in products]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "product_not_found",
                "message": f"Products not found: {', '.join(missing)}",
            },
        )

    # Validate stock availability for each item
    insufficient_stock: list[dict[str, object]] = []
    for item in order_in.items:
        product = products[item.product_id]
        if product.stock_quantity < item.quantity:
            insufficient_stock.append(
                {
                    "product_id": str(item.product_id),
                    "requested": item.quantity,
                    "available": product.stock_quantity,
                }
            )

    if insufficient_stock:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "insufficient_stock",
                "message": "Insufficient stock for one or more products",
                "items": insufficient_stock,
            },
        )

    # Calculate order total: sum(item.quantity * product.price_pence)
    total_pence = sum(
        item.quantity * products[item.product_id].price_pence
        for item in order_in.items
    )

    # Create the order
    # Use the cognito sub as user_id (parsed as UUID)
    try:
        user_id = uuid.UUID(current_user.sub)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_user", "message": "Invalid user identifier in token"},
        )

    order = Order(
        user_id=user_id,
        status="pending",
        total_pence=total_pence,
    )
    db.add(order)
    await db.flush()  # Assign the order ID before creating items

    # Create order items and decrement stock
    for item in order_in.items:
        product = products[item.product_id]
        order_item = OrderItem(
            order_id=order.id,
            product_id=item.product_id,
            quantity=item.quantity,
            unit_price_pence=product.price_pence,
        )
        db.add(order_item)

        # Decrement stock
        product.stock_quantity -= item.quantity

    # Flush to populate relationships for the response
    await db.flush()

    # Eagerly load items for the response
    result = await db.execute(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.id == order.id)
    )
    order = result.scalar_one()

    return order


# ---------------------------------------------------------------------------
# GET /orders — list the current user's orders
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=list[OrderResponse],
    summary="List user's orders",
    description="Returns all orders for the authenticated user.",
)
async def list_orders(
    current_user: CurrentUser,
    db: DBSession,
    auth_service: Auth,
) -> list[Order]:
    """Return all orders belonging to the authenticated user."""
    # Require read permission
    _require_permission(current_user, auth_service, "read")

    try:
        user_id = uuid.UUID(current_user.sub)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_user", "message": "Invalid user identifier in token"},
        )

    result = await db.execute(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.user_id == user_id)
        .order_by(Order.created_at.desc())
    )
    orders = result.scalars().all()
    return list(orders)


# ---------------------------------------------------------------------------
# GET /orders/{order_id} — get a single order by ID
# ---------------------------------------------------------------------------


@router.get(
    "/{order_id}",
    response_model=OrderResponse,
    summary="Get order by ID",
    description="Returns a specific order if it belongs to the authenticated user.",
)
async def get_order(
    order_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
    auth_service: Auth,
) -> Order:
    """Return a single order by ID, scoped to the authenticated user."""
    # Require read permission
    _require_permission(current_user, auth_service, "read")

    try:
        user_id = uuid.UUID(current_user.sub)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_user", "message": "Invalid user identifier in token"},
        )

    result = await db.execute(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.id == order_id, Order.user_id == user_id)
    )
    order = result.scalar_one_or_none()

    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "order_not_found", "message": "Order not found"},
        )

    return order
