"""Property-based tests for Pydantic request model validation.

**Validates: Requirements 12.8, 6.9**

Uses Hypothesis to verify that Pydantic schema validation accepts all valid
input structures and rejects all invalid structures with correct field-level
error messages.
"""

import uuid

import pytest
from hypothesis import given, settings, assume, strategies as st
from pydantic import ValidationError

from app.schemas.product import ProductCreate
from app.schemas.order import OrderItemCreate, OrderCreate


# ---------------------------------------------------------------------------
# Strategies for valid data
# ---------------------------------------------------------------------------

valid_name = st.text(
    alphabet=st.characters(categories=("L", "N", "P", "Z")),
    min_size=1,
    max_size=255,
).filter(lambda s: len(s.strip()) > 0)

valid_description = st.one_of(
    st.none(),
    st.text(max_size=2000),
)

valid_price_pence = st.integers(min_value=1, max_value=10_000_000)

valid_stock_quantity = st.integers(min_value=0, max_value=1_000_000)

valid_category = st.text(
    alphabet=st.characters(categories=("L", "N", "P", "Z")),
    min_size=1,
    max_size=100,
).filter(lambda s: len(s.strip()) > 0)

valid_quantity = st.integers(min_value=1, max_value=100)

valid_uuid = st.uuids().map(str)


@st.composite
def valid_product_payload(draw):
    """Generate a valid ProductCreate payload."""
    return {
        "name": draw(valid_name),
        "description": draw(valid_description),
        "price_pence": draw(valid_price_pence),
        "stock_quantity": draw(valid_stock_quantity),
        "category": draw(valid_category),
    }


@st.composite
def valid_order_item_payload(draw):
    """Generate a valid OrderItemCreate payload."""
    return {
        "product_id": draw(valid_uuid),
        "quantity": draw(valid_quantity),
    }


@st.composite
def valid_order_payload(draw):
    """Generate a valid OrderCreate payload with 1-50 items."""
    num_items = draw(st.integers(min_value=1, max_value=5))
    items = [draw(valid_order_item_payload()) for _ in range(num_items)]
    return {"items": items}


# ---------------------------------------------------------------------------
# Property tests: valid payloads are accepted
# ---------------------------------------------------------------------------


@pytest.mark.property
@settings(max_examples=50)
@given(payload=valid_product_payload())
def test_valid_product_payload_accepted(payload):
    """Property: all valid ProductCreate payloads are accepted without error.

    **Validates: Requirements 12.8**
    """
    product = ProductCreate(**payload)
    assert product.name == payload["name"]
    assert product.price_pence == payload["price_pence"]
    assert product.stock_quantity == payload["stock_quantity"]
    assert product.category == payload["category"]
    assert product.description == payload["description"]


@pytest.mark.property
@settings(max_examples=50)
@given(payload=valid_order_payload())
def test_valid_order_payload_accepted(payload):
    """Property: all valid OrderCreate payloads are accepted without error.

    **Validates: Requirements 12.8**
    """
    order = OrderCreate(**payload)
    assert len(order.items) == len(payload["items"])
    for item, raw in zip(order.items, payload["items"]):
        assert str(item.product_id) == raw["product_id"]
        assert item.quantity == raw["quantity"]


# ---------------------------------------------------------------------------
# Property tests: invalid payloads are rejected with field-level errors
# ---------------------------------------------------------------------------


@pytest.mark.property
@settings(max_examples=50)
@given(
    name=st.one_of(
        st.just(""),  # too short
        st.text(min_size=256, max_size=300),  # too long
    )
)
def test_invalid_product_name_rejected(name):
    """Property: ProductCreate rejects names violating length constraints.

    name must have min_length=1, max_length=255.

    **Validates: Requirements 12.8, 6.9**
    """
    with pytest.raises(ValidationError) as exc_info:
        ProductCreate(
            name=name,
            price_pence=100,
            stock_quantity=0,
            category="test",
        )
    errors = exc_info.value.errors()
    field_names = [e["loc"][-1] for e in errors]
    assert "name" in field_names


@pytest.mark.property
@settings(max_examples=50)
@given(description=st.text(min_size=2001, max_size=2100))
def test_invalid_product_description_rejected(description):
    """Property: ProductCreate rejects descriptions exceeding max_length=2000.

    **Validates: Requirements 12.8, 6.9**
    """
    with pytest.raises(ValidationError) as exc_info:
        ProductCreate(
            name="Valid Name",
            description=description,
            price_pence=100,
            stock_quantity=0,
            category="test",
        )
    errors = exc_info.value.errors()
    field_names = [e["loc"][-1] for e in errors]
    assert "description" in field_names


@pytest.mark.property
@settings(max_examples=50)
@given(
    price=st.one_of(
        st.integers(max_value=0),  # must be gt=0
        st.integers(min_value=10_000_001),  # must be le=10_000_000
    )
)
def test_invalid_product_price_rejected(price):
    """Property: ProductCreate rejects price_pence outside (0, 10_000_000].

    price_pence must satisfy gt=0 and le=10_000_000.

    **Validates: Requirements 12.8, 6.9**
    """
    with pytest.raises(ValidationError) as exc_info:
        ProductCreate(
            name="Valid Name",
            price_pence=price,
            stock_quantity=0,
            category="test",
        )
    errors = exc_info.value.errors()
    field_names = [e["loc"][-1] for e in errors]
    assert "price_pence" in field_names


