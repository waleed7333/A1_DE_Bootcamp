# src/transform/gold/build_facts.py
# Phase 5: Transform - Gold Layer - Facts
# Builds all 5 fact DataFrames using silver data and dimension lookups

import pandas as pd
import numpy as np
from sqlalchemy import text

from code.src.config import get_olap_engine
from code.src.transform.gold.build_dimensions import build_lookup_map


# =============================================================================
# FACT TABLE BUILDERS
# =============================================================================


def build_fact_sales(engine, dimensions: dict) -> pd.DataFrame:
    """
    Build Fact_Sales from silver.order_items + silver.orders.

    Grain: one row per order_id + order_item_id.

    Parameters
    ----------
    engine : sqlalchemy.engine.Engine
    dimensions : dict
        Dictionary containing all dimension DataFrames.

    Returns
    -------
    pd.DataFrame
        Fact_Sales ready for loading.
    """
    print("    → Building Fact_Sales...")

    # Load source data
    order_items = pd.read_sql_table("order_items", engine, schema="silver")
    orders = pd.read_sql_table("orders", engine, schema="silver")

    # Merge items with orders to get timestamps and customer_id
    df = order_items.merge(orders, on="order_id", how="left")

    # Build lookup maps
    customer_map = build_lookup_map(dimensions["dim_customer"], "customer_id", "customer_key")
    seller_map = build_lookup_map(dimensions["dim_seller"], "seller_id", "seller_key")
    product_map = build_lookup_map(dimensions["dim_product"], "product_id", "product_key")
    order_status_map = build_lookup_map(
        dimensions["dim_order_status"], "order_status", "order_status_key"
    )

    # Map natural keys to surrogate keys
    df["customer_key"] = df["customer_id"].map(customer_map)
    df["seller_key"] = df["seller_id"].map(seller_map)
    df["product_key"] = df["product_id"].map(product_map)
    df["order_status_key"] = df["order_status"].map(order_status_map)
        # Add location keys by joining with dimension tables
    # Build location lookup map
    location_map = build_lookup_map(
        dimensions["dim_location"], "zip_code_prefix", "location_key"
    )

    # Get customer zip codes from dim_customer
    customer_zip_map = dict(
        zip(
            dimensions["dim_customer"]["customer_id"],
            dimensions["dim_customer"]["zip_code_prefix"],
        )
    )
    df["customer_zip"] = df["customer_id"].map(customer_zip_map)
    df["customer_location_key"] = df["customer_zip"].map(location_map)

    # Get seller zip codes from dim_seller
    seller_zip_map = dict(
        zip(
            dimensions["dim_seller"]["seller_id"],
            dimensions["dim_seller"]["zip_code_prefix"],
        )
    )
    df["seller_zip"] = df["seller_id"].map(seller_zip_map)
    df["seller_location_key"] = df["seller_zip"].map(location_map)

    # Convert timestamps to date keys (YYYYMMDD)
    date_columns = {
        "order_purchase_timestamp": "purchase_date_key",
        "order_approved_at": "approved_date_key",
        "order_delivered_carrier_date": "delivered_carrier_date_key",
        "order_delivered_customer_date": "delivered_customer_date_key",
        "order_estimated_delivery_date": "estimated_delivery_date_key",
    }

    for src_col, tgt_col in date_columns.items():
        df[tgt_col] = pd.to_datetime(df[src_col]).dt.strftime("%Y%m%d")
        # Convert to int where possible, NaN stays NaN
        df[tgt_col] = pd.to_numeric(df[tgt_col], errors="coerce").astype("Int64")

    # Calculate measures
    df["unit_price"] = df["price"]
    df["quantity"] = 1  # Each row in order_items is 1 unit
    df["item_total"] = df["unit_price"] * df["quantity"]
    df["shipping_value"] = df["freight_value"]

    # Calculate delivery delay: actual - estimated (positive = late)
    delivered = pd.to_datetime(df["order_delivered_customer_date"])
    estimated = pd.to_datetime(df["order_estimated_delivery_date"])
    df["delivery_delay_days"] = (delivered - estimated).dt.days

    # Extract time key from purchase timestamp
    purchase_dt = pd.to_datetime(df["order_purchase_timestamp"])
    df["purchase_time_key"] = purchase_dt.dt.hour * 60 + purchase_dt.dt.minute

    # Select and order final columns
    result = df[
        [
            "order_id",
            "order_item_id",
            "customer_key",
            "seller_key",
            "product_key",
            "customer_location_key",
            "seller_location_key",
            "purchase_date_key",
            "approved_date_key",
            "delivered_carrier_date_key",
            "delivered_customer_date_key",
            "estimated_delivery_date_key",
            "order_status_key",
            "unit_price",
            "quantity",
            "item_total",
            "shipping_value",
            "delivery_delay_days",
            "purchase_time_key",
        ]
    ].copy()

    # Add surrogate key
    result.insert(0, "sales_key", range(1, len(result) + 1))

    print(f"      {len(result):,} rows built")
    return result


