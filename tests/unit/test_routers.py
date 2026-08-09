"""Unit tests for API routers: products, orders, and auth.

Tests product CRUD with valid/invalid payloads, auth enforcement, cache integration.
Tests order creation with stock validation and total calculation.
Tests error responses (401, 403, 404, 422).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.dependencies import get_auth_service, get_cache_client, get_db_session
from app.main import create_app
from app.models.order import Order, OrderItem
from app.models.product import Product
from app.services.auth_service import (
    AuthService,
    InvalidTokenError,
    TokenClaims,
    TokenExpiredError,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def settings() -> Settings:
    """Provide test settings for local environment."""
    return Settings(
        environment="local",
        database_url="postgresql+asyncpg://test:test@localhost:5432/test",
        redis_url="redis://localhost:6379/0",
    )


@pytest.fixture
def app(settings: Settings):
    """Create a test FastAPI app with dependency overrides."""
    return create_app(settings=settings)


@pytest.fixture
def mock_db():
    """Provide a mock async DB session."""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.fixture
def mock_cache():
    """Provide a mock Redis cache client."""
    cache = AsyncMock()
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock()
    cache.scan = AsyncMock(return_value=(0, []))
    cache.delete = AsyncMock()
    return cache


@pytest.fixture
def mock_auth_service():
    """Provide a mock AuthService that validates tokens successfully."""
    service = AsyncMock(spec=AuthService)
    service.validate_token = AsyncMock(
        return_value=TokenClaims(
            sub=str(uuid.uuid4()),
            email="test@example.com",
            groups=["admin"],
            exp=9999999999,
            iss="https://cognito-idp.eu-west-2.amazonaws.com/pool-id",
            client_id="test-client",
            token_use="access",
        )
    )
    service.check_permission = MagicMock(return_value=True)
    return service


@pytest.fixture
def viewer_auth_service():
    """Provide a mock AuthService with viewer role (read-only)."""
    service = AsyncMock(spec=AuthService)
    service.validate_token = AsyncMock(
        return_value=TokenClaims(
            sub=str(uuid.uuid4()),
            email="viewer@example.com",
            groups=["viewer"],
            exp=9999999999,
            iss="https://cognito-idp.eu-west-2.amazonaws.com/pool-id",
            client_id="test-client",
            token_use="access",
        )
    )
    # viewer can read but not write or delete
    def _check_perm(claims, resource, action):
        return action == "read"
    service.check_permission = MagicMock(side_effect=_check_perm)
    return service


def _make_product(
    product_id: uuid.UUID | None = None,
    name: str = "Test Product",
    price_pence: int = 500,
    stock_quantity: int = 100,
    category: str = "test",
    is_active: bool = True,
) -> Product:
    """Create a Product model instance for testing."""
    p = Product()
    p.id = product_id or uuid.uuid4()
    p.name = name
    p.description = "A test product"
    p.price_pence = price_pence
    p.stock_quantity = stock_quantity
    p.category = category
    p.is_active = is_active
    p.created_at = datetime.now(timezone.utc)
    p.updated_at = datetime.now(timezone.utc)
    return p


def _setup_overrides(app, mock_db, mock_cache, mock_auth_service):
    """Apply dependency overrides to the test app."""
    async def override_db():
        yield mock_db

    async def override_cache():
        return mock_cache

    async def override_auth():
        return mock_auth_service

    app.dependency_overrides[get_db_session] = override_db
    app.dependency_overrides[get_cache_client] = override_cache
    app.dependency_overrides[get_auth_service] = override_auth


# ===========================================================================
# Products Router Tests
# ===========================================================================


class TestProductsListEndpoint:
    """Tests for GET /products."""

    async def test_list_products_returns_paginated_results(
        self, app, mock_db, mock_cache, mock_auth_service
    ):
        """GET /products returns paginated product list from DB on cache miss."""
        _setup_overrides(app, mock_db, mock_cache, mock_auth_service)

        product = _make_product()
        # Mock the query execution for products
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [product]
        # Mock the count query
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1
        mock_db.execute = AsyncMock(side_effect=[mock_result, mock_count_result])

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/products",
                headers={"Authorization": "Bearer valid-token"},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["page"] == 1
        assert body["page_size"] == 20
        assert len(body["items"]) == 1
        assert body["items"][0]["name"] == "Test Product"

    async def test_list_products_returns_cached_results(
        self, app, mock_db, mock_cache, mock_auth_service
    ):
        """GET /products returns cached data on cache hit without querying DB."""
        _setup_overrides(app, mock_db, mock_cache, mock_auth_service)

        cached_response = {
            "items": [
                {
                    "id": str(uuid.uuid4()),
                    "name": "Cached Product",
                    "description": None,
                    "price_pence": 999,
                    "stock_quantity": 50,
                    "category": "cached",
                    "is_active": True,
                    "created_at": "2024-01-01T00:00:00",
                }
            ],
            "total": 1,
            "page": 1,
            "page_size": 20,
        }
        import json
        mock_cache.get = AsyncMock(return_value=json.dumps(cached_response))

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/products",
                headers={"Authorization": "Bearer valid-token"},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["items"][0]["name"] == "Cached Product"
        # DB should not have been called
        mock_db.execute.assert_not_called()

    async def test_list_products_requires_auth(self, app, mock_db, mock_cache, mock_auth_service):
        """GET /products returns 401 when no Authorization header is provided."""
        _setup_overrides(app, mock_db, mock_cache, mock_auth_service)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/products")

        assert resp.status_code == 401


class TestProductsGetEndpoint:
    """Tests for GET /products/{id}."""

    async def test_get_product_by_id(self, app, mock_db, mock_cache, mock_auth_service):
        """GET /products/{id} returns product details on cache miss."""
        _setup_overrides(app, mock_db, mock_cache, mock_auth_service)

        product = _make_product()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = product
        mock_db.execute = AsyncMock(return_value=mock_result)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                f"/products/{product.id}",
                headers={"Authorization": "Bearer valid-token"},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "Test Product"
        assert body["price_pence"] == 500

    async def test_get_product_not_found(self, app, mock_db, mock_cache, mock_auth_service):
        """GET /products/{id} returns 404 when product doesn't exist."""
        _setup_overrides(app, mock_db, mock_cache, mock_auth_service)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                f"/products/{uuid.uuid4()}",
                headers={"Authorization": "Bearer valid-token"},
            )

        assert resp.status_code == 404


