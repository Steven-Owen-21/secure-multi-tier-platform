"""Property-based tests for Terraform variable validation logic.

**Validates: Requirements 16.7**

Uses Hypothesis to generate invalid CIDR ranges, instance sizes, and retention
period values, verifying that validation logic rejects all invalid inputs with
appropriate error messages.

Property 6: Terraform variable validation rejects all out-of-range values.
"""

import pytest
from hypothesis import given, settings, strategies as st

from infrastructure.logic.terraform_validation import (
    ValidationResult,
    validate_app_port,
    validate_az_count,
    validate_db_backup_retention_days,
    validate_ecs_max_capacity,
    validate_ecs_min_capacity,
    validate_vpc_cidr,
    validate_waf_body_size_limit,
    validate_waf_rate_limit,
)


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

# Invalid CIDR strategies - various forms of invalid CIDR blocks
invalid_cidr_wrong_prefix = st.sampled_from([
    "10.0.0.0/8",
    "10.0.0.0/24",
    "10.0.0.0/32",
    "192.168.0.0/12",
    "172.16.0.0/20",
    "10.0.0.0/15",
    "10.0.0.0/17",
])

invalid_cidr_malformed = st.sampled_from([
    "not-a-cidr/16",
    "999.999.999.999/16",
    "10.0.0/16",
    "10.0.0.0.0/16",
    "/16",
    "10.0.0.0",
    "",
    "abc.def.ghi.jkl/16",
    "256.0.0.0/16",
    "10.0.0.-1/16",
])

# Combine all invalid CIDR strategies
invalid_cidrs = st.one_of(invalid_cidr_wrong_prefix, invalid_cidr_malformed)

# Valid CIDR blocks for positive testing
valid_cidrs = st.sampled_from([
    "10.0.0.0/16",
    "172.16.0.0/16",
    "192.168.0.0/16",
    "10.1.0.0/16",
    "10.255.0.0/16",
])

# Invalid AZ counts (outside 2-4 range)
invalid_az_counts = st.one_of(
    st.integers(max_value=1),
    st.integers(min_value=5),
)

# Invalid ECS min capacity (below 1)
invalid_ecs_min = st.integers(max_value=0)

# Invalid ECS max capacity (below 2)
invalid_ecs_max = st.integers(max_value=1)

# Invalid DB backup retention (outside 1-35 range)
invalid_retention_days = st.one_of(
    st.integers(max_value=0),
    st.integers(min_value=36),
)

# Invalid app port (outside 1-65535 range)
invalid_app_ports = st.one_of(
    st.integers(max_value=0),
    st.integers(min_value=65536),
)

# Invalid WAF rate limit (outside 100-20,000,000 range)
invalid_waf_rate_limits = st.one_of(
    st.integers(max_value=99),
    st.integers(min_value=20_000_001),
)

# Invalid WAF body size limit (outside 1024-65536 range)
invalid_waf_body_sizes = st.one_of(
    st.integers(max_value=1023),
    st.integers(min_value=65537),
)


# ---------------------------------------------------------------------------
# Property tests: Invalid inputs are rejected
# ---------------------------------------------------------------------------


@pytest.mark.property
@settings(max_examples=100)
@given(cidr=invalid_cidrs)
def test_vpc_cidr_rejects_invalid_inputs(cidr):
    """Property 6: vpc_cidr validation rejects invalid CIDR blocks.

    For any CIDR string that is not a valid /16 CIDR block, the validation
    SHALL return invalid with an appropriate error message.

    **Validates: Requirements 16.7**
    """
    result = validate_vpc_cidr(cidr)

    assert not result.valid, f"Expected invalid for CIDR '{cidr}' but got valid"
    assert result.error_message is not None
    assert "vpc_cidr" in result.error_message
    assert "/16" in result.error_message


@pytest.mark.property
@settings(max_examples=50)
@given(cidr=valid_cidrs)
def test_vpc_cidr_accepts_valid_inputs(cidr):
    """Property 6: vpc_cidr validation accepts valid /16 CIDR blocks.

    For any valid /16 CIDR block, the validation SHALL return valid.

    **Validates: Requirements 16.7**
    """
    result = validate_vpc_cidr(cidr)

    assert result.valid, f"Expected valid for CIDR '{cidr}' but got: {result.error_message}"
    assert result.error_message is None


