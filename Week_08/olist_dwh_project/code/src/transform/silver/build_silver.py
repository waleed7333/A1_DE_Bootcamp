# src/transform/silver/build_silver.py
# Phase 3: Transform - Silver Layer
# Cleans, standardizes, and merges data from bronze layer

import pandas as pd
from sqlalchemy import text

from code.src.config import get_olap_engine, create_schema


def clean_geolocation(engine):
    """
    Clean and aggregate geolocation data.

    - Converts scientific notation coordinates to proper decimals
    - Standardizes city names (lowercase, no accents)
    - Aggregates by zip_code_prefix to remove duplicates

    Parameters
    ----------
    engine : sqlalchemy.engine.Engine
        Connected engine to olist_olap database.

    Returns
    -------
    pd.DataFrame
        Cleaned geolocation data aggregated at zip code level.
    """
    print("    → Cleaning geolocation...")

    df = pd.read_sql_table("geolocation", engine, schema="bronze")

    # Convert scientific notation floats to proper format
    df["geolocation_lat"] = pd.to_numeric(df["geolocation_lat"], errors="coerce")
    df["geolocation_lng"] = pd.to_numeric(df["geolocation_lng"], errors="coerce")

    # Standardize city names: lowercase and strip whitespace
    df["geolocation_city"] = (
        df["geolocation_city"]
        .str.lower()
        .str.normalize("NFKD")
        .str.encode("ascii", errors="ignore")
        .str.decode("utf-8")
        .str.strip()
    )

    # Aggregate: one row per zip code prefix
    df_agg = (
        df.groupby(
            ["geolocation_zip_code_prefix", "geolocation_city", "geolocation_state"],
        )
        .agg(
            geolocation_lat=("geolocation_lat", "mean"),
            geolocation_lng=("geolocation_lng", "mean"),
        )
        .reset_index()
    )

    # Rename columns for silver layer consistency
    df_agg.rename(
        columns={
            "geolocation_zip_code_prefix": "zip_code_prefix",
            "geolocation_city": "city",
            "geolocation_state": "state",
            "geolocation_lat": "latitude",
            "geolocation_lng": "longitude",
        },
        inplace=True,
    )

    print(f"      Aggregated from {len(df):,} rows to {len(df_agg):,} unique zip codes")
    return df_agg


def clean_customers(engine):
    """
    Clean customers table.

    Parameters
    ----------
    engine : sqlalchemy.engine.Engine

    Returns
    -------
    pd.DataFrame
        Cleaned customers data.
    """
    print("    → Cleaning customers...")
    df = pd.read_sql_table("customers", engine, schema="bronze")

    # Standardize city and state to lowercase
    df["customer_city"] = df["customer_city"].str.lower().str.strip()
    df["customer_state"] = df["customer_state"].str.upper().str.strip()

    # Remove rows with critical NULL values
    df = df.dropna(subset=["customer_id", "customer_unique_id"])

    return df


def clean_sellers(engine):
    """
    Clean sellers table.

    Parameters
    ----------
    engine : sqlalchemy.engine.Engine

    Returns
    -------
    pd.DataFrame
        Cleaned sellers data.
    """
    print("    → Cleaning sellers...")
    df = pd.read_sql_table("sellers", engine, schema="bronze")

    df["seller_city"] = df["seller_city"].str.lower().str.strip()
    df["seller_state"] = df["seller_state"].str.upper().str.strip()

    df = df.dropna(subset=["seller_id"])

    return df


