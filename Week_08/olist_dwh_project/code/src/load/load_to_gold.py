# src/load/load_to_gold.py
# Phase 6: Load - Write dimension and fact DataFrames to olist_olap

import pandas as pd
from sqlalchemy import text

from code.src.config import get_olap_engine, create_schema


def create_gold_schemas(engine):
    """
    Create the 'dimensions' and 'facts' schemas in olist_olap.

    Parameters
    ----------
    engine : sqlalchemy.engine.Engine
        Connected engine to olist_olap.
    """
    print("\n  Creating gold schemas...")
    create_schema(engine, "dimensions")
    create_schema(engine, "facts")


def write_table(df: pd.DataFrame, schema: str, table_name: str, engine, pk_col: str = None):
    """
    Write a DataFrame to a PostgreSQL table and optionally set primary key.

    Parameters
    ----------
    df : pd.DataFrame
        Data to write.
    schema : str
        Target schema name ('dimensions' or 'facts').
    table_name : str
        Target table name.
    engine : sqlalchemy.engine.Engine
        Connected engine.
    pk_col : str, optional
        Column name to set as primary key.
    """
    # Drop existing table for idempotent reload
    with engine.connect() as conn:
        conn.execute(text(f"DROP TABLE IF EXISTS {schema}.{table_name} CASCADE"))
        conn.execute(text("COMMIT"))

    # Write DataFrame
    df.to_sql(
        name=table_name,
        con=engine,
        schema=schema,
        if_exists="replace",
        index=False,
    )

    # Set primary key if specified
    if pk_col:
        with engine.connect() as conn:
            conn.execute(
                text(
                    f"ALTER TABLE {schema}.{table_name} "
                    f"ADD PRIMARY KEY ({pk_col})"
                )
            )
            conn.execute(text("COMMIT"))


def create_indexes(engine):
    """
    Create performance indexes on fact table foreign key columns.

    Parameters
    ----------
    engine : sqlalchemy.engine.Engine
    """
    print("\n  Creating indexes...")

    index_definitions = [
        # Fact_Sales indexes
        ("facts", "fact_sales", "customer_key"),
        ("facts", "fact_sales", "seller_key"),
        ("facts", "fact_sales", "product_key"),
        ("facts", "fact_sales", "purchase_date_key"),
        ("facts", "fact_sales", "delivered_customer_date_key"),
        ("facts", "fact_sales", "order_status_key"),
        # Fact_Payments indexes
        ("facts", "fact_payments", "customer_key"),
        ("facts", "fact_payments", "payment_date_key"),
        ("facts", "fact_payments", "payment_type_key"),
        # Fact_Reviews indexes
        ("facts", "fact_reviews", "customer_key"),
        ("facts", "fact_reviews", "review_creation_date_key"),
        # Fact_Seller_Acquisition indexes
        ("facts", "fact_seller_acquisition", "lead_key"),
        ("facts", "fact_seller_acquisition", "seller_key"),
        ("facts", "fact_seller_acquisition", "lead_source_key"),
        # Fact_Order_Events indexes
        ("facts", "fact_order_events", "customer_key"),
        ("facts", "fact_order_events", "seller_key"),
        ("facts", "fact_order_events", "event_date_key"),
        ("facts", "fact_order_events", "event_type_key"),
        # Fact_Sales location indexes (new)
        ("facts", "fact_sales", "customer_location_key"),
        ("facts", "fact_sales", "seller_location_key"),
    ]

    with engine.connect() as conn:
        for schema, table, column in index_definitions:
            idx_name = f"idx_{table}_{column}"
            sql = (
                f"CREATE INDEX IF NOT EXISTS {idx_name} "
                f"ON {schema}.{table} ({column})"
            )
            conn.execute(text(sql))
        conn.execute(text("COMMIT"))

    print(f"    ✓ {len(index_definitions)} indexes created")


def load_all_to_database(dimensions: dict, facts: dict):
    """
    Main entry point for Phase 6.

    Writes all dimension and fact DataFrames to olist_olap database.
    Sets primary keys and creates performance indexes.

    Parameters
    ----------
    dimensions : dict
        Dictionary of dimension DataFrames from Phase 4.
    facts : dict
        Dictionary of fact DataFrames from Phase 5.
    """
    print("\n" + "=" * 70)
    print("PHASE 6: LOAD - Write to olist_olap (Dimensions + Facts)")
    print("=" * 70)

    engine = get_olap_engine()

    # Create schemas
    create_gold_schemas(engine)

    # ------------------------------------------------------------------
    # Write dimensions
    # ------------------------------------------------------------------
    print("\n  Writing dimensions...")

    dim_pk_map = {
        "dim_date": "date_key",
        "dim_time": "time_key",
        "dim_payment_type": "payment_type_key",
        "dim_order_status": "order_status_key",
        "dim_event_type": "event_type_key",
        "dim_lead_source": "lead_source_key",
        "dim_location": "location_key",
        "dim_customer": "customer_key",
        "dim_seller": "seller_key",
        "dim_product": "product_key",
        "dim_lead": "lead_key",
    }

    for dim_name, df in dimensions.items():
        pk_col = dim_pk_map.get(dim_name)
        write_table(df, "dimensions", dim_name, engine, pk_col)
        print(f"    ✓ dimensions.{dim_name:<30} {len(df):>10,} rows")

    # ------------------------------------------------------------------
    # Write facts
    # ------------------------------------------------------------------
    print("\n  Writing facts...")

    fact_pk_map = {
        "fact_sales": "sales_key",
        "fact_payments": "payment_key",
        "fact_reviews": "review_key",
        "fact_seller_acquisition": "acquisition_key",
        "fact_order_events": "event_key",
    }

    for fact_name, df in facts.items():
        pk_col = fact_pk_map.get(fact_name)
        write_table(df, "facts", fact_name, engine, pk_col)
        print(f"    ✓ facts.{fact_name:<35} {len(df):>10,} rows")

    # ------------------------------------------------------------------
    # Create indexes
    # ------------------------------------------------------------------
    create_indexes(engine)

    total_rows = sum(len(df) for df in dimensions.values()) + sum(
        len(df) for df in facts.values()
    )

    print(f"\n  {'─' * 50}")
    print(f"  TOTAL: {len(dimensions)} dimensions + {len(facts)} facts")
    print(f"  Rows written: {total_rows:,}")
    print(f"  Database: olist_olap is ready for analytics")
    print("=" * 70)

    # Print index summary
    index_count = 20
    print(f"\n  ✓ {index_count} B-tree indexes created for query performance optimization")