class TestProductsCreateEndpoint:
    """Tests for POST /products."""

    async def test_create_product_valid_payload(
        self, app, mock_db, mock_cache, mock_auth_service
    ):
        """POST /products creates a product with valid data (admin/manager)."""
        _setup_overrides(app, mock_db, mock_cache, mock_auth_service)

        product = _make_product(name="New Widget", price_pence=1200, category="widgets")

        # After flush + refresh, the product should have an id
        async def fake_refresh(obj):
            obj.id = product.id
            obj.name = "New Widget"
            obj.description = "A widget"
            obj.price_pence = 1200
            obj.stock_quantity = 10
            obj.category = "widgets"
            obj.is_active = True
            obj.created_at = datetime.now(timezone.utc)
            obj.updated_at = datetime.now(timezone.utc)

        mock_db.refresh = AsyncMock(side_effect=fake_refresh)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/products",
                json={
                    "name": "New Widget",
                    "description": "A widget",
                    "price_pence": 1200,
                    "stock_quantity": 10,
                    "category": "widgets",
                },
                headers={"Authorization": "Bearer valid-token"},
            )

        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "New Widget"
        assert body["price_pence"] == 1200

    async def test_create_product_invalid_payload_missing_name(
        self, app, mock_db, mock_cache, mock_auth_service
    ):
        """POST /products returns 422 for missing required fields."""
        _setup_overrides(app, mock_db, mock_cache, mock_auth_service)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/products",
                json={
                    "description": "No name provided",
                    "price_pence": 500,
                    "stock_quantity": 10,
                    "category": "test",
                },
                headers={"Authorization": "Bearer valid-token"},
            )

        assert resp.status_code == 422

    async def test_create_product_invalid_price_zero(
        self, app, mock_db, mock_cache, mock_auth_service
    ):
        """POST /products returns 422 when price_pence is 0 (must be > 0)."""
        _setup_overrides(app, mock_db, mock_cache, mock_auth_service)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/products",
                json={
                    "name": "Free Item",
                    "price_pence": 0,
                    "stock_quantity": 10,
                    "category": "test",
                },
                headers={"Authorization": "Bearer valid-token"},
            )

        assert resp.status_code == 422

    async def test_create_product_invalid_negative_stock(
        self, app, mock_db, mock_cache, mock_auth_service
    ):
        """POST /products returns 422 when stock_quantity is negative."""
        _setup_overrides(app, mock_db, mock_cache, mock_auth_service)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/products",
                json={
                    "name": "Bad Stock",
                    "price_pence": 100,
                    "stock_quantity": -5,
                    "category": "test",
                },
                headers={"Authorization": "Bearer valid-token"},
            )

        assert resp.status_code == 422

    async def test_create_product_forbidden_for_viewer(
        self, app, mock_db, mock_cache, viewer_auth_service
    ):
        """POST /products returns 403 for viewer role (write not allowed)."""
        _setup_overrides(app, mock_db, mock_cache, viewer_auth_service)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/products",
                json={
                    "name": "Blocked Product",
                    "price_pence": 100,
                    "stock_quantity": 10,
                    "category": "test",
                },
                headers={"Authorization": "Bearer valid-token"},
            )

        assert resp.status_code == 403


