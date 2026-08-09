"""Property-based tests for session data serialisation round-trip.

**Validates: Requirements 4.10, 12.10**

Uses Hypothesis to generate SessionData instances with random valid fields
and verify that JSON serialisation (model_dump_json) followed by deserialisation
(model_validate_json) preserves all data types and values without loss.
"""

import pytest
from hypothesis import given, settings, strategies as st

from app.services.session_service import SessionData


# Strategy for generating valid metadata dictionaries (JSON-compatible values)
json_primitives = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-(2**53), max_value=2**53),
    st.floats(allow_nan=False, allow_infinity=False),
    st.text(max_size=50),
)

json_values = st.recursive(
    json_primitives,
    lambda children: st.one_of(
        st.lists(children, max_size=5),
        st.dictionaries(st.text(min_size=1, max_size=20), children, max_size=5),
    ),
    max_leaves=10,
)

metadata_strategy = st.dictionaries(
    keys=st.text(min_size=1, max_size=30),
    values=json_values,
    max_size=10,
)


@st.composite
def session_data_strategy(draw):
    """Generate valid SessionData instances with random fields.

    Produces realistic combinations of user_id, email, role, groups,
    timestamps, and metadata values.
    """
    user_id = draw(st.text(min_size=1, max_size=64, alphabet=st.characters(
        whitelist_categories=("L", "N", "P"),
    )))
    email = draw(st.emails())
    role = draw(st.sampled_from(["admin", "manager", "viewer", "editor", "analyst"]))
    groups = draw(st.lists(
        st.text(min_size=1, max_size=30, alphabet=st.characters(
            whitelist_categories=("L", "N"),
        )),
        max_size=10,
    ))
    # Unix timestamps: reasonable range (year 2000 to year 2100)
    created_at = draw(st.floats(
        min_value=946684800.0,
        max_value=4102444800.0,
        allow_nan=False,
        allow_infinity=False,
    ))
    last_accessed = draw(st.floats(
        min_value=created_at,
        max_value=4102444800.0,
        allow_nan=False,
        allow_infinity=False,
    ))
    metadata = draw(metadata_strategy)

    return SessionData(
        user_id=user_id,
        email=email,
        role=role,
        groups=groups,
        created_at=created_at,
        last_accessed=last_accessed,
        metadata=metadata,
    )


@pytest.mark.property
@settings(max_examples=200)
@given(session=session_data_strategy())
def test_serialise_deserialise_preserves_all_fields(session: SessionData):
    """Property: serialise→deserialise round-trip preserves all data fields.

    For any valid SessionData instance, converting to JSON and back must
    produce an identical object with all fields and types intact.

    **Validates: Requirements 4.10, 12.10**
    """
    serialised = session.model_dump_json()
    restored = SessionData.model_validate_json(serialised)

    assert restored == session


@pytest.mark.property
@settings(max_examples=200)
@given(session=session_data_strategy())
def test_serialise_deserialise_preserves_types(session: SessionData):
    """Property: round-trip preserves Python types for all fields.

    Verifies that after deserialisation, field types match the originals
    (str remains str, list remains list, float remains float, dict remains dict).

    **Validates: Requirements 4.10, 12.10**
    """
    serialised = session.model_dump_json()
    restored = SessionData.model_validate_json(serialised)

    assert isinstance(restored.user_id, str)
    assert isinstance(restored.email, str)
    assert isinstance(restored.role, str)
    assert isinstance(restored.groups, list)
    assert all(isinstance(g, str) for g in restored.groups)
    assert isinstance(restored.created_at, float)
    assert isinstance(restored.last_accessed, float)
    assert isinstance(restored.metadata, dict)
