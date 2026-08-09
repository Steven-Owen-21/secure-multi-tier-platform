"""Migration logic for generating SQL statements from migration operations.

This module provides a pure function that generates SQL strings for common
database migration operations: CREATE TABLE, ALTER TABLE ADD COLUMN,
CREATE INDEX, and ALTER TABLE ADD FOREIGN KEY.

Used by Alembic migration scripts and validated with property-based tests.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Union


class ColumnType(Enum):
    """Supported column types for migration operations."""

    INTEGER = "INTEGER"
    TEXT = "TEXT"
    VARCHAR_255 = "VARCHAR(255)"
    BOOLEAN = "BOOLEAN"
    TIMESTAMP = "TIMESTAMP"
    UUID = "UUID"


@dataclass(frozen=True)
class ColumnDef:
    """Column definition for CREATE TABLE operations."""

    name: str
    col_type: ColumnType
    nullable: bool = True
    primary_key: bool = False


@dataclass(frozen=True)
class CreateTable:
    """Migration operation: create a new table."""

    table_name: str
    columns: list[ColumnDef]


@dataclass(frozen=True)
class AddColumn:
    """Migration operation: add a column to an existing table."""

    table_name: str
    column: ColumnDef


@dataclass(frozen=True)
class AddIndex:
    """Migration operation: add an index on a table column."""

    table_name: str
    column_name: str
    index_name: str
    unique: bool = False


@dataclass(frozen=True)
class AddForeignKey:
    """Migration operation: add a foreign key constraint."""

    table_name: str
    column_name: str
    reference_table: str
    reference_column: str
    constraint_name: str


MigrationOperation = Union[CreateTable, AddColumn, AddIndex, AddForeignKey]


def generate_sql(operation: MigrationOperation) -> str:
    """Generate valid SQL for a migration operation.

    Args:
        operation: One of CreateTable, AddColumn, AddIndex, or AddForeignKey.

    Returns:
        A valid SQL statement string for the given operation.

    Raises:
        ValueError: If the operation type is not supported.
    """
    if isinstance(operation, CreateTable):
        return _generate_create_table(operation)
    elif isinstance(operation, AddColumn):
        return _generate_add_column(operation)
    elif isinstance(operation, AddIndex):
        return _generate_add_index(operation)
    elif isinstance(operation, AddForeignKey):
        return _generate_add_foreign_key(operation)
    else:
        raise ValueError(f"Unsupported migration operation: {type(operation)}")


def _generate_create_table(op: CreateTable) -> str:
    """Generate CREATE TABLE SQL."""
    col_defs = []
    for col in op.columns:
        parts = [f'"{col.name}" {col.col_type.value}']
        if col.primary_key:
            parts.append("PRIMARY KEY")
        if not col.nullable and not col.primary_key:
            parts.append("NOT NULL")
        col_defs.append(" ".join(parts))

    columns_sql = ",\n  ".join(col_defs)
    return f'CREATE TABLE "{op.table_name}" (\n  {columns_sql}\n);'


def _generate_add_column(op: AddColumn) -> str:
    """Generate ALTER TABLE ADD COLUMN SQL."""
    col = op.column
    parts = [f'ALTER TABLE "{op.table_name}" ADD COLUMN "{col.name}" {col.col_type.value}']
    if not col.nullable:
        parts.append("NOT NULL")
    return " ".join(parts) + ";"


def _generate_add_index(op: AddIndex) -> str:
    """Generate CREATE INDEX SQL."""
    unique_clause = "UNIQUE " if op.unique else ""
    return (
        f'CREATE {unique_clause}INDEX "{op.index_name}" '
        f'ON "{op.table_name}" ("{op.column_name}");'
    )


def _generate_add_foreign_key(op: AddForeignKey) -> str:
    """Generate ALTER TABLE ADD FOREIGN KEY SQL."""
    return (
        f'ALTER TABLE "{op.table_name}" ADD CONSTRAINT "{op.constraint_name}" '
        f'FOREIGN KEY ("{op.column_name}") '
        f'REFERENCES "{op.reference_table}" ("{op.reference_column}");'
    )
