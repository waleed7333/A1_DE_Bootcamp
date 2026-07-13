#!/usr/bin/env python3
"""Inspect clean, audit, and quarantine counts for evidence screenshots."""

from __future__ import annotations

import sys
from pathlib import Path

from pyspark.sql import functions as F

# Reuse the project's official Spark configuration.
# This avoids missing Iceberg catalog settings.
PROJECT_SPARK_JOBS = Path("/opt/project/spark_jobs")
sys.path.insert(0, str(PROJECT_SPARK_JOBS))

from validate_lakehouse import make_spark  # noqa: E402


CATALOG = "ecommerce"


def section(title: str) -> None:
    """Print a readable section header."""
    print("\n" + "=" * 120)
    print(title)
    print("=" * 120)


def table_exists(spark, table_name: str) -> bool:
    """Return True if an Iceberg table can be read."""
    try:
        spark.table(table_name).limit(1).collect()
        return True
    except Exception as error:
        print(f"[UNREADABLE] {table_name}: {type(error).__name__}: {error}")
        return False


def show_clean_counts(spark) -> None:
    """Show valid records stored in processed clean tables."""
    section("1. CLEAN PROCESSED TABLE ROW COUNTS")

    tables = [
        "product_catalog_clean",
        "clickstream_clean",
        "webserver_logs_clean",
        "users_cdc_clean",
        "orders_cdc_clean",
        "order_items_cdc_clean",
        "user_profile_scd2",
        "weather_clean",
        "holidays_clean",
    ]

    rows = []

    for table in tables:
        full_name = f"{CATALOG}.processed.{table}"

        if table_exists(spark, full_name):
            rows.append((table, spark.table(full_name).count()))

    if rows:
        spark.createDataFrame(rows, ["table_name", "rows"]).orderBy("table_name").show(
            100, False
        )
    else:
        print("No processed tables were readable.")


def show_quarantine_counts(spark) -> None:
    """Show rejected and duplicate records by source and reason."""
    section("2. QUARANTINE COUNTS BY SOURCE AND REASON")

    table_name = f"{CATALOG}.audit.quarantine_records"

    if not table_exists(spark, table_name):
        return

    qr = spark.table(table_name)

    qr.groupBy("source_name", "reason_code", "reason_description") \
        .agg(F.count("*").alias("quarantined_records")) \
        .orderBy("source_name", "reason_code") \
        .show(200, False)


def show_duplicate_records(spark) -> None:
    """Show duplicate records only."""
    section("3. DUPLICATE RECORD SAMPLES")

    table_name = f"{CATALOG}.audit.quarantine_records"

    if not table_exists(spark, table_name):
        return

    qr = spark.table(table_name)

    qr.filter(F.col("reason_code").like("DUPLICATE%")) \
        .select(
            "source_name",
            "reason_code",
            "source_record_id",
            "kafka_topic",
            "kafka_partition",
            "kafka_offset",
            "quarantined_at",
        ) \
        .orderBy(F.col("quarantined_at").desc()) \
        .show(50, False)


def show_invalid_records(spark) -> None:
    """Show invalid non-duplicate records only."""
    section("4. INVALID RECORD SAMPLES")

    table_name = f"{CATALOG}.audit.quarantine_records"

    if not table_exists(spark, table_name):
        return

    qr = spark.table(table_name)

    qr.filter(~F.col("reason_code").like("DUPLICATE%")) \
        .select(
            "source_name",
            "reason_code",
            "reason_description",
            "source_record_id",
            "kafka_topic",
            "kafka_partition",
            "kafka_offset",
            "quarantined_at",
        ) \
        .orderBy(F.col("quarantined_at").desc()) \
        .show(50, False)


def show_quality_metrics(spark) -> None:
    """Show audit quality metrics."""
    section("5. QUALITY METRICS SUMMARY")

    table_name = f"{CATALOG}.audit.quality_metrics"

    if not table_exists(spark, table_name):
        return

    qm = spark.table(table_name)

    qm.groupBy("source_name", "metric_name") \
        .agg(F.sum(F.col("metric_value").cast("long")).alias("total_value")) \
        .orderBy("source_name", "metric_name") \
        .show(200, False)


def show_pipeline_evidence(spark) -> None:
    """Show latest pipeline, validation, and serving evidence."""
    section("6. PIPELINE, VALIDATION, AND SERVING EVIDENCE")

    evidence_tables = [
        f"{CATALOG}.audit.pipeline_runs",
        f"{CATALOG}.audit.validation_runs",
        f"{CATALOG}.audit.serving_builds",
        f"{CATALOG}.audit.watermarks",
        f"{CATALOG}.audit.external_api_failures",
    ]

    for table_name in evidence_tables:
        print(f"\n--- {table_name} ---")

        if table_exists(spark, table_name):
            spark.table(table_name).show(20, False)


def main() -> int:
    """Run all audit inspection queries."""
    spark = make_spark()
    spark.sparkContext.setLogLevel("ERROR")

    try:
        show_clean_counts(spark)
        show_quarantine_counts(spark)
        show_duplicate_records(spark)
        show_invalid_records(spark)
        show_quality_metrics(spark)
        show_pipeline_evidence(spark)

        section("7. INTERPRETATION")
        print("Valid records are stored in ecommerce.processed.* clean tables.")
        print("Invalid and duplicate records are stored in ecommerce.audit.quarantine_records.")
        print("Audit counts and run evidence are stored in ecommerce.audit.* tables.")
        print("Expected rule: Input = Accepted Clean + Rejected Quarantine + Duplicates")

        return 0
    finally:
        spark.stop()


if __name__ == "__main__":
    raise SystemExit(main())