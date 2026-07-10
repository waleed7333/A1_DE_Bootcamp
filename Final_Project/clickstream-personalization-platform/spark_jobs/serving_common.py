"""Simple versioned ClickHouse serving helpers for the project."""

from __future__ import annotations

import os
from typing import Iterable

import clickhouse_connect
from pyspark.sql import DataFrame, SparkSession, Window, functions as F
from pyspark.sql.types import DecimalType, StringType, StructField, StructType

CATALOG = "ecommerce"
DATABASE = "personalization_olap"
TABLES = (
    "dim_date",
    "dim_product",
    "dim_user_current",
    "fact_clickstream_event",
    "fact_order",
    "fact_order_item",
    "mart_journey_session",
    "mart_product_performance_daily",
    "mart_web_experience_daily",
    "mart_navigation_paths",
    "mart_personalization_candidates",
    "mart_context_impact_daily",
)
ORDER_SCHEMA = StructType(
    [
        StructField("order_id", StringType()),
        StructField("user_id", StringType()),
        StructField("checkout_id", StringType()),
        StructField("order_timestamp", StringType()),
        StructField("order_status", StringType()),
        StructField("payment_status", StringType()),
        StructField("currency", StringType()),
        StructField("subtotal_amount", StringType()),
        StructField("discount_amount", StringType()),
        StructField("tax_amount", StringType()),
        StructField("shipping_amount", StringType()),
        StructField("total_amount", StringType()),
        StructField("created_at", StringType()),
        StructField("updated_at", StringType()),
    ]
)
ITEM_SCHEMA = StructType(
    [
        StructField("order_item_id", StringType()),
        StructField("order_id", StringType()),
        StructField("product_id", StringType()),
        StructField("quantity", StringType()),
        StructField("unit_price", StringType()),
        StructField("line_total", StringType()),
        StructField("created_at", StringType()),
        StructField("updated_at", StringType()),
    ]
)


def make_spark(app_name: str) -> SparkSession:
    """Create a small local Spark session that reuses Iceberg configuration."""
    return (
        SparkSession.builder.appName(app_name)
        .config(
            "spark.sql.catalog.ecommerce.jdbc.user",
            os.environ.get("POSTGRES_USER", "ecommerce_user"),
        )
        .config(
            "spark.sql.catalog.ecommerce.jdbc.password",
            os.environ.get("POSTGRES_PASSWORD", ""),
        )
        .config("spark.sql.catalog.ecommerce.type", "jdbc")
        .config("spark.sql.catalog.ecommerce.cache-enabled", "false")
        .getOrCreate()
    )


def clickhouse_client():
    """Connect to ClickHouse using container-network settings."""
    return clickhouse_connect.get_client(
        host=os.environ.get("CLICKHOUSE_HOST", "clickhouse"),
        port=int(os.environ.get("CLICKHOUSE_PORT", "8123")),
        username=os.environ.get("CLICKHOUSE_USER", "default"),
        password=os.environ.get("CLICKHOUSE_PASSWORD", ""),
        database="default",
    )


