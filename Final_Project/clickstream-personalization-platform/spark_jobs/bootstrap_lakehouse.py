#!/usr/bin/env python3
"""Create the final Iceberg tables and load the immutable Product Catalog once."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pyspark.sql import SparkSession, functions as F
from pyspark.sql.types import DecimalType, IntegerType

PROJECT_DATA = Path("/opt/project/data")
PROJECT_RUNTIME = Path("/opt/project/runtime")
CATALOG_PATH = PROJECT_DATA / "reference" / "product_catalog.csv"
MANIFEST_PATH = PROJECT_DATA / "source" / "generation_manifest.json"
CATALOG = "ecommerce"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap the Clickstream Iceberg Lakehouse")
    parser.add_argument("--run-id", required=True)
    return parser.parse_args()


def now_utc() -> datetime:
    return datetime.now(UTC)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_report(run_id: str, payload: dict[str, Any]) -> None:
    PROJECT_RUNTIME.mkdir(parents=True, exist_ok=True)
    path = PROJECT_RUNTIME / f"bootstrap_lakehouse_{run_id}.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def make_spark() -> SparkSession:
    password = os.environ.get("POSTGRES_PASSWORD", "")
    user = os.environ.get("POSTGRES_USER", "ecommerce_user")
    if not password:
        raise RuntimeError("POSTGRES_PASSWORD is not available inside spark-engine")
    return (
        SparkSession.builder.appName("bootstrap-lakehouse")
        .config("spark.sql.catalog.ecommerce.jdbc.user", user)
        .config("spark.sql.catalog.ecommerce.jdbc.password", password)
        .config("spark.sql.catalog.ecommerce.type", "jdbc")
        .config("spark.sql.catalog.ecommerce.cache-enabled", "false")
        .getOrCreate()
    )


def create_tables(spark: SparkSession) -> None:
    """Create the small approved Raw, Clean, and Audit table set."""
    for namespace in ("raw", "processed", "audit"):
        spark.sql(f"CREATE NAMESPACE IF NOT EXISTS {CATALOG}.{namespace}")

    tables = [
        f"""
        CREATE TABLE IF NOT EXISTS {CATALOG}.raw.kafka_messages (
            source_name STRING,
            kafka_topic STRING,
            kafka_partition INT,
            kafka_offset BIGINT,
            kafka_timestamp TIMESTAMP,
            source_record_id STRING,
            raw_payload STRING,
            source_file STRING,
            ingested_at TIMESTAMP,
            stream_batch_id BIGINT
        ) USING iceberg
        PARTITIONED BY (days(ingested_at), source_name)
        TBLPROPERTIES ('format-version'='2', 'write.format.default'='parquet', 'write.parquet.compression-codec'='zstd')
        """,
        f"""
        CREATE TABLE IF NOT EXISTS {CATALOG}.processed.product_catalog_clean (
            product_id STRING, product_name STRING, category STRING, price DECIMAL(12,2), inventory INT,
            created_at TIMESTAMP, updated_at TIMESTAMP, catalog_checksum STRING, loaded_at TIMESTAMP
        ) USING iceberg PARTITIONED BY (category)
        TBLPROPERTIES ('format-version'='2', 'write.format.default'='parquet', 'write.parquet.compression-codec'='zstd')
        """,
        f"""
        CREATE TABLE IF NOT EXISTS {CATALOG}.processed.clickstream_clean (
            event_id STRING, contract_version STRING, event_timestamp TIMESTAMP, session_id STRING, visitor_id STRING,
            request_id STRING, user_id STRING, event_type STRING, page_url STRING, search_query STRING,
            product_id STRING, checkout_id STRING, order_id STRING, ip_address STRING, device_type STRING,
            browser STRING, operating_system STRING, traffic_source STRING, scroll_depth_pct INT,
            time_on_page_seconds INT, late_arrival BOOLEAN, geo_country_code STRING, geo_country_name STRING,
            geo_city STRING, geo_latitude DOUBLE, geo_longitude DOUBLE, geo_timezone STRING,
            source_file STRING, kafka_topic STRING, kafka_partition INT, kafka_offset BIGINT,
            source_record_id STRING, processed_at TIMESTAMP
        ) USING iceberg PARTITIONED BY (days(event_timestamp))
        TBLPROPERTIES ('format-version'='2', 'write.format.default'='parquet', 'write.parquet.compression-codec'='zstd')
        """,
        f"""
        CREATE TABLE IF NOT EXISTS {CATALOG}.processed.webserver_logs_clean (
            log_id STRING, contract_version STRING, request_id STRING, log_timestamp TIMESTAMP, ip_address STRING,
            http_method STRING, endpoint STRING, status_code INT, response_time_ms INT, user_agent STRING,
            bytes_sent BIGINT, late_arrival BOOLEAN, geo_country_code STRING, geo_country_name STRING,
            geo_city STRING, geo_latitude DOUBLE, geo_longitude DOUBLE, geo_timezone STRING,
            source_file STRING, kafka_topic STRING, kafka_partition INT, kafka_offset BIGINT,
            source_record_id STRING, processed_at TIMESTAMP
        ) USING iceberg PARTITIONED BY (days(log_timestamp))
        TBLPROPERTIES ('format-version'='2', 'write.format.default'='parquet', 'write.parquet.compression-codec'='zstd')
        """,
        f"""
        CREATE TABLE IF NOT EXISTS {CATALOG}.processed.users_cdc_clean (
            cdc_event_id STRING, user_id STRING, operation STRING, before_json STRING, after_json STRING,
            source_lsn BIGINT, source_ts_ms BIGINT, kafka_topic STRING, kafka_partition INT, kafka_offset BIGINT,
            source_record_id STRING, processed_at TIMESTAMP
        ) USING iceberg PARTITIONED BY (days(processed_at))
        TBLPROPERTIES ('format-version'='2', 'write.format.default'='parquet', 'write.parquet.compression-codec'='zstd')
        """,
        f"""
        CREATE TABLE IF NOT EXISTS {CATALOG}.processed.orders_cdc_clean (
            cdc_event_id STRING, order_id STRING, user_id STRING, checkout_id STRING, operation STRING,
            before_json STRING, after_json STRING, source_lsn BIGINT, source_ts_ms BIGINT,
            kafka_topic STRING, kafka_partition INT, kafka_offset BIGINT, source_record_id STRING,
            processed_at TIMESTAMP
        ) USING iceberg PARTITIONED BY (days(processed_at))
        TBLPROPERTIES ('format-version'='2', 'write.format.default'='parquet', 'write.parquet.compression-codec'='zstd')
        """,
        f"""
        CREATE TABLE IF NOT EXISTS {CATALOG}.processed.order_items_cdc_clean (
            cdc_event_id STRING, order_item_id STRING, order_id STRING, product_id STRING, operation STRING,
            before_json STRING, after_json STRING, source_lsn BIGINT, source_ts_ms BIGINT,
            kafka_topic STRING, kafka_partition INT, kafka_offset BIGINT, source_record_id STRING,
            processed_at TIMESTAMP
        ) USING iceberg PARTITIONED BY (days(processed_at))
        TBLPROPERTIES ('format-version'='2', 'write.format.default'='parquet', 'write.parquet.compression-codec'='zstd')
        """,
        f"""
        CREATE TABLE IF NOT EXISTS {CATALOG}.processed.user_profile_scd2 (
            user_id STRING, email STRING, first_name STRING, last_name STRING, membership_type STRING,
            account_status STRING, country_code STRING, city STRING, is_deleted BOOLEAN, effective_from TIMESTAMP,
            effective_to TIMESTAMP, is_current BOOLEAN, version_sequence INT, source_lsn BIGINT,
            created_at TIMESTAMP, updated_at TIMESTAMP, processed_at TIMESTAMP
        ) USING iceberg PARTITIONED BY (days(effective_from))
        TBLPROPERTIES ('format-version'='2', 'write.format.default'='parquet', 'write.parquet.compression-codec'='zstd')
        """,
        f"""
        CREATE TABLE IF NOT EXISTS {CATALOG}.processed.weather_clean (
            weather_key STRING, latitude DOUBLE, longitude DOUBLE, weather_hour TIMESTAMP,
            temperature_c DOUBLE, precipitation_mm DOUBLE, weather_code INT, weather_condition STRING,
            coverage_status STRING, fetched_at TIMESTAMP
        ) USING iceberg PARTITIONED BY (days(weather_hour))
        TBLPROPERTIES ('format-version'='2', 'write.format.default'='parquet', 'write.parquet.compression-codec'='zstd')
        """,
        f"""
        CREATE TABLE IF NOT EXISTS {CATALOG}.processed.holidays_clean (
            holiday_key STRING, country_code STRING, holiday_date DATE, holiday_name STRING,
            holiday_type STRING, year INT, coverage_status STRING, fetched_at TIMESTAMP
        ) USING iceberg PARTITIONED BY (year)
        TBLPROPERTIES ('format-version'='2', 'write.format.default'='parquet', 'write.parquet.compression-codec'='zstd')
        """,
        f"""
        CREATE TABLE IF NOT EXISTS {CATALOG}.audit.pipeline_runs (
            run_id STRING, job_name STRING, source_name STRING, status STRING, started_at TIMESTAMP,
            finished_at TIMESTAMP, input_count BIGINT, accepted_count BIGINT, invalid_count BIGINT,
            duplicate_count BIGINT, output_count BIGINT, error_message STRING, recorded_at TIMESTAMP
        ) USING iceberg PARTITIONED BY (days(recorded_at))
        TBLPROPERTIES ('format-version'='2', 'write.format.default'='parquet', 'write.parquet.compression-codec'='zstd')
        """,
        f"""
        CREATE TABLE IF NOT EXISTS {CATALOG}.audit.quality_metrics (
            run_id STRING, source_name STRING, metric_name STRING, metric_value STRING,
            status STRING, recorded_at TIMESTAMP
        ) USING iceberg PARTITIONED BY (days(recorded_at))
        TBLPROPERTIES ('format-version'='2', 'write.format.default'='parquet', 'write.parquet.compression-codec'='zstd')
        """,
        f"""
        CREATE TABLE IF NOT EXISTS {CATALOG}.audit.quarantine_records (
            quarantine_id STRING, source_name STRING, reason_code STRING, reason_description STRING,
            raw_payload STRING, kafka_topic STRING, kafka_partition INT, kafka_offset BIGINT,
            source_record_id STRING, stream_batch_id BIGINT, quarantined_at TIMESTAMP
        ) USING iceberg PARTITIONED BY (days(quarantined_at), source_name)
        TBLPROPERTIES ('format-version'='2', 'write.format.default'='parquet', 'write.parquet.compression-codec'='zstd')
        """,
        f"""
        CREATE TABLE IF NOT EXISTS {CATALOG}.audit.external_api_failures (
            run_id STRING, api_name STRING, request_key STRING, http_status INT, error_message STRING,
            retry_count INT, status STRING, occurred_at TIMESTAMP
        ) USING iceberg PARTITIONED BY (days(occurred_at))
        TBLPROPERTIES ('format-version'='2', 'write.format.default'='parquet', 'write.parquet.compression-codec'='zstd')
        """,
        f"""
        CREATE TABLE IF NOT EXISTS {CATALOG}.audit.watermarks (
            job_name STRING, source_name STRING, last_processed_id STRING, last_processed_offset BIGINT,
            last_snapshot_id STRING, updated_at TIMESTAMP
        ) USING iceberg PARTITIONED BY (days(updated_at))
        TBLPROPERTIES ('format-version'='2', 'write.format.default'='parquet', 'write.parquet.compression-codec'='zstd')
        """,
        f"""
        CREATE TABLE IF NOT EXISTS {CATALOG}.audit.validation_runs (
            validation_id STRING, status STRING, cutoff_description STRING, source_snapshot_summary STRING,
            quality_status STRING, relationship_status STRING, scd2_status STRING, coverage_status STRING,
            details_json STRING, created_at TIMESTAMP
        ) USING iceberg PARTITIONED BY (days(created_at))
        TBLPROPERTIES ('format-version'='2', 'write.format.default'='parquet', 'write.parquet.compression-codec'='zstd')
        """,
        f"""
        CREATE TABLE IF NOT EXISTS {CATALOG}.audit.serving_builds (
            serving_build_id STRING, validation_id STRING, status STRING, row_count_summary STRING,
            error_message STRING, activated_at TIMESTAMP, created_at TIMESTAMP
        ) USING iceberg PARTITIONED BY (days(created_at))
        TBLPROPERTIES ('format-version'='2', 'write.format.default'='parquet', 'write.parquet.compression-codec'='zstd')
        """,
    ]
    for statement in tables:
        spark.sql(statement)


def load_static_catalog(spark: SparkSession) -> tuple[int, bool]:
    """Load the fixed, validated catalog exactly once."""
    if not CATALOG_PATH.is_file() or not MANIFEST_PATH.is_file():
        raise FileNotFoundError("Product Catalog or generation manifest is missing")
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    checksum = sha256_file(CATALOG_PATH)
    if checksum != manifest.get("catalog_checksum"):
        raise RuntimeError("Product Catalog checksum does not match generation manifest")
    raw = spark.read.option("header", True).option("mode", "FAILFAST").csv(str(CATALOG_PATH))
    parsed = raw.select(
        F.trim("product_id").alias("product_id"), F.trim("product_name").alias("product_name"),
        F.trim("category").alias("category"), F.col("price").cast(DecimalType(12, 2)).alias("price"),
        F.col("inventory").cast(IntegerType()).alias("inventory"),
        F.to_timestamp("created_at", "yyyy-MM-dd'T'HH:mm:ssX").alias("created_at"),
        F.to_timestamp("updated_at", "yyyy-MM-dd'T'HH:mm:ssX").alias("updated_at"),
        F.lit(checksum).alias("catalog_checksum"), F.current_timestamp().alias("loaded_at"),
    )
    invalid = parsed.filter(
        F.col("product_id").isNull() | (F.length("product_id") == 0) | F.col("product_name").isNull()
        | F.col("category").isNull() | (F.col("price") < 0) | (F.col("inventory") < 0)
    ).count()
    duplicate = parsed.groupBy("product_id").count().filter("count > 1").count()
    if invalid or duplicate:
        raise RuntimeError(f"Product Catalog validation failed: invalid={invalid}, duplicate={duplicate}")
    existing = spark.table(f"{CATALOG}.processed.product_catalog_clean").count()
    if existing == 0:
        parsed.writeTo(f"{CATALOG}.processed.product_catalog_clean").append()
        return parsed.count(), True
    return existing, False


def main() -> int:
    args = parse_args()
    spark: SparkSession | None = None
    try:
        spark = make_spark()
        create_tables(spark)
        product_rows, inserted = load_static_catalog(spark)
        write_report(args.run_id, {
            "status": "PASSED", "run_id": args.run_id, "tables_created_or_verified": 17,
            "product_catalog_rows": product_rows, "catalog_inserted": inserted, "finished_at_utc": now_utc(),
        })
        return 0
    except Exception as error:
        write_report(args.run_id, {"status": "FAILED", "run_id": args.run_id, "error": f"{type(error).__name__}: {error}"})
        raise
    finally:
        if spark is not None:
            spark.stop()


if __name__ == "__main__":
    raise SystemExit(main())