def build_fact_payments(engine, dimensions: dict) -> pd.DataFrame:
    """
    Build Fact_Payments from silver.order_payments.

    Grain: one row per order_id + payment_sequential.

    Parameters
    ----------
    engine : sqlalchemy.engine.Engine
    dimensions : dict

    Returns
    -------
    pd.DataFrame
        Fact_Payments ready for loading.
    """
    print("    → Building Fact_Payments...")

    df = pd.read_sql_table("order_payments", engine, schema="silver")

    # Build lookup maps
    customer_map = build_lookup_map(dimensions["dim_customer"], "customer_id", "customer_key")
    payment_type_map = build_lookup_map(
        dimensions["dim_payment_type"], "payment_type", "payment_type_key"
    )

    # We need customer_id for mapping. payments table has order_id, not customer_id.
    # Join with orders to get customer_id
    orders = pd.read_sql_table("orders", engine, schema="silver")
    orders_subset = orders[["order_id", "customer_id"]].drop_duplicates()

    df = df.merge(orders_subset, on="order_id", how="left")

    # Map to surrogate keys
    df["customer_key"] = df["customer_id"].map(customer_map)
    df["payment_type_key"] = df["payment_type"].map(payment_type_map)

    # Payment date = order purchase date (closest approximation in source)
    orders_full = orders[["order_id", "order_purchase_timestamp"]]
    df = df.merge(orders_full, on="order_id", how="left")
    df["payment_date_key"] = (
        pd.to_datetime(df["order_purchase_timestamp"]).dt.strftime("%Y%m%d")
    )
    df["payment_date_key"] = pd.to_numeric(df["payment_date_key"], errors="coerce").astype("Int64")

    # Select final columns
    result = df[
        [
            "order_id",
            "payment_sequential",
            "customer_key",
            "payment_date_key",
            "payment_type_key",
            "payment_value",
            "payment_installments",
        ]
    ].copy()

    # Add surrogate key
    result.insert(0, "payment_key", range(1, len(result) + 1))

    print(f"      {len(result):,} rows built")
    return result


def build_fact_reviews(engine, dimensions: dict) -> pd.DataFrame:
    """
    Build Fact_Reviews from silver.order_reviews.

    Grain: one row per review_id.

    Parameters
    ----------
    engine : sqlalchemy.engine.Engine
    dimensions : dict

    Returns
    -------
    pd.DataFrame
        Fact_Reviews ready for loading.
    """
    print("    → Building Fact_Reviews...")

    df = pd.read_sql_table("order_reviews", engine, schema="silver")

    # We need customer_id for mapping
    orders = pd.read_sql_table("orders", engine, schema="silver")
    orders_subset = orders[["order_id", "customer_id"]].drop_duplicates()
    df = df.merge(orders_subset, on="order_id", how="left")

    # Map to surrogate key
    customer_map = build_lookup_map(dimensions["dim_customer"], "customer_id", "customer_key")
    df["customer_key"] = df["customer_id"].map(customer_map)

    # Convert dates to date keys
    df["review_creation_date_key"] = (
        pd.to_datetime(df["review_creation_date"]).dt.strftime("%Y%m%d")
    )
    df["review_creation_date_key"] = pd.to_numeric(
        df["review_creation_date_key"], errors="coerce"
    ).astype("Int64")

    df["review_answer_date_key"] = (
        pd.to_datetime(df["review_answer_timestamp"]).dt.strftime("%Y%m%d")
    )
    df["review_answer_date_key"] = pd.to_numeric(
        df["review_answer_date_key"], errors="coerce"
    ).astype("Int64")

    # Add derived columns
    df["is_positive"] = df["review_score"] >= 4
    df["is_negative"] = df["review_score"] <= 2

    # Select final columns
    result = df[
        [
            "review_id",
            "order_id",
            "customer_key",
            "review_creation_date_key",
            "review_answer_date_key",
            "review_score",
            "is_positive",
            "is_negative",
        ]
    ].copy()

    # Add surrogate key
    result.insert(0, "review_key", range(1, len(result) + 1))

    print(f"      {len(result):,} rows built")
    return result


