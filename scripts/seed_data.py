"""Database seed script for local development.

Populates the local PostgreSQL instance with realistic sample data:
- 5 users with different roles
- 20 products across categories
- 10 orders with order items

Usage:
    python -m scripts.seed_data
    # or via Makefile:
    make seed-data
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from random import Random

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.models import Base, Order, OrderItem, Product, User

# Fixed seed for reproducible data
_RNG = Random(42)


# --- Sample Data Definitions ---

USERS = [
    {
        "cognito_sub": "sub-admin-001",
        "email": "admin@example.com",
        "full_name": "Alice Admin",
        "role": "admin",
    },
    {
        "cognito_sub": "sub-manager-001",
        "email": "bob.manager@example.com",
        "full_name": "Bob Manager",
        "role": "manager",
    },
    {
        "cognito_sub": "sub-manager-002",
        "email": "carol.manager@example.com",
        "full_name": "Carol Manager",
        "role": "manager",
    },
    {
        "cognito_sub": "sub-viewer-001",
        "email": "dave.viewer@example.com",
        "full_name": "Dave Viewer",
        "role": "viewer",
    },
    {
        "cognito_sub": "sub-viewer-002",
        "email": "eve.viewer@example.com",
        "full_name": "Eve Viewer",
        "role": "viewer",
    },
]

PRODUCTS = [
    # Electronics (5)
    {"name": "Wireless Headphones", "description": "Noise-cancelling Bluetooth headphones", "price_pence": 7999, "stock_quantity": 150, "category": "electronics"},
    {"name": "USB-C Hub", "description": "7-in-1 USB-C docking station", "price_pence": 3499, "stock_quantity": 200, "category": "electronics"},
    {"name": "Mechanical Keyboard", "description": "RGB mechanical keyboard with Cherry MX switches", "price_pence": 8999, "stock_quantity": 75, "category": "electronics"},
    {"name": "Webcam 4K", "description": "Ultra HD webcam with auto-focus", "price_pence": 5999, "stock_quantity": 120, "category": "electronics"},
    {"name": "Portable SSD 1TB", "description": "External NVMe SSD with USB 3.2", "price_pence": 6999, "stock_quantity": 90, "category": "electronics"},
    # Office Supplies (5)
    {"name": "Ergonomic Mouse", "description": "Vertical ergonomic wireless mouse", "price_pence": 2499, "stock_quantity": 300, "category": "office"},
    {"name": "Standing Desk Mat", "description": "Anti-fatigue mat for standing desks", "price_pence": 4499, "stock_quantity": 60, "category": "office"},
    {"name": "Monitor Arm", "description": "Adjustable single monitor arm clamp mount", "price_pence": 3999, "stock_quantity": 85, "category": "office"},
    {"name": "Desk Organiser", "description": "Bamboo desk organiser with drawers", "price_pence": 1999, "stock_quantity": 200, "category": "office"},
    {"name": "Whiteboard 120x90cm", "description": "Magnetic dry-erase whiteboard", "price_pence": 4999, "stock_quantity": 40, "category": "office"},
    # Books (5)
    {"name": "Cloud Architecture Patterns", "description": "Comprehensive guide to cloud design patterns", "price_pence": 3499, "stock_quantity": 500, "category": "books"},
    {"name": "Terraform: Up & Running", "description": "Practical infrastructure as code guide", "price_pence": 2999, "stock_quantity": 350, "category": "books"},
    {"name": "Designing Data-Intensive Apps", "description": "Distributed systems fundamentals", "price_pence": 3999, "stock_quantity": 400, "category": "books"},
    {"name": "The Phoenix Project", "description": "Novel about IT and DevOps transformation", "price_pence": 1499, "stock_quantity": 600, "category": "books"},
    {"name": "Site Reliability Engineering", "description": "How Google runs production systems", "price_pence": 4499, "stock_quantity": 250, "category": "books"},
    # Hardware (5)
    {"name": "Raspberry Pi 5 8GB", "description": "Single-board computer for projects", "price_pence": 7999, "stock_quantity": 45, "category": "hardware"},
    {"name": "Arduino Starter Kit", "description": "Complete electronics learning kit", "price_pence": 5499, "stock_quantity": 70, "category": "hardware"},
    {"name": "Network Switch 8-port", "description": "Gigabit unmanaged network switch", "price_pence": 2999, "stock_quantity": 100, "category": "hardware"},
    {"name": "Ethernet Cable Cat6 5m", "description": "Shielded Cat6 patch cable", "price_pence": 799, "stock_quantity": 1000, "category": "hardware"},
    {"name": "UPS 1500VA", "description": "Uninterruptible power supply with USB", "price_pence": 12999, "stock_quantity": 30, "category": "hardware"},
]

ORDER_STATUSES = ["pending", "confirmed", "shipped", "delivered", "cancelled"]


def _generate_orders(
    users: list[User], products: list[Product]
) -> list[tuple[Order, list[OrderItem]]]:
    """Generate 10 orders with random items."""
    orders: list[tuple[Order, list[OrderItem]]] = []
    base_time = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)

    for i in range(10):
        user = _RNG.choice(users)
        status = _RNG.choice(ORDER_STATUSES)
        order_id = uuid.UUID(int=_RNG.getrandbits(128))

        # Pick 1-4 random products for the order
        num_items = _RNG.randint(1, 4)
        selected_products = _RNG.sample(products, num_items)

        items: list[OrderItem] = []
        total_pence = 0

        for product in selected_products:
            quantity = _RNG.randint(1, 5)
            unit_price = product.price_pence
            total_pence += unit_price * quantity

            item = OrderItem(
                id=uuid.UUID(int=_RNG.getrandbits(128)),
                order_id=order_id,
                product_id=product.id,
                quantity=quantity,
                unit_price_pence=unit_price,
            )
            items.append(item)

        created_at = base_time + timedelta(days=i * 3, hours=_RNG.randint(0, 12))
        order = Order(
            id=order_id,
            user_id=user.id,
            status=status,
            total_pence=total_pence,
            created_at=created_at,
            updated_at=created_at,
        )
        orders.append((order, items))

    return orders


async def seed_database() -> None:
    """Seed the local database with sample data."""
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)

    # Create all tables (idempotent for local dev)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        # Check if data already exists
        result = await session.execute(text("SELECT count(*) FROM users"))
        count = result.scalar()
        if count and count > 0:
            print(f"Database already seeded ({count} users found). Skipping.")
            await engine.dispose()
            return

        # Seed users
        users: list[User] = []
        for user_data in USERS:
            user = User(id=uuid.UUID(int=_RNG.getrandbits(128)), **user_data)
            session.add(user)
            users.append(user)
        await session.flush()
        print(f"  Created {len(users)} users")

        # Seed products
        products: list[Product] = []
        for product_data in PRODUCTS:
            product = Product(id=uuid.UUID(int=_RNG.getrandbits(128)), **product_data)
            session.add(product)
            products.append(product)
        await session.flush()
        print(f"  Created {len(products)} products")

        # Seed orders and order items
        order_data = _generate_orders(users, products)
        for order, items in order_data:
            session.add(order)
            for item in items:
                session.add(item)
        await session.flush()
        print(f"  Created {len(order_data)} orders with items")

        await session.commit()

    await engine.dispose()
    print("\nDatabase seeded successfully!")


def main() -> None:
    """Entry point for the seed script."""
    print("Seeding local PostgreSQL database...")
    asyncio.run(seed_database())


if __name__ == "__main__":
    main()
