"""Property-based tests for database schema migration logic.

**Validates: Requirements 3.10**

Uses Hypothesis to verify that migration logic produces valid SQL for all
supported migration operations (create table, add column, add index, add foreign key)
with randomly generated valid identifiers.
"""

import re

import pytest
from hypothesis import given, settings, strategies as st

from app.db.migration_logic import (
    AddColumn,
    AddForeignKey,
    AddIndex,
    ColumnDef,
    ColumnType,
    CreateTable,
    generate_sql,
)

# Strategy for valid SQL identifiers: lowercase letters followed by optional
# lowercase alphanumeric and underscores (1-30 chars total).
valid_identifier = st.from_regex(r"[a-z][a-z0-9_]{0,29}", fullmatch=True)

# Strategy for column types
column_types = st.sampled_from(list(ColumnType))


@st.composite
def column_def_strategy(draw):
    """Generate a valid ColumnDef with random identifier and type."""
    name = draw(valid_identifier)
    col_type = draw(column_types)
    nullable = draw(st.booleans())
    primary_key = draw(st.booleans())
    return ColumnDef(name=name, col_type=col_type, nullable=nullable, primary_key=primary_key)


@st.composite
def create_table_strategy(draw):
    """Generate a valid CreateTable operation with 1-5 columns."""
    table_name = draw(valid_identifier)
    columns = draw(st.lists(column_def_strategy(), min_size=1, max_size=5))
    return CreateTable(table_name=table_name, columns=columns)


@st.composite
def add_column_strategy(draw):
    """Generate a valid AddColumn operation."""
    table_name = draw(valid_identifier)
    column = draw(column_def_strategy())
    return AddColumn(table_name=table_name, column=column)


@st.composite
def add_index_strategy(draw):
    """Generate a valid AddIndex operation."""
    table_name = draw(valid_identifier)
    column_name = draw(valid_identifier)
    index_name = draw(valid_identifier)
    unique = draw(st.booleans())
    return AddIndex(
        table_name=table_name,
        column_name=column_name,
        index_name=index_name,
        unique=unique,
    )


@st.composite
def add_foreign_key_strategy(draw):
    """Generate a valid AddForeignKey operation."""
    table_name = draw(valid_identifier)
    column_name = draw(valid_identifier)
    reference_table = draw(valid_identifier)
    reference_column = draw(valid_identifier)
    constraint_name = draw(valid_identifier)
    return AddForeignKey(
        table_name=table_name,
        column_name=column_name,
        reference_table=reference_table,
        reference_column=reference_column,
        constraint_name=constraint_name,
    )


@st.composite
def any_migration_operation(draw):
    """Generate any valid migration operation."""
    return draw(
        st.one_of(
            create_table_strategy(),
            add_column_strategy(),
            add_index_strategy(),
            add_foreign_key_strategy(),
        )
    )


@pytest.mark.property
@settings(max_examples=50)
@given(op=create_table_strategy())
def test_create_table_produces_valid_sql(op):
    """Property: CREATE TABLE generates SQL with correct structure.

    For any valid table name and column definitions, the generated SQL must:
    - Start with CREATE TABLE
    - Contain the table name
    - Contain all column names and types
    - End with a semicolon

    **Validates: Requirements 3.10**
    """
    sql = generate_sql(op)

    assert sql.startswith("CREATE TABLE")
    assert f'"{op.table_name}"' in sql
    assert sql.endswith(";")

    for col in op.columns:
        assert f'"{col.name}"' in sql
        assert col.col_type.value in sql

    # Primary key columns must have PRIMARY KEY in their definition
    for col in op.columns:
        if col.primary_key:
            assert "PRIMARY KEY" in sql


@pytest.mark.property
@settings(max_examples=50)
@given(op=add_column_strategy())
def test_add_column_produces_valid_sql(op):
    """Property: ADD COLUMN generates SQL with correct ALTER TABLE structure.

    For any valid table name and column definition, the generated SQL must:
    - Start with ALTER TABLE
    - Contain ADD COLUMN
    - Include the table name, column name, and column type
    - End with a semicolon

    **Validates: Requirements 3.10**
    """
    sql = generate_sql(op)

    assert sql.startswith("ALTER TABLE")
    assert "ADD COLUMN" in sql
    assert f'"{op.table_name}"' in sql
    assert f'"{op.column.name}"' in sql
    assert op.column.col_type.value in sql
    assert sql.endswith(";")

    if not op.column.nullable:
        assert "NOT NULL" in sql