def build_fact_seller_acquisition(engine, dimensions: dict) -> pd.DataFrame:
    """
    Build Fact_Seller_Acquisition from silver.leads.

    Grain: one row per mql_id (marketing qualified lead).

    Parameters
    ----------
    engine : sqlalchemy.engine.Engine
    dimensions : dict

    Returns
    -------
    pd.DataFrame
        Fact_Seller_Acquisition ready for loading.
    """
    print("    → Building Fact_Seller_Acquisition...")

    df = pd.read_sql_table("leads", engine, schema="silver")

    # Build lookup maps
    lead_map = build_lookup_map(dimensions["dim_lead"], "mql_id", "lead_key")
    seller_map = build_lookup_map(dimensions["dim_seller"], "seller_id", "seller_key")
    lead_source_map = build_lookup_map(
        dimensions["dim_lead_source"], "origin", "lead_source_key"
    )

    # Map to surrogate keys
    df["lead_key"] = df["mql_id"].map(lead_map)
    df["seller_key"] = df["seller_id"].map(seller_map)  # Will be NaN for unconverted leads
    df["lead_source_key"] = df["origin"].map(lead_source_map)

    # Convert dates to date keys
    df["first_contact_date_key"] = (
        pd.to_datetime(df["first_contact_date"]).dt.strftime("%Y%m%d")
    )
    df["first_contact_date_key"] = pd.to_numeric(
        df["first_contact_date_key"], errors="coerce"
    ).astype("Int64")

    df["won_date_key"] = (
        pd.to_datetime(df["won_date"]).dt.strftime("%Y%m%d")
    )
    df["won_date_key"] = pd.to_numeric(
        df["won_date_key"], errors="coerce"
    ).astype("Int64")

    # Derived columns
    df["conversion_flag"] = df["won_date"].notna()

    # Calculate conversion days
    first_contact = pd.to_datetime(df["first_contact_date"])
    won = pd.to_datetime(df["won_date"])
    df["conversion_days"] = (won - first_contact).dt.days

    # Select final columns - only keys and measures (no descriptive attributes)
    result = df[
        [
            "lead_key",
            "seller_key",
            "lead_source_key",
            "first_contact_date_key",
            "won_date_key",
            "declared_monthly_revenue",
            "declared_product_catalog_size",
            "has_company",
            "has_gtin",
            "conversion_flag",
            "conversion_days",
        ]
    ].copy()

    # Add surrogate key
    result.insert(0, "acquisition_key", range(1, len(result) + 1))

    print(f"      {len(result):,} rows built")
    return result