def ensure_schema(client) -> None:
    """Create append-only versioned tables and stable Power BI views."""
    client.command(f"CREATE DATABASE IF NOT EXISTS {DATABASE}")
    client.command(
        f"CREATE TABLE IF NOT EXISTS {DATABASE}.serving_control (active_build_id String, activated_at DateTime('UTC'), status String) ENGINE = MergeTree ORDER BY activated_at"
    )
    columns = {
        "dim_date": "activity_date Date, calendar_year UInt16, calendar_month UInt8, day_of_month UInt8, day_name String, serving_build_id String",
        "dim_product": "product_id String, product_name String, category String, price Decimal(12,2), inventory Int32, serving_build_id String",
        "dim_user_current": "user_id String, membership_type String, account_status String, country_code String, city String, is_deleted UInt8, effective_from DateTime('UTC'), serving_build_id String",
        "fact_clickstream_event": (
            "event_id String, "
            "event_timestamp DateTime('UTC'), "
            "event_date Date, "
            "session_id String, "
            "request_id Nullable(String), "
            "user_id String, "
            "event_type String, "
            "page_url String, "
            "product_id Nullable(String), "
            "checkout_id Nullable(String), "
            "order_id Nullable(String), "
            "device_type String, "
            "traffic_source String, "
            "time_on_page_seconds Int32, "
            "late_arrival UInt8, "
            "country_code String, "
            "city String, "
            "membership_type_at_event String, "
            "serving_build_id String"
        ),
        "fact_order": "order_id String, user_id String, checkout_id String, order_timestamp DateTime('UTC'), order_date Date, order_status String, payment_status String, total_amount Decimal(18,2), confirmed_purchase UInt8, recognized_revenue Decimal(18,2), country_code String, city String, membership_type_at_order String, serving_build_id String",
        "fact_order_item": "order_item_id String, order_id String, user_id String, order_timestamp DateTime('UTC'), order_date Date, product_id String, quantity Int32, unit_price Decimal(18,2), line_total Decimal(18,2), confirmed_purchase UInt8, country_code String, city String, serving_build_id String",
        "mart_journey_session": "session_id String, session_start DateTime('UTC'), session_end DateTime('UTC'), activity_date Date, user_id String, country_code String, city String, traffic_source String, device_type String, event_count UInt32, page_navigation_count UInt32, product_view_count UInt32, add_to_cart_count UInt32, checkout_start_count UInt32, checkout_complete_count UInt32, engaged_seconds UInt32, bounce UInt8, confirmed_purchase UInt8, cart_abandoned UInt8, serving_build_id String",
        "mart_product_performance_daily": "activity_date Date, product_id String, product_name String, category String, country_code String, city String, paid_orders UInt32, customer_count UInt32, units_sold UInt64, recognized_revenue Decimal(18,2), product_views UInt32, serving_build_id String",
        "mart_web_experience_daily": "activity_date Date, page_url String, country_code String, city String, traffic_source String, device_type String, event_count UInt32, session_count UInt32, avg_engaged_time_seconds Float64, avg_response_time_ms Float64, p95_response_time_ms Float64, error_count UInt32, error_rate Float64, request_correlation_coverage Float64, serving_build_id String",
        "mart_navigation_paths": "activity_date Date, from_page String, to_page String, country_code String, city String, traffic_source String, device_type String, transition_count UInt64, session_count UInt32, serving_build_id String",
        "mart_personalization_candidates": "user_id String, product_id String, product_name String, category String, membership_type String, country_code String, city String, product_view_count UInt32, add_to_cart_count UInt32, checkout_start_count UInt32, last_interest_at DateTime('UTC'), candidate_reason String, serving_build_id String",
        "mart_context_impact_daily": "activity_date Date, country_code String, city String, session_count UInt32, event_count UInt32, product_view_count UInt32, add_to_cart_count UInt32, confirmed_purchase_count UInt32, recognized_revenue Decimal(18,2), avg_temperature_c Nullable(Float64), precipitation_mm Nullable(Float64), is_holiday UInt8, serving_build_id String",
    }
    for table, definition in columns.items():
        client.command(
            f"CREATE TABLE IF NOT EXISTS {DATABASE}.{table} "
            f"({definition}) ENGINE = MergeTree ORDER BY serving_build_id"
        )

        client.command(
            f"CREATE OR REPLACE VIEW {DATABASE}.v_{table} AS "
            f"SELECT * FROM {DATABASE}.{table} WHERE serving_build_id = "
            f"(SELECT argMax(active_build_id, activated_at) "
            f"FROM {DATABASE}.serving_control WHERE status = 'ACTIVE')"
        )

    # Optional clickstream identifiers are legitimately NULL for some events.
    nullable_event_columns = (
        "request_id",
        "product_id",
        "checkout_id",
        "order_id",
    )

    for column_name in nullable_event_columns:
        client.command(
            f"ALTER TABLE {DATABASE}.fact_clickstream_event "
            f"MODIFY COLUMN {column_name} Nullable(String)"
        )

REQUIRED_DATETIME_COLUMNS = {
    "dim_user_current": ("effective_from",),
    "fact_clickstream_event": ("event_timestamp",),
    "fact_order": ("order_timestamp",),
    "fact_order_item": ("order_timestamp",),
    "mart_journey_session": (
        "session_start",
        "session_end",
    ),
    "mart_personalization_candidates": (
        "last_interest_at",
    ),
}


def _assert_required_datetime_values(
    table: str,
    dataframe: DataFrame,
) -> None:
    """Fail clearly before ClickHouse receives an invalid NULL DateTime value."""
    required_columns = [
        column
        for column in REQUIRED_DATETIME_COLUMNS.get(table, ())
        if column in dataframe.columns
    ]

    if not required_columns:
        return

    checks = [
        F.sum(
            F.when(
                F.col(column).isNull(),
                F.lit(1),
            ).otherwise(F.lit(0))
        )
        .cast("long")
        .alias(column)
        for column in required_columns
    ]

    result = dataframe.agg(*checks).first().asDict()

    invalid = {
        column: int(result.get(column) or 0)
        for column in required_columns
        if int(result.get(column) or 0) > 0
    }

    if invalid:
        detail = ", ".join(
            f"{column}={count}"
            for column, count in invalid.items()
        )

        raise RuntimeError(
            f"Serving frame {table} has NULL required DateTime values: {detail}"
        )