@pytest.mark.property
@settings(max_examples=100)
@given(az_count=invalid_az_counts)
def test_az_count_rejects_invalid_inputs(az_count):
    """Property 6: az_count validation rejects values outside 2-4.

    For any integer outside the range [2, 4], the validation
    SHALL return invalid with an appropriate error message.

    **Validates: Requirements 16.7**
    """
    result = validate_az_count(az_count)

    assert not result.valid, f"Expected invalid for az_count={az_count} but got valid"
    assert result.error_message is not None
    assert "az_count" in result.error_message


@pytest.mark.property
@settings(max_examples=50)
@given(az_count=st.integers(min_value=2, max_value=4))
def test_az_count_accepts_valid_inputs(az_count):
    """Property 6: az_count validation accepts values in [2, 4].

    For any integer in the range [2, 4], the validation SHALL return valid.

    **Validates: Requirements 16.7**
    """
    result = validate_az_count(az_count)

    assert result.valid, f"Expected valid for az_count={az_count} but got: {result.error_message}"
    assert result.error_message is None


@pytest.mark.property
@settings(max_examples=100)
@given(min_cap=invalid_ecs_min)
def test_ecs_min_capacity_rejects_invalid_inputs(min_cap):
    """Property 6: ecs_min_capacity validation rejects values below 1.

    For any integer less than 1, the validation SHALL return invalid
    with an appropriate error message.

    **Validates: Requirements 16.7**
    """
    result = validate_ecs_min_capacity(min_cap)

    assert not result.valid, f"Expected invalid for ecs_min_capacity={min_cap} but got valid"
    assert result.error_message is not None
    assert "ecs_min_capacity" in result.error_message


@pytest.mark.property
@settings(max_examples=50)
@given(min_cap=st.integers(min_value=1, max_value=100))
def test_ecs_min_capacity_accepts_valid_inputs(min_cap):
    """Property 6: ecs_min_capacity validation accepts values >= 1.

    For any integer >= 1, the validation SHALL return valid.

    **Validates: Requirements 16.7**
    """
    result = validate_ecs_min_capacity(min_cap)

    assert result.valid, (
        f"Expected valid for ecs_min_capacity={min_cap} but got: {result.error_message}"
    )
    assert result.error_message is None


@pytest.mark.property
@settings(max_examples=100)
@given(max_cap=invalid_ecs_max)
def test_ecs_max_capacity_rejects_invalid_inputs(max_cap):
    """Property 6: ecs_max_capacity validation rejects values below 2.

    For any integer less than 2, the validation SHALL return invalid
    with an appropriate error message.

    **Validates: Requirements 16.7**
    """
    result = validate_ecs_max_capacity(max_cap)

    assert not result.valid, f"Expected invalid for ecs_max_capacity={max_cap} but got valid"
    assert result.error_message is not None
    assert "ecs_max_capacity" in result.error_message


@pytest.mark.property
@settings(max_examples=50)
@given(max_cap=st.integers(min_value=2, max_value=100))
def test_ecs_max_capacity_accepts_valid_inputs(max_cap):
    """Property 6: ecs_max_capacity validation accepts values >= 2.

    For any integer >= 2, the validation SHALL return valid.

    **Validates: Requirements 16.7**
    """
    result = validate_ecs_max_capacity(max_cap)

    assert result.valid, (
        f"Expected valid for ecs_max_capacity={max_cap} but got: {result.error_message}"
    )
    assert result.error_message is None


@pytest.mark.property
@settings(max_examples=100)
@given(retention=invalid_retention_days)
def test_db_backup_retention_rejects_invalid_inputs(retention):
    """Property 6: db_backup_retention_days validation rejects values outside 1-35.

    For any integer outside the range [1, 35], the validation
    SHALL return invalid with an appropriate error message.

    **Validates: Requirements 16.7**
    """
    result = validate_db_backup_retention_days(retention)

    assert not result.valid, (
        f"Expected invalid for db_backup_retention_days={retention} but got valid"
    )
    assert result.error_message is not None
    assert "db_backup_retention_days" in result.error_message


