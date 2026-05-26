# src/transform/bronze/build_bronze.py
# Phase 2: Transform - Bronze Layer
# Creates a raw 1:1 copy of olist_oltp tables inside olist_olap.bronze schema

import pandas as pd
from sqlalchemy import text

from code.src.config import get_oltp_engine, get_olap_engine, create_database, create_schema, OLAP_DB


BRONZE_TABLES = [
    "customers",
    "geolocation",
    "leads_closed",
    "leads_qualified",
    "order_items",
    "order_payments",
    "order_reviews",
    "orders",
    "product_category_name_translation",
    "products",
    "sellers",
]


def build_bronze_layer():
    """
    Main entry point for Phase 2.

    Copies all tables from olist_oltp to olist_olap.bronze schema.
    - Creates the OLAP database if not exists
    - Creates 'bronze' schema
    - Copies each table with an added `_loaded_at` timestamp
    """
    print("\n" + "=" * 70)
    print("PHASE 2: TRANSFORM - Bronze Layer (Raw Copy)")
    print("=" * 70)

    # Ensure OLAP database exists
    print(f"\n  Creating database '{OLAP_DB}'...")
    create_database(OLAP_DB)

    olap_engine = get_olap_engine()
    oltp_engine = get_oltp_engine()

    # Create bronze schema
    print("\n  Creating schemas...")
    create_schema(olap_engine, "bronze")

    print("\n  Copying tables to bronze layer...")
    total_rows = 0

    for table in BRONZE_TABLES:
        # Read from OLTP
        df = pd.read_sql_table(table, oltp_engine)

        # Add metadata column
        df["_loaded_at"] = pd.Timestamp.now()

        row_count = len(df)
        total_rows += row_count

        # Write to OLAP bronze schema with explicit schema qualification
        # Create table manually to control schema placement
        with olap_engine.connect() as conn:
            conn.execute(text(f"DROP TABLE IF EXISTS bronze.{table} CASCADE"))
            conn.execute(text("COMMIT"))

        df.to_sql(
            name=table,
            con=olap_engine,
            schema="bronze",
            if_exists="replace",
            index=False,
        )

        print(f"    ✓ bronze.{table:<45} {row_count:>10,} rows")

    print(f"\n  {'─' * 50}")
    print(f"  TOTAL: {len(BRONZE_TABLES)} tables, {total_rows:,} rows copied")
    print(f"  Schema: olist_olap.bronze is ready")
    print("=" * 70)