def build_fact_order_events(engine, dimensions: dict) -> pd.DataFrame:
    """
    Build Fact_Order_Events by unpivoting silver.orders timestamp columns.

    Grain: one row per order_id + event_type_key.

    Takes each order and creates separate rows for each lifecycle event
    (purchased, approved, delivered_carrier, delivered_customer, canceled).
    Events with NULL timestamps are excluded.

    Parameters
    ----------
    engine : sqlalchemy.engine.Engine
    dimensions : dict

    Returns
    -------
    pd.DataFrame
        Fact_Order_Events ready for loading.
    """
    print("    → Building Fact_Order_Events...")

    orders = pd.read_sql_table("orders", engine, schema="silver")

    # Build lookup maps
    customer_map = build_lookup_map(dimensions["dim_customer"], "customer_id", "customer_key")
    seller_map = build_lookup_map(dimensions["dim_seller"], "seller_id", "seller_key")

    # We need seller_id for each order. Get it from order_items.
    order_items = pd.read_sql_table("order_items", engine, schema="silver")
    order_seller = (
        order_items.groupby("order_id")["seller_id"].first().reset_index()
    )
    orders = orders.merge(order_seller, on="order_id", how="left")

    # Map to surrogate keys
    orders["customer_key"] = orders["customer_id"].map(customer_map)
    orders["seller_key"] = orders["seller_id"].map(seller_map)

    # Define event mapping: (timestamp_column, event_type_name)
    event_map = [
        ("order_purchase_timestamp", "purchased"),
        ("order_approved_at", "approved"),
        ("order_delivered_carrier_date", "delivered_carrier"),
        ("order_delivered_customer_date", "delivered_customer"),
    ]

    # Reverse lookup: event_name → event_type_key
    dim_event = dimensions["dim_event_type"]
    event_name_to_key = dict(zip(dim_event["event_type_name"], dim_event["event_type_key"]))

    # Unpivot: one row per event per order
    event_rows = []

    for ts_col, event_name in event_map:
        subset = orders[["order_id", "customer_key", "seller_key", ts_col]].copy()
        subset["event_type_name"] = event_name
        subset.rename(columns={ts_col: "event_timestamp"}, inplace=True)
        event_rows.append(subset)

    # Handle canceled orders separately
    canceled = orders[orders["order_status"] == "canceled"][
        ["order_id", "customer_key", "seller_key", "order_purchase_timestamp"]
    ].copy()
    canceled["event_type_name"] = "canceled"
    canceled.rename(columns={"order_purchase_timestamp": "event_timestamp"}, inplace=True)
    event_rows.append(canceled)

    # Combine all events
    df = pd.concat(event_rows, ignore_index=True)

    # Remove rows with NULL timestamps
    df = df.dropna(subset=["event_timestamp"])

    # Convert timestamp to date key
    df["event_date_key"] = (
        pd.to_datetime(df["event_timestamp"]).dt.strftime("%Y%m%d")
    )
    df["event_date_key"] = pd.to_numeric(df["event_date_key"], errors="coerce").astype("Int64")

    # Map event name to event type key
    df["event_type_key"] = df["event_type_name"].map(event_name_to_key)

    # Select final columns
    result = df[
        [
            "order_id",
            "customer_key",
            "seller_key",
            "event_date_key",
            "event_type_key",
        ]
    ].copy()

    # Add surrogate key
    result.insert(0, "event_key", range(1, len(result) + 1))

    print(f"      {len(result):,} rows built from {len(orders):,} orders")
    return result


# =============================================================================
# MAIN ORCHESTRATOR
# =============================================================================


def build_all_facts(dimensions: dict) -> dict:
    """
    Main entry point for Phase 5.

    Builds all 5 fact DataFrames and returns them as a dictionary.

    Parameters
    ----------
    dimensions : dict
        Dictionary containing all dimension DataFrames from Phase 4.

    Returns
    -------
    dict
        Dictionary with fact names as keys and DataFrames as values.
        Keys: fact_sales, fact_payments, fact_reviews,
              fact_seller_acquisition, fact_order_events
    """
    print("\n" + "=" * 70)
    print("PHASE 5: TRANSFORM - Gold Layer - Facts")
    print("=" * 70)

    engine = get_olap_engine()

    facts = {}

    print("\n  Building fact tables...")

    facts["fact_sales"] = build_fact_sales(engine, dimensions)
    facts["fact_payments"] = build_fact_payments(engine, dimensions)
    facts["fact_reviews"] = build_fact_reviews(engine, dimensions)
    facts["fact_seller_acquisition"] = build_fact_seller_acquisition(engine, dimensions)
    facts["fact_order_events"] = build_fact_order_events(engine, dimensions)

    print(f"\n  {'─' * 50}")
    print(f"  TOTAL: {len(facts)} fact tables built successfully")
    print("=" * 70)

    return facts