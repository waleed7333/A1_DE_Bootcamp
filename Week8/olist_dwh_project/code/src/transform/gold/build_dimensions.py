# src/transform/gold/build_dimensions.py
# Phase 4: Transform - Gold Layer - Dimensions
# Builds all 10 dimension DataFrames from silver layer data

import pandas as pd
import numpy as np
from sqlalchemy import text

from code.src.config import get_olap_engine


# =============================================================================
# DIMENSION BUILDERS
# =============================================================================


def build_dim_date() -> pd.DataFrame:
    """
    Build Dim_Date by generating all dates from 2016-01-01 to 2018-12-31.

    This dimension is independent of source data.
    Contains fiscal calendar attributes for time-series analysis.

    Returns
    -------
    pd.DataFrame
        Dim_Date with surrogate key date_key (YYYYMMDD format).
    """
    print("    → Building Dim_Date...")

    date_range = pd.date_range(start="2016-01-01", end="2018-12-31", freq="D")

    df = pd.DataFrame()
    df["date_key"] = date_range.strftime("%Y%m%d").astype(int)
    df["full_date"] = date_range.date
    df["year"] = date_range.year
    df["month"] = date_range.month
    df["month_name"] = date_range.strftime("%B")
    df["quarter"] = date_range.quarter
    df["day_of_week"] = date_range.dayofweek + 1  # 1=Monday, 7=Sunday
    df["day_name"] = date_range.strftime("%A")
    df["is_weekend"] = date_range.dayofweek >= 5  # Saturday=5, Sunday=6

    print(f"      Generated {len(df):,} rows (2016-01-01 to 2018-12-31)")
    return df


def build_dim_time() -> pd.DataFrame:
    """
    Build Dim_Time by generating all 1440 minutes in a day.

    Contains time-of-day attributes for intraday analysis.

    Returns
    -------
    pd.DataFrame
        Dim_Time with surrogate key time_key (0-1439).
    """
    print("    → Building Dim_Time...")

    minutes = []
    for minute_of_day in range(1440):
        hour = minute_of_day // 60
        minute = minute_of_day % 60

        # Determine part of day
        if 6 <= hour < 12:
            part_of_day = "Morning"
        elif 12 <= hour < 18:
            part_of_day = "Afternoon"
        elif 18 <= hour < 22:
            part_of_day = "Evening"
        else:
            part_of_day = "Night"

        # Determine business hours
        is_business_hours = 9 <= hour < 17

        # 12-hour format
        hour_12 = hour % 12
        if hour_12 == 0:
            hour_12 = 12
        am_pm = "AM" if hour < 12 else "PM"

        minutes.append(
            {
                "time_key": minute_of_day,
                "hour": hour,
                "minute": minute,
                "hour_12": hour_12,
                "am_pm": am_pm,
                "part_of_day": part_of_day,
                "is_business_hours": is_business_hours,
            }
        )

    df = pd.DataFrame(minutes)
    print(f"      Generated {len(df):,} rows (00:00 to 23:59)")
    return df


def build_dim_payment_type(engine) -> pd.DataFrame:
    """
    Build Dim_Payment_Type from distinct payment types in silver layer.

    Parameters
    ----------
    engine : sqlalchemy.engine.Engine

    Returns
    -------
    pd.DataFrame
    """
    print("    → Building Dim_Payment_Type...")

    df = pd.read_sql_table("order_payments", engine, schema="silver")
    payment_types = df["payment_type"].dropna().unique()

    result = pd.DataFrame(
        {
            "payment_type_key": range(1, len(payment_types) + 1),
            "payment_type": sorted(payment_types),
        }
    )

    print(f"      Found {len(result)} payment types")
    return result


def build_dim_order_status(engine) -> pd.DataFrame:
    """
    Build Dim_Order_Status from distinct order statuses in silver layer.

    Parameters
    ----------
    engine : sqlalchemy.engine.Engine

    Returns
    -------
    pd.DataFrame
    """
    print("    → Building Dim_Order_Status...")

    df = pd.read_sql_table("orders", engine, schema="silver")
    statuses = df["order_status"].dropna().unique()

    result = pd.DataFrame(
        {
            "order_status_key": range(1, len(statuses) + 1),
            "order_status": sorted(statuses),
        }
    )

    print(f"      Found {len(result)} order statuses")
    return result