@pytest.mark.property
@settings(max_examples=50)
@given(retention=st.integers(min_value=1, max_value=35))
def test_db_backup_retention_accepts_valid_inputs(retention):
    """Property 6: db_backup_retention_days validation accepts values in [1, 35].

    For any integer in the range [1, 35], the validation SHALL return valid.

    **Validates: Requirements 16.7**
    """
    result = validate_db_backup_retention_days(retention)

    assert result.valid, (
        f"Expected valid for db_backup_retention_days={retention} but got: {result.error_message}"
    )
    assert result.error_message is None


@pytest.mark.property
@settings(max_examples=100)
@given(port=invalid_app_ports)
def test_app_port_rejects_invalid_inputs(port):
    """Property 6: app_port validation rejects values outside 1-65535.

    For any integer outside the range [1, 65535], the validation
    SHALL return invalid with an appropriate error message.

    **Validates: Requirements 16.7**
    """
    result = validate_app_port(port)

    assert not result.valid, f"Expected invalid for app_port={port} but got valid"
    assert result.error_message is not None
    assert "app_port" in result.error_message


@pytest.mark.property
@settings(max_examples=50)
@given(port=st.integers(min_value=1, max_value=65535))
def test_app_port_accepts_valid_inputs(port):
    """Property 6: app_port validation accepts values in [1, 65535].

    For any integer in the range [1, 65535], the validation SHALL return valid.

    **Validates: Requirements 16.7**
    """
    result = validate_app_port(port)

    assert result.valid, f"Expected valid for app_port={port} but got: {result.error_message}"
    assert result.error_message is None


@pytest.mark.property
@settings(max_examples=100)
@given(rate=invalid_waf_rate_limits)
def test_waf_rate_limit_rejects_invalid_inputs(rate):
    """Property 6: waf_rate_limit validation rejects values outside 100-20,000,000.

    For any integer outside the range [100, 20,000,000], the validation
    SHALL return invalid with an appropriate error message.

    **Validates: Requirements 16.7**
    """
    result = validate_waf_rate_limit(rate)

    assert not result.valid, f"Expected invalid for waf_rate_limit={rate} but got valid"
    assert result.error_message is not None
    assert "waf_rate_limit" in result.error_message


@pytest.mark.property
@settings(max_examples=50)
@given(rate=st.integers(min_value=100, max_value=20_000_000))
def test_waf_rate_limit_accepts_valid_inputs(rate):
    """Property 6: waf_rate_limit validation accepts values in [100, 20,000,000].

    For any integer in the range [100, 20,000,000], the validation SHALL return valid.

    **Validates: Requirements 16.7**
    """
    result = validate_waf_rate_limit(rate)

    assert result.valid, (
        f"Expected valid for waf_rate_limit={rate} but got: {result.error_message}"
    )
    assert result.error_message is None


@pytest.mark.property
@settings(max_examples=100)
@given(size=invalid_waf_body_sizes)
def test_waf_body_size_limit_rejects_invalid_inputs(size):
    """Property 6: waf_body_size_limit validation rejects values outside 1024-65536.

    For any integer outside the range [1024, 65536], the validation
    SHALL return invalid with an appropriate error message.

    **Validates: Requirements 16.7**
    """
    result = validate_waf_body_size_limit(size)

    assert not result.valid, f"Expected invalid for waf_body_size_limit={size} but got valid"
    assert result.error_message is not None
    assert "waf_body_size_limit" in result.error_message


@pytest.mark.property
@settings(max_examples=50)
@given(size=st.integers(min_value=1024, max_value=65536))
def test_waf_body_size_limit_accepts_valid_inputs(size):
    """Property 6: waf_body_size_limit validation accepts values in [1024, 65536].

    For any integer in the range [1024, 65536], the validation SHALL return valid.

    **Validates: Requirements 16.7**
    """
    result = validate_waf_body_size_limit(size)

    assert result.valid, (
        f"Expected valid for waf_body_size_limit={size} but got: {result.error_message}"
    )
    assert result.error_message is None