class TestProductsUpdateEndpoint:
    """Tests for PUT /products/{id}."""

    async def test_update_product_valid_payload(
        self, app, mock_db, mock_cache, mock_auth_service
    ):
        """PUT /products/{id} updates specified fields."""
        _setup_overrides(app, mock_db, mock_cache, mock_auth_service)

        product = _make_product(name="Old Name", price_pence=500)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = product
        mock_db.execute = AsyncMock(return_value=mock_result)

        async def fake_refresh(obj):
            obj.name = "Updated Name"

        mock_db.refresh = AsyncMock(side_effect=fake_refresh)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.put(
                f"/products/{product.id}",
                json={"name": "Updated Name"},
                headers={"Authorization": "Bearer valid-token"},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "Updated Name"

    async def test_update_product_not_found(
        self, app, mock_db, mock_cache, mock_auth_service
    ):
        """PUT /products/{id} returns 404 for non-existent product."""
        _setup_overrides(app, mock_db, mock_cache, mock_auth_service)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.put(
                f"/products/{uuid.uuid4()}",
                json={"name": "No Such Product"},
                headers={"Authorization": "Bearer valid-token"},
            )

        assert resp.status_code == 404


class TestProductsDeleteEndpoint:
    """Tests for DELETE /products/{id}."""

    async def test_delete_product_soft_deletes(
        self, app, mock_db, mock_cache, mock_auth_service
    ):
        """DELETE /products/{id} returns 204 and soft-deletes the product."""
        _setup_overrides(app, mock_db, mock_cache, mock_auth_service)

        product = _make_product()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = product
        mock_db.execute = AsyncMock(return_value=mock_result)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.delete(
                f"/products/{product.id}",
                headers={"Authorization": "Bearer valid-token"},
            )

        assert resp.status_code == 204
        assert product.is_active is False

    async def test_delete_product_not_found(
        self, app, mock_db, mock_cache, mock_auth_service
    ):
        """DELETE /products/{id} returns 404 for non-existent product."""
        _setup_overrides(app, mock_db, mock_cache, mock_auth_service)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.delete(
                f"/products/{uuid.uuid4()}",
                headers={"Authorization": "Bearer valid-token"},
            )

        assert resp.status_code == 404

    async def test_delete_product_forbidden_for_viewer(
        self, app, mock_db, mock_cache, viewer_auth_service
    ):
        """DELETE /products/{id} returns 403 for viewer role."""
        _setup_overrides(app, mock_db, mock_cache, viewer_auth_service)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.delete(
                f"/products/{uuid.uuid4()}",
                headers={"Authorization": "Bearer valid-token"},
            )

        assert resp.status_code == 403


# ===========================================================================
# Orders Router Tests
# ===========================================================================


class TestOrdersCreateEndpoint:
    """Tests for POST /orders."""

    async def test_create_order_with_valid_items(
        self, app, mock_db, mock_cache, mock_auth_service
    ):
        """POST /orders creates an order, validates stock, calculates total."""
        _setup_overrides(app, mock_db, mock_cache, mock_auth_service)

        product_id = uuid.uuid4()
        product = _make_product(product_id=product_id, price_pence=1000, stock_quantity=50)

        user_id = uuid.UUID(mock_auth_service.validate_token.return_value.sub)

        # First execute: fetch products
        mock_products_result = MagicMock()
        mock_products_result.scalars.return_value.all.return_value = [product]

        # Second execute: reload order with items
        order_id = uuid.uuid4()
        order_item = OrderItem()
        order_item.id = uuid.uuid4()
        order_item.order_id = order_id
        order_item.product_id = product_id
        order_item.quantity = 3
        order_item.unit_price_pence = 1000

        order = Order()
        order.id = order_id
        order.user_id = user_id
        order.status = "pending"
        order.total_pence = 3000
        order.created_at = datetime.now(timezone.utc)
        order.updated_at = datetime.now(timezone.utc)
        order.items = [order_item]

        mock_order_result = MagicMock()
        mock_order_result.scalar_one.return_value = order

        mock_db.execute = AsyncMock(
            side_effect=[mock_products_result, mock_order_result]
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/orders",
                json={"items": [{"product_id": str(product_id), "quantity": 3}]},
                headers={"Authorization": "Bearer valid-token"},
            )

        assert resp.status_code == 201
        body = resp.json()
        assert body["total_pence"] == 3000
        assert body["status"] == "pending"
        assert len(body["items"]) == 1
        assert body["items"][0]["quantity"] == 3

    async def test_create_order_insufficient_stock(
        self, app, mock_db, mock_cache, mock_auth_service
    ):
        """POST /orders returns 400 when requested quantity exceeds stock."""
        _setup_overrides(app, mock_db, mock_cache, mock_auth_service)

        product_id = uuid.uuid4()
        product = _make_product(product_id=product_id, stock_quantity=2)

        mock_products_result = MagicMock()
        mock_products_result.scalars.return_value.all.return_value = [product]
        mock_db.execute = AsyncMock(return_value=mock_products_result)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/orders",
                json={"items": [{"product_id": str(product_id), "quantity": 10}]},
                headers={"Authorization": "Bearer valid-token"},
            )

        assert resp.status_code == 400
        body = resp.json()
        assert body["error"]["code"] == "HTTP_400"
        assert "insufficient_stock" in body["error"]["message"]

    async def test_create_order_product_not_found(
        self, app, mock_db, mock_cache, mock_auth_service
    ):
        """POST /orders returns 400 when a product in the order doesn't exist."""
        _setup_overrides(app, mock_db, mock_cache, mock_auth_service)

        # Return empty product list
        mock_products_result = MagicMock()
        mock_products_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_products_result)

        missing_id = uuid.uuid4()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/orders",
                json={"items": [{"product_id": str(missing_id), "quantity": 1}]},
                headers={"Authorization": "Bearer valid-token"},
            )

        assert resp.status_code == 400
        body = resp.json()
        assert body["error"]["code"] == "HTTP_400"
        assert "product_not_found" in body["error"]["message"]

    async def test_create_order_total_calculation_multiple_items(
        self, app, mock_db, mock_cache, mock_auth_service
    ):
        """POST /orders calculates total correctly across multiple line items."""
        _setup_overrides(app, mock_db, mock_cache, mock_auth_service)

        product_a_id = uuid.uuid4()
        product_b_id = uuid.uuid4()
        product_a = _make_product(product_id=product_a_id, price_pence=200, stock_quantity=50)
        product_b = _make_product(product_id=product_b_id, price_pence=350, stock_quantity=50)

        user_id = uuid.UUID(mock_auth_service.validate_token.return_value.sub)

        mock_products_result = MagicMock()
        mock_products_result.scalars.return_value.all.return_value = [product_a, product_b]

        # Expected total: 2*200 + 5*350 = 400 + 1750 = 2150
        order_id = uuid.uuid4()
        item_a = OrderItem()
        item_a.id = uuid.uuid4()
        item_a.order_id = order_id
        item_a.product_id = product_a_id
        item_a.quantity = 2
        item_a.unit_price_pence = 200

        item_b = OrderItem()
        item_b.id = uuid.uuid4()
        item_b.order_id = order_id
        item_b.product_id = product_b_id
        item_b.quantity = 5
        item_b.unit_price_pence = 350

        order = Order()
        order.id = order_id
        order.user_id = user_id
        order.status = "pending"
        order.total_pence = 2150
        order.created_at = datetime.now(timezone.utc)
        order.updated_at = datetime.now(timezone.utc)
        order.items = [item_a, item_b]

        mock_order_result = MagicMock()
        mock_order_result.scalar_one.return_value = order

        mock_db.execute = AsyncMock(
            side_effect=[mock_products_result, mock_order_result]
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/orders",
                json={
                    "items": [
                        {"product_id": str(product_a_id), "quantity": 2},
                        {"product_id": str(product_b_id), "quantity": 5},
                    ]
                },
                headers={"Authorization": "Bearer valid-token"},
            )

        assert resp.status_code == 201
        body = resp.json()
        assert body["total_pence"] == 2150
        assert len(body["items"]) == 2

    async def test_create_order_empty_items_returns_422(
        self, app, mock_db, mock_cache, mock_auth_service
    ):
        """POST /orders returns 422 when items list is empty."""
        _setup_overrides(app, mock_db, mock_cache, mock_auth_service)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/orders",
                json={"items": []},
                headers={"Authorization": "Bearer valid-token"},
            )

        assert resp.status_code == 422

    async def test_create_order_invalid_quantity_zero(
        self, app, mock_db, mock_cache, mock_auth_service
    ):
        """POST /orders returns 422 when item quantity is 0."""
        _setup_overrides(app, mock_db, mock_cache, mock_auth_service)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/orders",
                json={"items": [{"product_id": str(uuid.uuid4()), "quantity": 0}]},
                headers={"Authorization": "Bearer valid-token"},
            )

        assert resp.status_code == 422

    async def test_create_order_requires_auth(
        self, app, mock_db, mock_cache, mock_auth_service
    ):
        """POST /orders returns 401 when no token is provided."""
        _setup_overrides(app, mock_db, mock_cache, mock_auth_service)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/orders",
                json={"items": [{"product_id": str(uuid.uuid4()), "quantity": 1}]},
            )

        assert resp.status_code == 401