def build_dim_event_type() -> pd.DataFrame:
    """
    Build Dim_Event_Type with fixed order lifecycle events.

    Returns
    -------
    pd.DataFrame
    """
    print("    → Building Dim_Event_Type...")

    events = [
        "purchased",
        "approved",
        "delivered_carrier",
        "delivered_customer",
        "canceled",
    ]

    result = pd.DataFrame(
        {
            "event_type_key": range(1, len(events) + 1),
            "event_type_name": events,
        }
    )

    print(f"      Defined {len(result)} event types")
    return result


def build_dim_lead_source(engine) -> pd.DataFrame:
    """
    Build Dim_Lead_Source from distinct origins in silver leads.

    Parameters
    ----------
    engine : sqlalchemy.engine.Engine

    Returns
    -------
    pd.DataFrame
    """
    print("    → Building Dim_Lead_Source...")

    df = pd.read_sql_table("leads", engine, schema="silver")
    sources = df["origin"].dropna().unique()

    result = pd.DataFrame(
        {
            "lead_source_key": range(1, len(sources) + 1),
            "origin": sorted(sources),
        }
    )

    print(f"      Found {len(result)} lead sources")
    return result


def build_dim_location(engine) -> pd.DataFrame:
    """
    Build Dim_Location from cleaned silver.geolocation.

    Parameters
    ----------
    engine : sqlalchemy.engine.Engine

    Returns
    -------
    pd.DataFrame
    """
    print("    → Building Dim_Location...")

    df = pd.read_sql_table("geolocation", engine, schema="silver")

    # region mapping
    region_map = {
        'SP': 'Southeast', 'RJ': 'Southeast', 'MG': 'Southeast', 'ES': 'Southeast',
        'PR': 'South', 'SC': 'South', 'RS': 'South',
        'BA': 'Northeast', 'PE': 'Northeast', 'CE': 'Northeast', 'MA': 'Northeast',
        'PB': 'Northeast', 'RN': 'Northeast', 'AL': 'Northeast', 'SE': 'Northeast', 'PI': 'Northeast',
        'DF': 'Central-West', 'GO': 'Central-West', 'MT': 'Central-West', 'MS': 'Central-West',
        'AM': 'North', 'PA': 'North', 'RO': 'North', 'RR': 'North', 'AP': 'North', 'TO': 'North', 'AC': 'North',
    }

    # Select only required columns
    result = df[["zip_code_prefix", "city", "state"]].copy()

    # Add region column
    result["region"] = result["state"].map(region_map)

    # Add surrogate key
    result.insert(0, "location_key", range(1, len(result) + 1))

    print(f"      {len(result):,} locations loaded with regions")
    return result


def build_dim_customer(engine) -> pd.DataFrame:
    """
    Build Dim_Customer from silver.customers.

    Parameters
    ----------
    engine : sqlalchemy.engine.Engine

    Returns
    -------
    pd.DataFrame
    """
    print("    → Building Dim_Customer...")

    df = pd.read_sql_table("customers", engine, schema="silver")

    result = df[
        [
            "customer_id",
            "customer_unique_id",
            "customer_city",
            "customer_state",
            "customer_zip_code_prefix",
        ]
    ].copy()

    result.rename(
        columns={
            "customer_city": "city",
            "customer_state": "state",
            "customer_zip_code_prefix": "zip_code_prefix",
        },
        inplace=True,
    )

    # Add surrogate key
    result.insert(0, "customer_key", range(1, len(result) + 1))

    print(f"      {len(result):,} customers loaded")
    return result


def build_dim_seller(engine) -> pd.DataFrame:
    """
    Build Dim_Seller from silver.sellers.

    Parameters
    ----------
    engine : sqlalchemy.engine.Engine

    Returns
    -------
    pd.DataFrame
    """
    print("    → Building Dim_Seller...")

    df = pd.read_sql_table("sellers", engine, schema="silver")

    result = df[
        ["seller_id", "seller_city", "seller_state", "seller_zip_code_prefix"]
    ].copy()

    result.rename(
        columns={
            "seller_city": "city",
            "seller_state": "state",
            "seller_zip_code_prefix": "zip_code_prefix",
        },
        inplace=True,
    )

    # Add surrogate key
    result.insert(0, "seller_key", range(1, len(result) + 1))

    print(f"      {len(result):,} sellers loaded")
    return result


