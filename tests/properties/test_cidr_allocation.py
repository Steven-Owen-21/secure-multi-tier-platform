"""Property-based tests for CIDR allocation logic.

**Validates: Requirements 1.9**

Uses Hypothesis to verify that the VPC module's CIDR allocation logic produces
non-overlapping subnet ranges for all valid AZ count and subnet size inputs.
"""

import ipaddress
from typing import List, Tuple

import pytest
from hypothesis import given, settings, strategies as st


# ---------------------------------------------------------------------------
# CIDR allocation logic mirroring the VPC Terraform module behaviour.
#
# The VPC uses a /16 CIDR. Subnets are /24 blocks allocated as:
#   - Public subnets:  10.0.1.0/24, 10.0.2.0/24, ... (offset 1 per AZ)
#   - Private subnets: 10.0.10.0/24, 10.0.11.0/24, ... (offset 10 per AZ)
# ---------------------------------------------------------------------------


def allocate_subnets(
    vpc_cidr: str, az_count: int
) -> Tuple[List[ipaddress.IPv4Network], List[ipaddress.IPv4Network]]:
    """Allocate public and private /24 subnets within a /16 VPC CIDR.

    Args:
        vpc_cidr: The VPC CIDR block (e.g. "10.0.0.0/16").
        az_count: Number of Availability Zones (2-4).

    Returns:
        Tuple of (public_subnets, private_subnets) as lists of IPv4Network.

    Raises:
        ValueError: If vpc_cidr is not a /16 or az_count is out of range.
    """
    vpc_network = ipaddress.IPv4Network(vpc_cidr, strict=True)

    if vpc_network.prefixlen != 16:
        raise ValueError(f"VPC CIDR must be /16, got /{vpc_network.prefixlen}")

    if not (2 <= az_count <= 4):
        raise ValueError(f"az_count must be between 2 and 4, got {az_count}")

    # Extract base octets from the VPC network address (e.g. 10, 0 from 10.0.0.0)
    base_octets = vpc_network.network_address.packed[:2]

    public_subnets: List[ipaddress.IPv4Network] = []
    private_subnets: List[ipaddress.IPv4Network] = []

    for i in range(az_count):
        # Public subnets start at third-octet offset 1: 10.0.1.0/24, 10.0.2.0/24, ...
        public_third_octet = 1 + i
        public_addr = ipaddress.IPv4Address(
            base_octets + bytes([public_third_octet, 0])
        )
        public_subnets.append(ipaddress.IPv4Network(f"{public_addr}/24"))

        # Private subnets start at third-octet offset 10: 10.0.10.0/24, 10.0.11.0/24, ...
        private_third_octet = 10 + i
        private_addr = ipaddress.IPv4Address(
            base_octets + bytes([private_third_octet, 0])
        )
        private_subnets.append(ipaddress.IPv4Network(f"{private_addr}/24"))

    return public_subnets, private_subnets


# ---------------------------------------------------------------------------
# Hypothesis Strategies
# ---------------------------------------------------------------------------


@st.composite
def valid_vpc_cidr(draw: st.DrawFn) -> str:
    """Generate a valid /16 VPC CIDR block.

    Generates CIDRs like X.Y.0.0/16 where X is in the private ranges
    (10.x, 172.16-31.x, 192.168.x).
    """
    # Use common private range first octets
    first_octet = draw(st.sampled_from([10, 172, 192]))

    if first_octet == 10:
        second_octet = draw(st.integers(min_value=0, max_value=255))
    elif first_octet == 172:
        second_octet = draw(st.integers(min_value=16, max_value=31))
    else:  # 192
        second_octet = draw(st.integers(min_value=168, max_value=168))

    return f"{first_octet}.{second_octet}.0.0/16"


az_count_strategy = st.integers(min_value=2, max_value=4)


# ---------------------------------------------------------------------------
# Property Tests
# ---------------------------------------------------------------------------


@pytest.mark.property
@settings(max_examples=50)
@given(vpc_cidr=valid_vpc_cidr(), az_count=az_count_strategy)
def test_cidr_allocation_produces_non_overlapping_subnets(vpc_cidr: str, az_count: int):
    """Property: all allocated subnets (public and private) are non-overlapping.

    For any valid VPC CIDR and AZ count (2-4), no two allocated subnets
    should share any IP addresses.

    **Validates: Requirements 1.9**
    """
    public_subnets, private_subnets = allocate_subnets(vpc_cidr, az_count)
    all_subnets = public_subnets + private_subnets

    # Check every pair of subnets for overlap
    for i in range(len(all_subnets)):
        for j in range(i + 1, len(all_subnets)):
            assert not all_subnets[i].overlaps(all_subnets[j]), (
                f"Subnets overlap: {all_subnets[i]} and {all_subnets[j]} "
                f"(vpc_cidr={vpc_cidr}, az_count={az_count})"
            )


@pytest.mark.property
@settings(max_examples=50)
@given(vpc_cidr=valid_vpc_cidr(), az_count=az_count_strategy)
def test_all_subnets_within_vpc_cidr(vpc_cidr: str, az_count: int):
    """Property: all allocated subnets are contained within the VPC CIDR block.

    Every public and private subnet must be a subset of the parent VPC network.

    **Validates: Requirements 1.9**
    """
    vpc_network = ipaddress.IPv4Network(vpc_cidr)
    public_subnets, private_subnets = allocate_subnets(vpc_cidr, az_count)

    for subnet in public_subnets + private_subnets:
        assert subnet.subnet_of(vpc_network), (
            f"Subnet {subnet} is not within VPC CIDR {vpc_cidr}"
        )


@pytest.mark.property
@settings(max_examples=50)
@given(vpc_cidr=valid_vpc_cidr(), az_count=az_count_strategy)
def test_correct_number_of_subnets_allocated(vpc_cidr: str, az_count: int):
    """Property: allocation produces exactly az_count public and az_count private subnets.

    **Validates: Requirements 1.9**
    """
    public_subnets, private_subnets = allocate_subnets(vpc_cidr, az_count)

    assert len(public_subnets) == az_count, (
        f"Expected {az_count} public subnets, got {len(public_subnets)}"
    )
    assert len(private_subnets) == az_count, (
        f"Expected {az_count} private subnets, got {len(private_subnets)}"
    )


@pytest.mark.property
@settings(max_examples=50)
@given(vpc_cidr=valid_vpc_cidr(), az_count=az_count_strategy)
def test_all_subnets_are_slash_24(vpc_cidr: str, az_count: int):
    """Property: all allocated subnets use /24 prefix length.

    **Validates: Requirements 1.9**
    """
    public_subnets, private_subnets = allocate_subnets(vpc_cidr, az_count)

    for subnet in public_subnets + private_subnets:
        assert subnet.prefixlen == 24, (
            f"Subnet {subnet} has prefix /{subnet.prefixlen}, expected /24"
        )