def clean_products(engine):
    """
    Clean products table and join with category name translations.

    Parameters
    ----------
    engine : sqlalchemy.engine.Engine

    Returns
    -------
    pd.DataFrame
        Cleaned products with English category names.
    """
    print("    → Cleaning products...")

    df_products = pd.read_sql_table("products", engine, schema="bronze")
    df_translation = pd.read_sql_table(
        "product_category_name_translation", engine, schema="bronze"
    )

    # Join with translation table to get English category names
    df = df_products.merge(
        df_translation,
        on="product_category_name",
        how="left",
    )

    # Fill missing English names with original Portuguese name
    df["product_category_name_english"] = df["product_category_name_english"].fillna(
        df["product_category_name"]
    )

    # Rename columns for clarity
    df.rename(
        columns={
            "product_name_lenght": "product_name_length",
            "product_description_lenght": "product_description_length",
        },
        inplace=True,
    )

    # Fill numeric columns with 0 where NULL
    numeric_cols = [
        "product_name_length",
        "product_description_length",
        "product_photos_qty",
        "product_weight_g",
        "product_length_cm",
        "product_height_cm",
        "product_width_cm",
    ]
    for col in numeric_cols:
        df[col] = df[col].fillna(0)

    return df


def clean_orders(engine):
    """
    Clean orders table - convert timestamp columns to datetime.

    Parameters
    ----------
    engine : sqlalchemy.engine.Engine

    Returns
    -------
    pd.DataFrame
        Cleaned orders with proper datetime columns.
    """
    print("    → Cleaning orders...")

    df = pd.read_sql_table("orders", engine, schema="bronze")

    # List of timestamp columns to convert
    timestamp_cols = [
        "order_purchase_timestamp",
        "order_approved_at",
        "order_delivered_carrier_date",
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ]

    for col in timestamp_cols:
        df[col] = pd.to_datetime(df[col], errors="coerce")

    return df


def clean_order_items(engine):
    """
    Clean order_items table.

    Parameters
    ----------
    engine : sqlalchemy.engine.Engine

    Returns
    -------
    pd.DataFrame
        Cleaned order items.
    """
    print("    → Cleaning order_items...")

    df = pd.read_sql_table("order_items", engine, schema="bronze")

    # Convert shipping_limit_date to datetime
    df["shipping_limit_date"] = pd.to_datetime(df["shipping_limit_date"], errors="coerce")

    # Ensure numeric columns are proper type
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df["freight_value"] = pd.to_numeric(df["freight_value"], errors="coerce")

    return df


def clean_order_payments(engine):
    """
    Clean order_payments table.

    Parameters
    ----------
    engine : sqlalchemy.engine.Engine

    Returns
    -------
    pd.DataFrame
        Cleaned order payments.
    """
    print("    → Cleaning order_payments...")
    df = pd.read_sql_table("order_payments", engine, schema="bronze")

    df["payment_value"] = pd.to_numeric(df["payment_value"], errors="coerce")
    df["payment_installments"] = pd.to_numeric(df["payment_installments"], errors="coerce").fillna(1).astype(int)

    return df


def clean_order_reviews(engine):
    """
    Clean order_reviews table.

    Parameters
    ----------
    engine : sqlalchemy.engine.Engine

    Returns
    -------
    pd.DataFrame
        Cleaned order reviews.
    """
    print("    → Cleaning order_reviews...")

    df = pd.read_sql_table("order_reviews", engine, schema="bronze")

    df["review_creation_date"] = pd.to_datetime(df["review_creation_date"], errors="coerce")
    df["review_answer_timestamp"] = pd.to_datetime(df["review_answer_timestamp"], errors="coerce")

    return df


def build_leads(engine):
    """
    Merge leads_qualified and leads_closed into a single leads table.

    Parameters
    ----------
    engine : sqlalchemy.engine.Engine

    Returns
    -------
    pd.DataFrame
        Combined and cleaned leads data.
    """
    print("    → Building combined leads table...")

    df_qualified = pd.read_sql_table("leads_qualified", engine, schema="bronze")
    df_closed = pd.read_sql_table("leads_closed", engine, schema="bronze")

    # Merge qualified and closed on mql_id
    df = df_qualified.merge(df_closed, on="mql_id", how="left")

    # Convert date columns
    df["first_contact_date"] = pd.to_datetime(df["first_contact_date"], errors="coerce")
    df["won_date"] = pd.to_datetime(df["won_date"], errors="coerce")

    # Drop redundant _loaded_at columns from both source tables
    cols_to_drop = [col for col in df.columns if col.endswith("_loaded_at")]
    df = df.drop(columns=cols_to_drop, errors="ignore")

    return df


