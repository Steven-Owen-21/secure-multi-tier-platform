"""Terraform variable validation logic.

Mirrors the validation rules defined in infrastructure/variables.tf for the
root module's configurable variables. Each validation function returns a tuple
of (is_valid, error_message) to allow property-based tests to verify that
invalid inputs are correctly rejected with appropriate error messages.

Validated variables:
    - vpc_cidr: Must be a valid /16 CIDR block
    - az_count: Must be between 2 and 4
    - ecs_min_capacity: Must be at least 1
    - ecs_max_capacity: Must be at least 2
    - db_backup_retention_days: Must be between 1 and 35
    - app_port: Must be between 1 and 65535
    - waf_rate_limit: Must be between 100 and 20,000,000
    - waf_body_size_limit: Must be between 1024 and 65536
"""

import ipaddress
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ValidationResult:
    """Result of a Terraform variable validation check."""

    valid: bool
    error_message: Optional[str] = None


def validate_vpc_cidr(cidr: str) -> ValidationResult:
    """Validate that a VPC CIDR is a valid /16 CIDR block.

    Mirrors the Terraform validation:
        condition = can(cidrhost(var.vpc_cidr, 0)) && endswith(var.vpc_cidr, "/16")

    Args:
        cidr: CIDR block string to validate.

    Returns:
        ValidationResult indicating whether the CIDR is valid.
    """
    if not isinstance(cidr, str):
        return ValidationResult(
            valid=False,
            error_message="vpc_cidr must be a valid /16 CIDR block.",
        )

    if not cidr.endswith("/16"):
        return ValidationResult(
            valid=False,
            error_message="vpc_cidr must be a valid /16 CIDR block.",
        )

    try:
        network = ipaddress.ip_network(cidr, strict=False)
        # Ensure it's IPv4 and exactly /16
        if not isinstance(network, ipaddress.IPv4Network):
            return ValidationResult(
                valid=False,
                error_message="vpc_cidr must be a valid /16 CIDR block.",
            )
        if network.prefixlen != 16:
            return ValidationResult(
                valid=False,
                error_message="vpc_cidr must be a valid /16 CIDR block.",
            )
    except (ValueError, TypeError):
        return ValidationResult(
            valid=False,
            error_message="vpc_cidr must be a valid /16 CIDR block.",
        )

    return ValidationResult(valid=True)


def validate_az_count(az_count: int) -> ValidationResult:
    """Validate that AZ count is between 2 and 4.

    Mirrors the Terraform validation:
        condition = var.az_count >= 2 && var.az_count <= 4

    Args:
        az_count: Number of availability zones.

    Returns:
        ValidationResult indicating whether the value is valid.
    """
    if not isinstance(az_count, int) or isinstance(az_count, bool):
        return ValidationResult(
            valid=False,
            error_message="az_count must be between 2 and 4.",
        )

    if az_count < 2 or az_count > 4:
        return ValidationResult(
            valid=False,
            error_message="az_count must be between 2 and 4.",
        )

    return ValidationResult(valid=True)


def validate_ecs_min_capacity(min_capacity: int) -> ValidationResult:
    """Validate that ECS minimum capacity is at least 1.

    Mirrors the Terraform validation:
        condition = var.ecs_min_capacity >= 1

    Args:
        min_capacity: Minimum number of ECS tasks.

    Returns:
        ValidationResult indicating whether the value is valid.
    """
    if not isinstance(min_capacity, int) or isinstance(min_capacity, bool):
        return ValidationResult(
            valid=False,
            error_message="ecs_min_capacity must be at least 1.",
        )

    if min_capacity < 1:
        return ValidationResult(
            valid=False,
            error_message="ecs_min_capacity must be at least 1.",
        )

    return ValidationResult(valid=True)


def validate_ecs_max_capacity(max_capacity: int) -> ValidationResult:
    """Validate that ECS maximum capacity is at least 2.

    Mirrors the Terraform validation:
        condition = var.ecs_max_capacity >= 2

    Args:
        max_capacity: Maximum number of ECS tasks.

    Returns:
        ValidationResult indicating whether the value is valid.
    """
    if not isinstance(max_capacity, int) or isinstance(max_capacity, bool):
        return ValidationResult(
            valid=False,
            error_message="ecs_max_capacity must be at least 2.",
        )

    if max_capacity < 2:
        return ValidationResult(
            valid=False,
            error_message="ecs_max_capacity must be at least 2.",
        )

    return ValidationResult(valid=True)


def validate_db_backup_retention_days(retention_days: int) -> ValidationResult:
    """Validate that DB backup retention is between 1 and 35 days.

    Mirrors the Terraform validation:
        condition = var.db_backup_retention_days >= 1 && var.db_backup_retention_days <= 35

    Args:
        retention_days: Number of days to retain backups.

    Returns:
        ValidationResult indicating whether the value is valid.
    """
    if not isinstance(retention_days, int) or isinstance(retention_days, bool):
        return ValidationResult(
            valid=False,
            error_message="db_backup_retention_days must be between 1 and 35.",
        )

    if retention_days < 1 or retention_days > 35:
        return ValidationResult(
            valid=False,
            error_message="db_backup_retention_days must be between 1 and 35.",
        )

    return ValidationResult(valid=True)


def validate_app_port(port: int) -> ValidationResult:
    """Validate that app port is between 1 and 65535.

    Mirrors the Terraform validation:
        condition = var.app_port > 0 && var.app_port <= 65535

    Args:
        port: Port number for the application service.

    Returns:
        ValidationResult indicating whether the value is valid.
    """
    if not isinstance(port, int) or isinstance(port, bool):
        return ValidationResult(
            valid=False,
            error_message="app_port must be between 1 and 65535.",
        )

    if port < 1 or port > 65535:
        return ValidationResult(
            valid=False,
            error_message="app_port must be between 1 and 65535.",
        )

    return ValidationResult(valid=True)


def validate_waf_rate_limit(rate_limit: int) -> ValidationResult:
    """Validate that WAF rate limit is between 100 and 20,000,000.

    Mirrors the Terraform validation:
        condition = var.waf_rate_limit >= 100 && var.waf_rate_limit <= 20000000

    Args:
        rate_limit: Maximum requests per 5-minute window per source IP.

    Returns:
        ValidationResult indicating whether the value is valid.
    """
    if not isinstance(rate_limit, int) or isinstance(rate_limit, bool):
        return ValidationResult(
            valid=False,
            error_message="waf_rate_limit must be between 100 and 20,000,000.",
        )

    if rate_limit < 100 or rate_limit > 20_000_000:
        return ValidationResult(
            valid=False,
            error_message="waf_rate_limit must be between 100 and 20,000,000.",
        )

    return ValidationResult(valid=True)


def validate_waf_body_size_limit(body_size_limit: int) -> ValidationResult:
    """Validate that WAF body size limit is between 1024 and 65536 bytes.

    Mirrors the Terraform validation:
        condition = var.waf_body_size_limit >= 1024 && var.waf_body_size_limit <= 65536

    Args:
        body_size_limit: Maximum request body size in bytes.

    Returns:
        ValidationResult indicating whether the value is valid.
    """
    if not isinstance(body_size_limit, int) or isinstance(body_size_limit, bool):
        return ValidationResult(
            valid=False,
            error_message="waf_body_size_limit must be between 1024 and 65536 bytes.",
        )

    if body_size_limit < 1024 or body_size_limit > 65536:
        return ValidationResult(
            valid=False,
            error_message="waf_body_size_limit must be between 1024 and 65536 bytes.",
        )

    return ValidationResult(valid=True)
