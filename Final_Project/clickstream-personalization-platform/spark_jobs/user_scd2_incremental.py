#!/usr/bin/env python3
"""Build a failure-safe incremental User Profile SCD Type 2 table."""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime

from pyspark.sql import DataFrame, SparkSession, Window
from pyspark.sql import functions as F
from pyspark.sql.types import BooleanType, StringType, StructField, StructType

CATALOG = "ecommerce"
SOURCE = f"{CATALOG}.processed.users_cdc_clean"
TARGET = f"{CATALOG}.processed.user_profile_scd2"
WATERMARKS = f"{CATALOG}.audit.watermarks"
PIPELINE_RUNS = f"{CATALOG}.audit.pipeline_runs"
PROFILE_FIELDS = (
    "email",
    "first_name",
    "last_name",
    "membership_type",
    "account_status",
    "country_code",
    "city",
)
USER_SCHEMA = StructType(
    [
        StructField("user_id", StringType(), True),
        *[StructField(name, StringType(), True) for name in PROFILE_FIELDS],
        StructField("created_at", StringType(), True),
        StructField("updated_at", StringType(), True),
    ]
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Incremental User SCD Type 2 materialization")
    parser.add_argument("--run-id", required=True)
    return parser.parse_args()


def now_utc() -> datetime:
    return datetime.now(UTC)


def make_spark() -> SparkSession:
    password = os.environ.get("POSTGRES_PASSWORD", "")
    user = os.environ.get("POSTGRES_USER", "ecommerce_user")
    return (
        SparkSession.builder.appName("user-scd2-incremental")
        .config("spark.sql.catalog.ecommerce.jdbc.user", user)
        .config("spark.sql.catalog.ecommerce.jdbc.password", password)
        .config("spark.sql.catalog.ecommerce.type", "jdbc")
        .config("spark.sql.catalog.ecommerce.cache-enabled", "false")
        .getOrCreate()
    )


def latest_watermark(spark: SparkSession) -> int:
    """Read the last committed SCD2 LSN. Missing data means first materialization."""
    rows = (
        spark.table(WATERMARKS)
        .filter((F.col("job_name") == "user_scd2") & (F.col("source_name") == "users_cdc_clean"))
        .orderBy(F.col("updated_at").desc())
        .limit(1)
        .collect()
    )
    return int(rows[0]["last_processed_offset"] or 0) if rows else 0


def normalize_events(spark: SparkSession) -> DataFrame:
    """Normalize user CDC while retaining update history and delete semantics."""
    raw = spark.table(SOURCE)
    after = F.from_json("after_json", USER_SCHEMA)
    before = F.from_json("before_json", USER_SCHEMA)
    record = F.when(F.col("operation") == "d", before).otherwise(after)
    parsed = raw.filter(F.col("operation").isin("r", "c", "u", "d")).withColumn("record", record)
    return parsed.select(
        F.col("record.user_id").alias("user_id"),
        *[F.col(f"record.{field}").alias(field) for field in PROFILE_FIELDS],
        F.to_timestamp(F.col("record.created_at"), "yyyy-MM-dd'T'HH:mm:ssX").alias("created_at"),
        F.to_timestamp(F.col("record.updated_at"), "yyyy-MM-dd'T'HH:mm:ssX").alias("updated_at"),
        F.col("operation"),
        F.col("source_lsn").cast("long").alias("source_lsn"),
        F.col("source_ts_ms").cast("long").alias("source_ts_ms"),
        F.col("kafka_partition").cast("int").alias("kafka_partition"),
        F.col("kafka_offset").cast("long").alias("kafka_offset"),
        F.col("processed_at"),
    ).filter(F.col("user_id").isNotNull() & (F.length(F.trim("user_id")) > 0))


def build_user_history(events: DataFrame) -> DataFrame:
    """Create valid SCD2 ranges from one affected user's complete CDC history."""
    order = Window.partitionBy("user_id").orderBy(
        F.col("source_lsn").asc_nulls_last(),
        F.col("source_ts_ms").asc_nulls_last(),
        F.col("kafka_partition"),
        F.col("kafka_offset"),
    )
    profile_hash = F.sha2(
        F.concat_ws("||", *[F.coalesce(F.col(name), F.lit("<NULL>")) for name in PROFILE_FIELDS]),
        256,
    )
    prepared = (
        events.withColumn("is_deleted", F.col("operation") == F.lit("d"))
        .withColumn(
            "account_status",
            F.when(F.col("operation") == "d", F.lit("deleted")).otherwise(F.col("account_status")),
        )
        .withColumn(
            "profile_hash", F.concat_ws("|", profile_hash, F.col("is_deleted").cast("string"))
        )
        .withColumn("previous_hash", F.lag("profile_hash").over(order))
        .filter(F.col("previous_hash").isNull() | (F.col("previous_hash") != F.col("profile_hash")))
        .withColumn("version_sequence", F.row_number().over(order))
        .withColumn(
            "safe_ts_ms",
            F.coalesce(
                F.col("source_ts_ms"), (F.unix_timestamp("processed_at") * F.lit(1000)).cast("long")
            ),
        )
        # Add version_sequence microseconds so same-millisecond changes keep valid ranges.
        .withColumn(
            "effective_from", F.expr("timestamp_micros(safe_ts_ms * 1000 + version_sequence)")
        )
    )
    version_order = Window.partitionBy("user_id").orderBy(
        "effective_from", "source_lsn", "kafka_partition", "kafka_offset"
    )
    return (
        prepared.withColumn("effective_to", F.lead("effective_from").over(version_order))
        .withColumn("is_current", F.col("effective_to").isNull().cast(BooleanType()))
        .select(
            "user_id",
            *PROFILE_FIELDS,
            "is_deleted",
            "effective_from",
            "effective_to",
            "is_current",
            "version_sequence",
            "source_lsn",
            "created_at",
            "updated_at",
            F.current_timestamp().alias("processed_at"),
        )
    )


def validate_scd2(df: DataFrame) -> dict[str, int]:
    """Reject a materialization that does not preserve one valid current version per user."""
    users = df.select("user_id").distinct().count()
    current = df.filter("is_current = true").count()
    duplicate_current = (
        df.filter("is_current = true").groupBy("user_id").count().filter("count != 1").count()
    )
    invalid_ranges = (
        df.filter("is_current = false")
        .filter(F.col("effective_to").isNull() | (F.col("effective_to") <= F.col("effective_from")))
        .count()
    )
    if users == 0 or current != users or duplicate_current or invalid_ranges:
        raise RuntimeError(
            f"Invalid SCD2 result: users={users}, current={current}, duplicate_current={duplicate_current}, invalid_ranges={invalid_ranges}"
        )
    return {
        "users": users,
        "current_rows": current,
        "duplicate_current": duplicate_current,
        "invalid_ranges": invalid_ranges,
    }


def record_run(
    spark: SparkSession,
    run_id: str,
    status: str,
    started: datetime,
    *,
    input_count: int,
    output_count: int,
    error: str | None = None,
) -> None:
    schema = "run_id string, job_name string, source_name string, status string, started_at timestamp, finished_at timestamp, input_count long, accepted_count long, invalid_count long, duplicate_count long, output_count long, error_message string, recorded_at timestamp"
    spark.createDataFrame(
        [
            (
                run_id,
                "user_scd2",
                "users_cdc_clean",
                status,
                started,
                now_utc(),
                input_count,
                output_count,
                0,
                0,
                output_count,
                error,
                now_utc(),
            )
        ],
        schema,
    ).writeTo(PIPELINE_RUNS).append()


def main() -> int:
    args = parse_args()
    spark: SparkSession | None = None
    started = now_utc()
    input_count = output_count = 0
    try:
        spark = make_spark()
        all_events = normalize_events(spark)
        watermark = latest_watermark(spark)
        new_events = all_events.filter(F.col("source_lsn") > F.lit(watermark))
        affected = new_events.select("user_id").distinct()
        input_count = new_events.count()
        if input_count == 0:
            record_run(spark, args.run_id, "PASSED", started, input_count=0, output_count=0)
            return 0
        affected_history = all_events.join(affected, "user_id", "inner")
        rebuilt = build_user_history(affected_history)
        current = spark.table(TARGET)
        unaffected = current.join(affected, "user_id", "left_anti")
        next_table = unaffected.unionByName(rebuilt, allowMissingColumns=True)
        metrics = validate_scd2(next_table)
        output_count = next_table.count()
        next_table.createOrReplaceTempView("next_user_profile_scd2")
        # Iceberg replaces the metadata pointer only after the new data was written successfully.
        spark.sql(
            f"CREATE OR REPLACE TABLE {TARGET} USING iceberg AS SELECT * FROM next_user_profile_scd2"
        )
        max_lsn = new_events.agg(F.max("source_lsn").alias("max_lsn")).collect()[0]["max_lsn"]
        spark.createDataFrame(
            [("user_scd2", "users_cdc_clean", str(max_lsn), int(max_lsn or 0), None, now_utc())],
            "job_name string, source_name string, last_processed_id string, last_processed_offset long, last_snapshot_id string, updated_at timestamp",
        ).writeTo(WATERMARKS).append()
        record_run(
            spark,
            args.run_id,
            "PASSED",
            started,
            input_count=input_count,
            output_count=output_count,
        )
        print(
            json.dumps(
                {
                    "status": "PASSED",
                    "run_id": args.run_id,
                    "incremental_events": input_count,
                    "rows": output_count,
                    **metrics,
                }
            )
        )
        return 0
    except Exception as error:
        if spark is not None:
            try:
                record_run(
                    spark,
                    args.run_id,
                    "FAILED",
                    started,
                    input_count=input_count,
                    output_count=output_count,
                    error=f"{type(error).__name__}: {error}",
                )
            except Exception:
                pass
        print(json.dumps({"status": "FAILED", "error": f"{type(error).__name__}: {error}"}))
        return 2
    finally:
        if spark is not None:
            spark.stop()


if __name__ == "__main__":
    raise SystemExit(main())