@pytest.mark.property
@settings(max_examples=50)
@given(op=add_index_strategy())
def test_add_index_produces_valid_sql(op):
    """Property: ADD INDEX generates SQL with correct CREATE INDEX structure.

    For any valid table name, column name, and index name, the generated SQL must:
    - Start with CREATE INDEX or CREATE UNIQUE INDEX
    - Contain the index name, table name, and column name
    - End with a semicolon

    **Validates: Requirements 3.10**
    """
    sql = generate_sql(op)

    if op.unique:
        assert sql.startswith("CREATE UNIQUE INDEX")
    else:
        assert sql.startswith("CREATE INDEX")

    assert f'"{op.index_name}"' in sql
    assert f'ON "{op.table_name}"' in sql
    assert f'("{op.column_name}")' in sql
    assert sql.endswith(";")


@pytest.mark.property
@settings(max_examples=50)
@given(op=add_foreign_key_strategy())
def test_add_foreign_key_produces_valid_sql(op):
    """Property: ADD FOREIGN KEY generates SQL with correct ALTER TABLE structure.

    For any valid table, column, reference table, reference column, and constraint name,
    the generated SQL must:
    - Start with ALTER TABLE
    - Contain ADD CONSTRAINT, FOREIGN KEY, and REFERENCES
    - Include all identifier names
    - End with a semicolon

    **Validates: Requirements 3.10**
    """
    sql = generate_sql(op)

    assert sql.startswith("ALTER TABLE")
    assert "ADD CONSTRAINT" in sql
    assert "FOREIGN KEY" in sql
    assert "REFERENCES" in sql
    assert f'"{op.table_name}"' in sql
    assert f'"{op.column_name}"' in sql
    assert f'"{op.reference_table}"' in sql
    assert f'"{op.reference_column}"' in sql
    assert f'"{op.constraint_name}"' in sql
    assert sql.endswith(";")


@pytest.mark.property
@settings(max_examples=50)
@given(op=any_migration_operation())
def test_all_operations_produce_terminated_sql(op):
    """Property: ALL migration operations produce SQL ending with a semicolon.

    For any valid migration operation, the generated SQL must be a non-empty
    string that ends with a semicolon statement terminator.

    **Validates: Requirements 3.10**
    """
    sql = generate_sql(op)

    assert isinstance(sql, str)
    assert len(sql) > 0
    assert sql.endswith(";")


@pytest.mark.property
@settings(max_examples=50)
@given(op=any_migration_operation())
def test_all_operations_produce_sql_without_unquoted_identifiers(op):
    """Property: ALL identifiers in generated SQL are properly quoted.

    For any valid migration operation, all user-supplied identifiers must
    be wrapped in double quotes to prevent SQL injection and keyword conflicts.

    **Validates: Requirements 3.10**
    """
    sql = generate_sql(op)

    # Extract all quoted identifiers from the SQL
    quoted_identifiers = re.findall(r'"([^"]+)"', sql)

    # All identifiers should be properly quoted - verify key identifiers are present
    if isinstance(op, CreateTable):
        assert op.table_name in quoted_identifiers
        for col in op.columns:
            assert col.name in quoted_identifiers
    elif isinstance(op, AddColumn):
        assert op.table_name in quoted_identifiers
        assert op.column.name in quoted_identifiers
    elif isinstance(op, AddIndex):
        assert op.table_name in quoted_identifiers
        assert op.column_name in quoted_identifiers
        assert op.index_name in quoted_identifiers
    elif isinstance(op, AddForeignKey):
        assert op.table_name in quoted_identifiers
        assert op.column_name in quoted_identifiers
        assert op.reference_table in quoted_identifiers
        assert op.reference_column in quoted_identifiers
        assert op.constraint_name in quoted_identifiers
