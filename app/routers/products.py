"""Products CRUD router with cache-aside pattern and role-based access control.

Implements:
- GET /products — list with pagination and category filtering (cached)
- GET /products/{id} — single product detail (cached)
- POST /products — create a new product (admin/manager)
- PUT /products/{id} — update a product (admin/manager)
- DELETE /products/{id} — soft-delete a product (admin only)

Cache keys follow the schema:
- cache:products:list:{hash(sort_by, category, page, page_size)}
- cache:products:detail:{product_id}
"""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import CacheClient, DBSession, Auth
from app.models.product import Product
from app.schemas.product import (
    ProductCreate,
    ProductListResponse,
    ProductResponse,
    ProductUpdate,
)
from app.services.auth_service import (
    AuthError,
    AuthService,
    InsufficientPermissionsError,
    TokenClaims,
)
from app.services.cache_service import CacheService

router = APIRouter(prefix="/products", tags=["products"])


# ---------------------------------------------------------------------------
# Auth dependency helpers
# ---------------------------------------------------------------------------


async def _extract_claims(
    auth_service: AuthService, authorization: str | None
) -> TokenClaims:
    """Validate the Authorization header and return token claims.

    Raises HTTPException 401 if the token is missing or invalid.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = authorization.removeprefix("Bearer ")
    try:
        return await auth_service.validate_token(token)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


def _require_permission(claims: TokenClaims, auth_service: AuthService, action: str) -> None:
    """Check permission for 'products' resource; raise 403 if denied."""
    if not auth_service.check_permission(claims, "products", action):
        raise HTTPException(status_code=403, detail="Insufficient permissions")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=ProductListResponse,
    summary="List products with pagination and optional category filter",
)
async def list_products(
    db: DBSession,
    cache: CacheClient,
    auth_service: Auth,
    authorization: Optional[str] = Header(None),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    category: Optional[str] = Query(None, description="Filter by category"),
    sort_by: str = Query("created_at", description="Sort field"),
) -> ProductListResponse:
    """GET /products — paginated product listing with cache-aside pattern."""
    # Auth: read permission required
    claims = await _extract_claims(auth_service, authorization)
    _require_permission(claims, auth_service, "read")

    # Build cache key
    cache_svc = CacheService(cache)
    cache_key = cache_svc.generate_key(
        "products:list",
        {"sort_by": sort_by, "category": category or "", "page": page, "page_size": page_size},
    )

    # Try cache first
    cached = await cache_svc.get(cache_key)
    if cached is not None:
        return ProductListResponse(**cached)

    # Cache miss — query database
    query = select(Product).where(Product.is_active == True)  # noqa: E712
    count_query = select(func.count()).select_from(Product).where(Product.is_active == True)  # noqa: E712

    if category:
        query = query.where(Product.category == category)
        count_query = count_query.where(Product.category == category)

    # Sorting
    sort_column = getattr(Product, sort_by, Product.created_at)
    query = query.order_by(sort_column.desc())

    # Pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await db.execute(query)
    products = result.scalars().all()

    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    response = ProductListResponse(
        items=[ProductResponse.model_validate(p) for p in products],
        total=total,
        page=page,
        page_size=page_size,
    )

    # Cache the result
    await cache_svc.set(cache_key, response.model_dump(mode="json"), ttl=60)

    return response


@router.get(
    "/{product_id}",
    response_model=ProductResponse,
    summary="Get a single product by ID",
)
async def get_product(
    product_id: uuid.UUID,
    db: DBSession,
    cache: CacheClient,
    auth_service: Auth,
    authorization: Optional[str] = Header(None),
) -> ProductResponse:
    """GET /products/{id} — single product with cache-aside pattern."""
    # Auth: read permission required
    claims = await _extract_claims(auth_service, authorization)
    _require_permission(claims, auth_service, "read")

    # Cache key for detail view
    cache_svc = CacheService(cache)
    cache_key = f"cache:products:detail:{product_id}"

    # Try cache first
    cached = await cache_svc.get(cache_key)
    if cached is not None:
        return ProductResponse(**cached)

    # Cache miss — query database
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()

    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    response = ProductResponse.model_validate(product)

    # Cache the result
    await cache_svc.set(cache_key, response.model_dump(mode="json"), ttl=300)

    return response


@router.post(
    "",
    response_model=ProductResponse,
    status_code=201,
    summary="Create a new product",
)
async def create_product(
    body: ProductCreate,
    db: DBSession,
    cache: CacheClient,
    auth_service: Auth,
    authorization: Optional[str] = Header(None),
) -> ProductResponse:
    """POST /products — create a product (admin/manager only)."""
    # Auth: write permission required
    claims = await _extract_claims(auth_service, authorization)
    _require_permission(claims, auth_service, "write")

    product = Product(
        name=body.name,
        description=body.description,
        price_pence=body.price_pence,
        stock_quantity=body.stock_quantity,
        category=body.category,
    )
    db.add(product)
    await db.flush()
    await db.refresh(product)

    # Invalidate list caches on write
    cache_svc = CacheService(cache)
    await cache_svc.invalidate("cache:products:list:*")

    return ProductResponse.model_validate(product)


@router.put(
    "/{product_id}",
    response_model=ProductResponse,
    summary="Update a product",
)
async def update_product(
    product_id: uuid.UUID,
    body: ProductUpdate,
    db: DBSession,
    cache: CacheClient,
    auth_service: Auth,
    authorization: Optional[str] = Header(None),
) -> ProductResponse:
    """PUT /products/{id} — update a product (admin/manager only)."""
    # Auth: write permission required
    claims = await _extract_claims(auth_service, authorization)
    _require_permission(claims, auth_service, "write")

    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()

    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    # Apply updates for provided fields only
    update_data = body.model_dump(exclude_unset=True)
    for field_name, value in update_data.items():
        setattr(product, field_name, value)

    await db.flush()
    await db.refresh(product)

    # Invalidate caches: both list and this product's detail
    cache_svc = CacheService(cache)
    await cache_svc.invalidate("cache:products:list:*")
    await cache_svc.invalidate(f"cache:products:detail:{product_id}")

    return ProductResponse.model_validate(product)


@router.delete(
    "/{product_id}",
    status_code=204,
    summary="Delete (soft-delete) a product",
)
async def delete_product(
    product_id: uuid.UUID,
    db: DBSession,
    cache: CacheClient,
    auth_service: Auth,
    authorization: Optional[str] = Header(None),
) -> None:
    """DELETE /products/{id} — soft-delete a product (admin only)."""
    # Auth: delete permission required
    claims = await _extract_claims(auth_service, authorization)
    _require_permission(claims, auth_service, "delete")

    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()

    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    # Soft delete: mark inactive
    product.is_active = False
    await db.flush()

    # Invalidate caches
    cache_svc = CacheService(cache)
    await cache_svc.invalidate("cache:products:list:*")
    await cache_svc.invalidate(f"cache:products:detail:{product_id}")