def write_dataframe(
    client,
    table: str,
    dataframe: DataFrame,
    columns: Iterable[str],
    chunk_size: int = 2000,
) -> int:
    """Insert rows in chunks with clear table-level failure reporting."""
    _assert_required_datetime_values(table, dataframe)

    names = list(columns)
    rows: list[list[object]] = []
    inserted = 0
    chunk_number = 0

    def flush_rows() -> None:
        nonlocal inserted, chunk_number

        if not rows:
            return

        chunk_number += 1

        try:
            client.insert(
                f"{DATABASE}.{table}",
                rows,
                column_names=names,
            )
        except Exception as error:
            raise RuntimeError(
                f"ClickHouse insert failed for table={table}, "
                f"chunk={chunk_number}, rows={len(rows)}: "
                f"{type(error).__name__}: {error}"
            ) from error

        inserted += len(rows)
        rows.clear()

    for row in dataframe.select(*names).toLocalIterator():
        rows.append([row[name] for name in names])

        if len(rows) >= chunk_size:
            flush_rows()

    flush_rows()

    return inserted


def _parse_debezium_timestamp(raw_value):
    """Parse PostgreSQL Debezium timestamps in ISO, milliseconds, or microseconds."""
    value = F.trim(raw_value.cast("string"))

    epoch_microseconds = F.when(
        value.rlike(r"^-?[0-9]{16,}$"),
        F.to_timestamp(F.from_unixtime(value.cast("double") / F.lit(1_000_000.0))),
    )

    epoch_milliseconds = F.when(
        value.rlike(r"^-?[0-9]{13,15}$"),
        F.to_timestamp(F.from_unixtime(value.cast("double") / F.lit(1_000.0))),
    )

    iso_timestamp = F.coalesce(
        F.to_timestamp(value),
        F.to_timestamp(
            value,
            "yyyy-MM-dd'T'HH:mm:ssX",
        ),
        F.to_timestamp(
            value,
            "yyyy-MM-dd'T'HH:mm:ss.SSSX",
        ),
        F.to_timestamp(
            value,
            "yyyy-MM-dd'T'HH:mm:ss.SSSSSSX",
        ),
    )

    return F.coalesce(
        epoch_microseconds,
        epoch_milliseconds,
        iso_timestamp,
    )

def current_orders(spark: SparkSession) -> DataFrame:
    """Resolve current orders and parse Debezium timestamps safely."""
    parsed = spark.table(f"{CATALOG}.processed.orders_cdc_clean")

    window = (
        Window.partitionBy("order_id")
        .orderBy(
            F.col("source_lsn").desc_nulls_last(),
            F.col("kafka_partition").desc(),
            F.col("kafka_offset").desc(),
        )
    )

    latest = (
        parsed
        .withColumn(
            "row_number",
            F.row_number().over(window),
        )
        .filter("row_number = 1")
        .filter(F.col("operation") != "d")
        .withColumn(
            "record",
            F.from_json("after_json", ORDER_SCHEMA),
        )
        .filter(F.col("record").isNotNull())
        .withColumn(
            "order_timestamp_raw",
            F.get_json_object(
                "after_json",
                "$.order_timestamp",
            ),
        )
        .withColumn(
            "order_timestamp",
            _parse_debezium_timestamp(
                F.col("order_timestamp_raw")
            ),
        )
    )

    return latest.select(
        "order_id",
        F.col("record.user_id").alias("user_id"),
        F.col("record.checkout_id").alias("checkout_id"),
        "order_timestamp",
        F.col("record.order_status").alias("order_status"),
        F.col("record.payment_status").alias("payment_status"),
        F.col("record.currency").alias("currency"),
        F.col("record.total_amount")
        .cast(DecimalType(18, 2))
        .alias("total_amount"),
        "source_lsn",
        "kafka_partition",
        "kafka_offset",
    )


def current_items(spark: SparkSession) -> DataFrame:
    """Resolve the latest order-item state, excluding an entity whose newest event is a delete."""
    parsed = spark.table(f"{CATALOG}.processed.order_items_cdc_clean")
    window = Window.partitionBy("order_item_id").orderBy(
        F.col("source_lsn").desc_nulls_last(),
        F.col("kafka_partition").desc(),
        F.col("kafka_offset").desc(),
    )
    latest = (
        parsed.withColumn("row_number", F.row_number().over(window))
        .filter("row_number = 1")
        .filter(F.col("operation") != "d")
        .withColumn("record", F.from_json("after_json", ITEM_SCHEMA))
        .filter(F.col("record").isNotNull())
    )
    return latest.select(
        "order_item_id",
        F.col("record.order_id").alias("order_id"),
        F.col("record.product_id").alias("product_id"),
        F.col("record.quantity").cast("int").alias("quantity"),
        F.col("record.unit_price").cast(DecimalType(18, 2)).alias("unit_price"),
        F.col("record.line_total").cast(DecimalType(18, 2)).alias("line_total"),
        "source_lsn",
        "kafka_partition",
        "kafka_offset",
    )
