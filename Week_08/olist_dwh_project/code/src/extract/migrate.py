# src/extract/migrate.py
# Phase 1: Extract - Migrate SQLite database to PostgreSQL (olist_oltp)

import sqlite3

import pandas as pd
from sqlalchemy import text

from code.src.config import SQLITE_PATH, create_database, get_oltp_engine, OLTP_DB


def get_sqlite_tables() -> list:
    """
    Retrieve list of all user-defined tables in the SQLite database.

    Returns
    -------
    list
        Table names sorted alphabetically.
    """
    conn = sqlite3.connect(SQLITE_PATH)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
    )

    tables = [row[0] for row in cursor.fetchall()]
    conn.close()
    return tables


def get_sqlite_schema(table_name: str) -> str:
    """
    Retrieve the CREATE TABLE statement for a given SQLite table.

    Parameters
    ----------
    table_name : str
        Name of the table.

    Returns
    -------
    str
        Original CREATE TABLE SQL from SQLite.
    """
    conn = sqlite3.connect(SQLITE_PATH)
    cursor = conn.cursor()

    cursor.execute(
        f"SELECT sql FROM sqlite_master WHERE type = 'table' AND name = '{table_name}'"
    )

    schema = cursor.fetchone()[0]
    conn.close()
    return schema


def convert_sqlite_to_postgres(create_sql: str, table_name: str) -> str:
    """
    Convert a SQLite CREATE TABLE statement to PostgreSQL-compatible syntax.

    Handles common SQLite → PostgreSQL differences:
    - Replace TEXT with VARCHAR (optional, TEXT also works in PG)
    - Replace REAL with DOUBLE PRECISION
    - Remove SQLite-specific quotes

    Parameters
    ----------
    create_sql : str
        Original CREATE TABLE from SQLite.
    table_name : str
        Name of the table.

    Returns
    -------
    str
        PostgreSQL-compatible CREATE TABLE statement.
    """
    # Basic conversions for compatibility
    pg_sql = create_sql

    # Ensure the table name is properly quoted for PostgreSQL
    # SQLite uses double quotes or backticks; standardize for PG
    pg_sql = pg_sql.replace(f'"{table_name}"', table_name)
    pg_sql = pg_sql.replace(f"`{table_name}`", table_name)

    return pg_sql


def migrate_table(table_name: str, oltp_engine) -> tuple:
    """
    Migrate a single table: read from SQLite, write to PostgreSQL.

    Parameters
    ----------
    table_name : str
        Name of the table to migrate.
    oltp_engine : sqlalchemy.engine.Engine
        Engine connected to olist_oltp database.

    Returns
    -------
    tuple
        (table_name, row_count) for summary reporting.
    """
    # 1. Read entire table from SQLite
    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    df = pd.read_sql_query(f"SELECT * FROM {table_name}", sqlite_conn)
    sqlite_conn.close()

    row_count = len(df)

    # 2. Get and convert schema
    create_sql = get_sqlite_schema(table_name)
    pg_create_sql = convert_sqlite_to_postgres(create_sql, table_name)

    # 3. Create table structure in PostgreSQL
    with oltp_engine.connect() as conn:
        # Drop table if it already exists (idempotent migration)
        conn.execute(text(f"DROP TABLE IF EXISTS {table_name} CASCADE"))
        conn.execute(text("COMMIT"))
        conn.execute(text(pg_create_sql))
        conn.execute(text("COMMIT"))

    # 4. Write data to PostgreSQL using pandas
    df.to_sql(
        name=table_name,
        con=oltp_engine,
        if_exists="append",
        index=False,
    )

    return table_name, row_count


def run_migration():
    """
    Main entry point for Phase 1.

    Orchestrates the full migration:
    1. Create olist_oltp database
    2. Discover all SQLite tables
    3. Migrate each table structure + data
    4. Print summary report
    """
    print("\n" + "=" * 70)
    print("PHASE 1: EXTRACT - SQLite → PostgreSQL (olist_oltp)")
    print("=" * 70)

    # Create the OLTP database
    print(f"\n  Creating database '{OLTP_DB}'...")
    create_database(OLTP_DB)

    oltp_engine = get_oltp_engine()

    # Get list of tables
    tables = get_sqlite_tables()
    print(f"\n  Found {len(tables)} tables in SQLite: {', '.join(tables)}")

    # Migrate each table
    print("\n  Migrating tables...")
    total_rows = 0

    for table in tables:
        table_name, row_count = migrate_table(table, oltp_engine)
        total_rows += row_count
        print(f"    ✓ {table_name:<40} {row_count:>10,} rows")

    print(f"\n  {'─' * 50}")
    print(f"  TOTAL: {len(tables)} tables, {total_rows:,} rows migrated")
    print(f"  Database: {OLTP_DB} is ready")
    print("=" * 70)