class TestOrdersListEndpoint:
    """Tests for GET /orders."""

    async def test_list_orders_returns_user_orders(
        self, app, mock_db, mock_cache, mock_auth_service
    ):
        """GET /orders returns orders belonging to the authenticated user."""
        _setup_overrides(app, mock_db, mock_cache, mock_auth_service)

        user_id = uuid.UUID(mock_auth_service.validate_token.return_value.sub)
        order = Order()
        order.id = uuid.uuid4()
        order.user_id = user_id
        order.status = "pending"
        order.total_pence = 500
        order.created_at = datetime.now(timezone.utc)
        order.updated_at = datetime.now(timezone.utc)
        order.items = []

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [order]
        mock_db.execute = AsyncMock(return_value=mock_result)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/orders",
                headers={"Authorization": "Bearer valid-token"},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["total_pence"] == 500


class TestOrdersGetEndpoint:
    """Tests for GET /orders/{id}."""

    async def test_get_order_not_found(
        self, app, mock_db, mock_cache, mock_auth_service
    ):
        """GET /orders/{id} returns 404 when order doesn't exist."""
        _setup_overrides(app, mock_db, mock_cache, mock_auth_service)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                f"/orders/{uuid.uuid4()}",
                headers={"Authorization": "Bearer valid-token"},
            )

        assert resp.status_code == 404