def write_silver_table(df, table_name, engine):
    """
    Write a DataFrame to the silver schema.

    Parameters
    ----------
    df : pd.DataFrame
        Data to write.
    table_name : str
        Name of the target table.
    engine : sqlalchemy.engine.Engine
        Connected engine.
    """
    with engine.connect() as conn:
        conn.execute(text(f"DROP TABLE IF EXISTS silver.{table_name} CASCADE"))
        conn.execute(text("COMMIT"))

    df.to_sql(
        name=table_name,
        con=engine,
        schema="silver",
        if_exists="replace",
        index=False,
    )


def build_silver_layer():
    """
    Main entry point for Phase 3.

    Orchestrates the cleaning of all tables:
    1. Creates 'silver' schema
    2. Cleans each table individually
    3. Writes cleaned data to olist_olap.silver
    """
    print("\n" + "=" * 70)
    print("PHASE 3: TRANSFORM - Silver Layer (Clean & Standardize)")
    print("=" * 70)

    engine = get_olap_engine()

    # Create silver schema
    print("\n  Creating schema...")
    create_schema(engine, "silver")

    # Clean and write each table
    print("\n  Cleaning tables...")

    # Geolocation
    df_geo = clean_geolocation(engine)
    write_silver_table(df_geo, "geolocation", engine)
    print(f"    ✓ silver.geolocation{' ' * 27} {len(df_geo):>10,} rows")

    # Customers
    df_cust = clean_customers(engine)
    write_silver_table(df_cust, "customers", engine)
    print(f"    ✓ silver.customers{' ' * 29} {len(df_cust):>10,} rows")

    # Sellers
    df_sell = clean_sellers(engine)
    write_silver_table(df_sell, "sellers", engine)
    print(f"    ✓ silver.sellers{' ' * 31} {len(df_sell):>10,} rows")

    # Products
    df_prod = clean_products(engine)
    write_silver_table(df_prod, "products", engine)
    print(f"    ✓ silver.products{' ' * 30} {len(df_prod):>10,} rows")

    # Orders
    df_orders = clean_orders(engine)
    write_silver_table(df_orders, "orders", engine)
    print(f"    ✓ silver.orders{' ' * 32} {len(df_orders):>10,} rows")

    # Order Items
    df_items = clean_order_items(engine)
    write_silver_table(df_items, "order_items", engine)
    print(f"    ✓ silver.order_items{' ' * 27} {len(df_items):>10,} rows")

    # Order Payments
    df_pay = clean_order_payments(engine)
    write_silver_table(df_pay, "order_payments", engine)
    print(f"    ✓ silver.order_payments{' ' * 24} {len(df_pay):>10,} rows")

    # Order Reviews
    df_rev = clean_order_reviews(engine)
    write_silver_table(df_rev, "order_reviews", engine)
    print(f"    ✓ silver.order_reviews{' ' * 24} {len(df_rev):>10,} rows")

    # Leads (merged)
    df_leads = build_leads(engine)
    write_silver_table(df_leads, "leads", engine)
    print(f"    ✓ silver.leads{' ' * 33} {len(df_leads):>10,} rows")

    total_rows = sum(
        [
            len(df_geo),
            len(df_cust),
            len(df_sell),
            len(df_prod),
            len(df_orders),
            len(df_items),
            len(df_pay),
            len(df_rev),
            len(df_leads),
        ]
    )

    print(f"\n  {'─' * 50}")
    print(f"  TOTAL: 9 tables, {total_rows:,} rows written")
    print(f"  Schema: olist_olap.silver is ready")
    print("=" * 70)