@pytest.mark.property
@settings(max_examples=50)
@given(stock=st.integers(max_value=-1))
def test_invalid_product_stock_rejected(stock):
    """Property: ProductCreate rejects negative stock_quantity (must be ge=0).

    **Validates: Requirements 12.8, 6.9**
    """
    with pytest.raises(ValidationError) as exc_info:
        ProductCreate(
            name="Valid Name",
            price_pence=100,
            stock_quantity=stock,
            category="test",
        )
    errors = exc_info.value.errors()
    field_names = [e["loc"][-1] for e in errors]
    assert "stock_quantity" in field_names


@pytest.mark.property
@settings(max_examples=50)
@given(
    category=st.one_of(
        st.just(""),  # too short
        st.text(min_size=101, max_size=150),  # too long
    )
)
def test_invalid_product_category_rejected(category):
    """Property: ProductCreate rejects categories violating length constraints.

    category must have min_length=1, max_length=100.

    **Validates: Requirements 12.8, 6.9**
    """
    with pytest.raises(ValidationError) as exc_info:
        ProductCreate(
            name="Valid Name",
            price_pence=100,
            stock_quantity=0,
            category=category,
        )
    errors = exc_info.value.errors()
    field_names = [e["loc"][-1] for e in errors]
    assert "category" in field_names


@pytest.mark.property
@settings(max_examples=50)
@given(
    quantity=st.one_of(
        st.integers(max_value=0),  # must be gt=0
        st.integers(min_value=101),  # must be le=100
    )
)
def test_invalid_order_item_quantity_rejected(quantity):
    """Property: OrderItemCreate rejects quantity outside (0, 100].

    quantity must satisfy gt=0 and le=100.

    **Validates: Requirements 12.8, 6.9**
    """
    with pytest.raises(ValidationError) as exc_info:
        OrderItemCreate(
            product_id=uuid.uuid4(),
            quantity=quantity,
        )
    errors = exc_info.value.errors()
    field_names = [e["loc"][-1] for e in errors]
    assert "quantity" in field_names


@pytest.mark.property
@settings(max_examples=50)
@given(
    items=st.one_of(
        st.just([]),  # empty list, min_length=1
        st.lists(
            valid_order_item_payload(),
            min_size=51,
            max_size=55,
        ),  # too many items, max_length=50
    )
)
def test_invalid_order_items_count_rejected(items):
    """Property: OrderCreate rejects item lists violating length constraints.

    items must have min_length=1 and max_length=50.

    **Validates: Requirements 12.8, 6.9**
    """
    with pytest.raises(ValidationError) as exc_info:
        OrderCreate(items=items)
    errors = exc_info.value.errors()
    field_names = [e["loc"][-1] for e in errors]
    assert "items" in field_names


@pytest.mark.property
@settings(max_examples=50)
@given(data=st.data())
def test_missing_required_fields_rejected_with_field_errors(data):
    """Property: missing required fields produce field-level validation errors.

    ProductCreate requires: name, price_pence, stock_quantity, category.
    Omitting any required field should produce a validation error for that field.

    **Validates: Requirements 12.8, 6.9**
    """
    all_fields = ["name", "price_pence", "stock_quantity", "category"]
    # Randomly pick which fields to omit (at least one)
    fields_to_omit = data.draw(
        st.lists(st.sampled_from(all_fields), min_size=1, max_size=4, unique=True)
    )

    payload = {
        "name": "Valid Name",
        "price_pence": 100,
        "stock_quantity": 0,
        "category": "test",
    }
    for field in fields_to_omit:
        del payload[field]

    with pytest.raises(ValidationError) as exc_info:
        ProductCreate(**payload)

    errors = exc_info.value.errors()
    error_fields = {e["loc"][-1] for e in errors}
    for field in fields_to_omit:
        assert field in error_fields, f"Expected error for missing field '{field}'"


@pytest.mark.property
@settings(max_examples=50)
@given(
    wrong_type_value=st.one_of(
        st.text(min_size=1, max_size=10),  # string where int expected
        st.lists(st.integers(), min_size=1, max_size=3),  # list where int expected
    )
)
def test_wrong_type_for_price_rejected(wrong_type_value):
    """Property: wrong types for numeric fields are rejected with field-level errors.

    **Validates: Requirements 12.8, 6.9**
    """
    # Pydantic coerces some types, so filter out values that would coerce to valid ints
    if isinstance(wrong_type_value, str):
        try:
            int(wrong_type_value)
            assume(False)  # Skip strings that look like valid ints
        except (ValueError, TypeError):
            pass

    with pytest.raises(ValidationError) as exc_info:
        ProductCreate(
            name="Valid Name",
            price_pence=wrong_type_value,
            stock_quantity=0,
            category="test",
        )
    errors = exc_info.value.errors()
    field_names = [e["loc"][-1] for e in errors]
    assert "price_pence" in field_names