def build_dim_product(engine) -> pd.DataFrame:
    """
    Build Dim_Product from silver.products.

    Parameters
    ----------
    engine : sqlalchemy.engine.Engine

    Returns
    -------
    pd.DataFrame
    """
    print("    → Building Dim_Product...")

    df = pd.read_sql_table("products", engine, schema="silver")

    result = df[
        [
            "product_id",
            "product_category_name",
            "product_category_name_english",
            "product_name_length",
            "product_description_length",
            "product_photos_qty",
            "product_weight_g",
            "product_length_cm",
            "product_height_cm",
            "product_width_cm",
        ]
    ].copy()

    # Add surrogate key
    result.insert(0, "product_key", range(1, len(result) + 1))

    print(f"      {len(result):,} products loaded")
    return result


def build_dim_lead(engine) -> pd.DataFrame:
    """
    Build Dim_Lead from silver.leads.

    Contains descriptive attributes of each marketing qualified lead.

    Parameters
    ----------
    engine : sqlalchemy.engine.Engine

    Returns
    -------
    pd.DataFrame
    """
    print("    → Building Dim_Lead...")

    df = pd.read_sql_table("leads", engine, schema="silver")

    result = df[
        [
            "mql_id",
            "lead_type",
            "lead_behaviour_profile",
            "business_segment",
            "business_type",
        ]
    ].copy()

    # Add surrogate key
    result.insert(0, "lead_key", range(1, len(result) + 1))

    print(f"      {len(result):,} leads loaded")
    return result


# =============================================================================
# LOOKUP HELPER
# =============================================================================


def build_lookup_map(df: pd.DataFrame, key_col: str, value_col: str) -> dict:
    """
    Build a dictionary mapping natural keys to surrogate keys.

    Used during fact table construction to replace original IDs
    with surrogate keys.

    Parameters
    ----------
    df : pd.DataFrame
        Dimension DataFrame.
    key_col : str
        Column containing the natural key (original ID).
    value_col : str
        Column containing the surrogate key.

    Returns
    -------
    dict
        Mapping from natural key to surrogate key.
    """
    return dict(zip(df[key_col], df[value_col]))


# =============================================================================
# MAIN ORCHESTRATOR
# =============================================================================


def build_all_dimensions() -> dict:
    """
    Main entry point for Phase 4.

    Builds all 10 dimension DataFrames and returns them as a dictionary.
    Dimensions are built in order of dependency:
    1. Independent dimensions (no source data needed)
    2. Static dimensions (from distinct values)
    3. Entity dimensions (from silver tables)

    Returns
    -------
    dict
        Dictionary with dimension names as keys and DataFrames as values.
        Keys: dim_date, dim_time, dim_payment_type, dim_order_status,
              dim_event_type, dim_lead_source, dim_location,
              dim_customer, dim_seller, dim_product, dim_lead
    """
    print("\n" + "=" * 70)
    print("PHASE 4: TRANSFORM - Gold Layer - Dimensions")
    print("=" * 70)

    engine = get_olap_engine()

    dimensions = {}

    # --- Independent dimensions (no dependencies) ---
    print("\n  Building independent dimensions...")
    dimensions["dim_date"] = build_dim_date()
    dimensions["dim_time"] = build_dim_time()
    dimensions["dim_event_type"] = build_dim_event_type()

    # --- Static dimensions (from distinct values) ---
    print("\n  Building static dimensions...")
    dimensions["dim_payment_type"] = build_dim_payment_type(engine)
    dimensions["dim_order_status"] = build_dim_order_status(engine)
    dimensions["dim_lead_source"] = build_dim_lead_source(engine)

    # --- Entity dimensions (from silver tables) ---
    print("\n  Building entity dimensions...")
    dimensions["dim_location"] = build_dim_location(engine)
    dimensions["dim_customer"] = build_dim_customer(engine)
    dimensions["dim_seller"] = build_dim_seller(engine)
    dimensions["dim_product"] = build_dim_product(engine)
    dimensions["dim_lead"] = build_dim_lead(engine)

    print(f"\n  {'─' * 50}")
    print(f"  TOTAL: {len(dimensions)} dimensions built successfully")
    print("=" * 70)

    return dimensions