# ===========================================================================
# Auth Error Responses Tests
# ===========================================================================


class TestAuthErrorResponses:
    """Tests for 401 and 403 error responses across routers."""

    async def test_expired_token_returns_401(
        self, app, mock_db, mock_cache
    ):
        """Request with expired token returns 401."""
        expired_auth = AsyncMock(spec=AuthService)
        expired_auth.validate_token = AsyncMock(side_effect=TokenExpiredError())
        expired_auth.check_permission = MagicMock(return_value=True)
        _setup_overrides(app, mock_db, mock_cache, expired_auth)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/products",
                headers={"Authorization": "Bearer expired-token"},
            )

        assert resp.status_code == 401

    async def test_invalid_token_returns_401(
        self, app, mock_db, mock_cache
    ):
        """Request with invalid/malformed token returns 401."""
        invalid_auth = AsyncMock(spec=AuthService)
        invalid_auth.validate_token = AsyncMock(
            side_effect=InvalidTokenError("Malformed token")
        )
        invalid_auth.check_permission = MagicMock(return_value=True)
        _setup_overrides(app, mock_db, mock_cache, invalid_auth)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/products",
                headers={"Authorization": "Bearer bad-token"},
            )

        assert resp.status_code == 401

    async def test_missing_bearer_prefix_returns_401(
        self, app, mock_db, mock_cache, mock_auth_service
    ):
        """Request with Authorization header but no 'Bearer ' prefix returns 401."""
        _setup_overrides(app, mock_db, mock_cache, mock_auth_service)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/products",
                headers={"Authorization": "Basic some-credentials"},
            )

        assert resp.status_code == 401

    async def test_viewer_cannot_delete_products_returns_403(
        self, app, mock_db, mock_cache, viewer_auth_service
    ):
        """Viewer role attempting delete returns 403."""
        _setup_overrides(app, mock_db, mock_cache, viewer_auth_service)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.delete(
                f"/products/{uuid.uuid4()}",
                headers={"Authorization": "Bearer valid-token"},
            )

        assert resp.status_code == 403

    async def test_viewer_cannot_create_orders_returns_403(
        self, app, mock_db, mock_cache, viewer_auth_service
    ):
        """Viewer role attempting order creation returns 403."""
        _setup_overrides(app, mock_db, mock_cache, viewer_auth_service)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/orders",
                json={"items": [{"product_id": str(uuid.uuid4()), "quantity": 1}]},
                headers={"Authorization": "Bearer valid-token"},
            )

        assert resp.status_code == 403

    async def test_orders_expired_token_returns_401(
        self, app, mock_db, mock_cache
    ):
        """Orders endpoint with expired token returns 401."""
        expired_auth = AsyncMock(spec=AuthService)
        expired_auth.validate_token = AsyncMock(side_effect=TokenExpiredError())
        _setup_overrides(app, mock_db, mock_cache, expired_auth)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/orders",
                headers={"Authorization": "Bearer expired-token"},
            )

        assert resp.status_code == 401
