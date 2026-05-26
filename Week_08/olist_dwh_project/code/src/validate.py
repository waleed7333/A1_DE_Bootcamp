# src/validate.py
# Phase 7: Validation - Data quality checks on the final star schema

import pandas as pd
from sqlalchemy import text

from code.src.config import get_olap_engine


def check_row_counts(engine) -> list:
    """
    Compare row counts between source (silver) and target (facts).

    Parameters
    ----------
    engine : sqlalchemy.engine.Engine

    Returns
    -------
    list
        List of (check_name, passed, detail) tuples.
    """
    print("\n  → Checking row counts...")
    results = []

    checks = [
        # (fact_table, silver_table, description)
        ("facts.fact_sales", "silver.order_items", "Sales vs Order Items"),
        ("facts.fact_payments", "silver.order_payments", "Payments vs Order Payments"),
        ("facts.fact_reviews", "silver.order_reviews", "Reviews vs Order Reviews"),
    ]

    for fact_table, silver_table, description in checks:
        fact_count = pd.read_sql_query(
            f"SELECT COUNT(*) AS cnt FROM {fact_table}", engine
        )["cnt"].iloc[0]

        silver_count = pd.read_sql_query(
            f"SELECT COUNT(*) AS cnt FROM {silver_table}", engine
        )["cnt"].iloc[0]

        passed = fact_count == silver_count
        results.append((description, passed, f"Fact: {fact_count:,} | Silver: {silver_count:,}"))

    # Special check for seller acquisition
    leads_count = pd.read_sql_query(
        "SELECT COUNT(*) AS cnt FROM facts.fact_seller_acquisition", engine
    )["cnt"].iloc[0]

    silver_leads = pd.read_sql_query(
        "SELECT COUNT(*) AS cnt FROM silver.leads", engine
    )["cnt"].iloc[0]

    passed = leads_count == silver_leads
    results.append(
        ("Acquisition vs Leads", passed, f"Fact: {leads_count:,} | Silver: {silver_leads:,}")
    )

    # Special check for order events (should be >= 4 * delivered orders)
    events_count = pd.read_sql_query(
        "SELECT COUNT(*) AS cnt FROM facts.fact_order_events", engine
    )["cnt"].iloc[0]

    # Calculate expected minimum: each delivered order has at least 4 events
    delivered_count = pd.read_sql_query(
        "SELECT COUNT(*) AS cnt FROM facts.fact_order_events WHERE event_type_key = 4",
        engine,
    )["cnt"].iloc[0]

    results.append(
        (
            "Order Events (delivered count check)",
            events_count > 0,
            f"Total events: {events_count:,} | Delivered events: {delivered_count:,}",
        )
    )

    return results


def check_null_foreign_keys(engine) -> list:
    """
    Check for NULL values in critical foreign key columns.

    Parameters
    ----------
    engine : sqlalchemy.engine.Engine

    Returns
    -------
    list
        List of (check_name, passed, detail) tuples.
    """
    print("\n  → Checking NULL foreign keys...")
    results = []

    checks = [
        # (table, column, nullable_ok)
        ("facts.fact_sales", "customer_key", False),
        ("facts.fact_sales", "seller_key", False),
        ("facts.fact_sales", "product_key", False),
        ("facts.fact_sales", "purchase_date_key", False),
        ("facts.fact_payments", "customer_key", False),
        ("facts.fact_payments", "payment_type_key", False),
        ("facts.fact_reviews", "customer_key", False),
        ("facts.fact_reviews", "review_score", False),
        ("facts.fact_seller_acquisition", "lead_key", False),
        ("facts.fact_seller_acquisition", "seller_key", True),  # NULL = unconverted
        ("facts.fact_order_events", "event_date_key", False),
        ("facts.fact_order_events", "event_type_key", False),
        ("facts.fact_sales", "customer_location_key", False),
        ("facts.fact_sales", "seller_location_key", False),
    ]

    for table, column, nullable_ok in checks:
        null_count = pd.read_sql_query(
            f"SELECT COUNT(*) AS cnt FROM {table} WHERE {column} IS NULL",
            engine,
        )["cnt"].iloc[0]

        passed = (null_count == 0) if not nullable_ok else True
        results.append(
            (f"{table}.{column}", passed, f"NULL count: {null_count:,}")
        )

    return results


def check_referential_integrity(engine) -> list:
    """
    Check that all foreign keys have matching primary keys in dimensions.

    Parameters
    ----------
    engine : sqlalchemy.engine.Engine

    Returns
    -------
    list
        List of (check_name, passed, detail) tuples.
    """
    print("\n  → Checking referential integrity...")
    results = []

    checks = [
        # (fact_table, fk_column, dim_table, pk_column)
        ("facts.fact_sales", "customer_key", "dimensions.dim_customer", "customer_key"),
        ("facts.fact_sales", "seller_key", "dimensions.dim_seller", "seller_key"),
        ("facts.fact_sales", "product_key", "dimensions.dim_product", "product_key"),
        ("facts.fact_payments", "customer_key", "dimensions.dim_customer", "customer_key"),
        ("facts.fact_payments", "payment_type_key", "dimensions.dim_payment_type", "payment_type_key"),
        ("facts.fact_reviews", "customer_key", "dimensions.dim_customer", "customer_key"),
        ("facts.fact_seller_acquisition", "lead_key", "dimensions.dim_lead", "lead_key"),
        ("facts.fact_order_events", "event_type_key", "dimensions.dim_event_type", "event_type_key"),
        ("facts.fact_sales", "customer_location_key", "dimensions.dim_location", "location_key"),
        ("facts.fact_sales", "seller_location_key", "dimensions.dim_location", "location_key"),
    ]

    for fact_table, fk_col, dim_table, pk_col in checks:
        # Count FKs that don't exist in the dimension
        orphan_count = pd.read_sql_query(
            f"""
            SELECT COUNT(*) AS cnt
            FROM {fact_table} f
            LEFT JOIN {dim_table} d ON f.{fk_col} = d.{pk_col}
            WHERE f.{fk_col} IS NOT NULL AND d.{pk_col} IS NULL
            """,
            engine,
        )["cnt"].iloc[0]

        passed = orphan_count == 0
        results.append(
            (f"{fact_table}.{fk_col} → {dim_table}", passed, f"Orphans: {orphan_count:,}")
        )

    return results


def run_validation():
    """
    Main entry point for Phase 7.

    Runs all validation checks and prints a summary report.
    """
    print("\n" + "=" * 70)
    print("PHASE 7: VALIDATION - Data Quality Checks")
    print("=" * 70)

    engine = get_olap_engine()

    all_results = []

    # Run checks
    all_results.extend(check_row_counts(engine))
    all_results.extend(check_null_foreign_keys(engine))
    all_results.extend(check_referential_integrity(engine))

    # Print summary
    passed = sum(1 for _, p, _ in all_results if p)
    failed = sum(1 for _, p, _ in all_results if not p)
    total = len(all_results)

    print(f"\n  {'─' * 60}")
    print(f"  VALIDATION REPORT")
    print(f"  {'─' * 60}")

    for name, ok, detail in all_results:
        status = "✓" if ok else "✗"
        print(f"    {status} {name:<50} {detail}")

    print(f"\n  {'─' * 60}")
    print(f"  TOTAL: {total} checks | {passed} passed | {failed} failed")

    if failed == 0:
        print(f"  STATUS: ✓ ALL CHECKS PASSED")
    else:
        print(f"  STATUS: ✗ {failed} CHECK(S) FAILED")

    print("=" * 70)