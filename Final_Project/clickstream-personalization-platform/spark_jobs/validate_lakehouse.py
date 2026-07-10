#!/usr/bin/env python3
"""Validate a stable completed Spark micro-batch before ClickHouse publication."""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pyspark.sql import DataFrame, SparkSession, functions as F

CATALOG = "ecommerce"
REPORTS = Path("/opt/project/reports")
RUNTIME = Path("/opt/project/runtime")

CLEAN_TABLES = {
    "clickstream": "clickstream_clean",
    "web_logs": "webserver_logs_clean",
    "users_cdc": "users_cdc_clean",
    "orders_cdc": "orders_cdc_clean",
    "order_items_cdc": "order_items_cdc_clean",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate the Clickstream Lakehouse")
    parser.add_argument("--run-id", required=True)
    return parser.parse_args()


def make_spark() -> SparkSession:
    return (
        SparkSession.builder.appName("validate-lakehouse")
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


def read_completed_batch_id() -> int:
    """Read the last fully completed Spark micro-batch.

    Raw can already contain records from a newer batch currently being processed.
    Those records must not enter validation until Clean or Quarantine is complete.
    """
    status_path = RUNTIME / "streaming_status.json"

    try:
        status = json.loads(status_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(
            "Streaming status is missing or invalid; cannot create validation cutoff"
        ) from error

    batch_id = status.get("last_successful_batch_id")

    if batch_id is None:
        raise RuntimeError(
            "No completed Spark micro-batch is recorded; validation is unsafe"
        )

    return int(batch_id)


def source_record_ids(raw_cutoff: DataFrame, source_name: str) -> DataFrame:
    """Return physical Kafka record IDs for one source inside the cutoff."""
    return (
        raw_cutoff.filter(F.col("source_name") == source_name)
        .select("source_record_id")
        .where(F.col("source_record_id").isNotNull())
        .distinct()
    )


def bounded_clean(
    spark: SparkSession,
    table_name: str,
    record_ids: DataFrame,
) -> DataFrame:
    """Restrict Clean data to the exact same Raw validation boundary."""
    return spark.table(f"{CATALOG}.processed.{table_name}").join(
        record_ids,
        "source_record_id",
        "inner",
    )


def check_scd2(spark: SparkSession) -> tuple[bool, dict[str, int]]:
    table = spark.table(f"{CATALOG}.processed.user_profile_scd2")

    users = table.select("user_id").distinct().count()
    current_rows = table.filter("is_current = true").count()

    duplicate_current = (
        table.filter("is_current = true")
        .groupBy("user_id")
        .count()
        .filter("count != 1")
        .count()
    )

    invalid_ranges = (
        table.filter("is_current = false")
        .filter(
            F.col("effective_to").isNull()
            | (F.col("effective_to") <= F.col("effective_from"))
        )
        .count()
    )

    passed = (
        users > 0
        and current_rows == users
        and duplicate_current == 0
        and invalid_ranges == 0
    )

    return passed, {
        "users": users,
        "current_rows": current_rows,
        "duplicate_current": duplicate_current,
        "invalid_ranges": invalid_ranges,
    }


def write_report(payload: dict[str, Any]) -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)

    (REPORTS / "validation_latest.json").write_text(
        json.dumps(payload, indent=2, default=str) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    args = parse_args()

    spark: SparkSession | None = None
    raw_cutoff: DataFrame | None = None

    validation_id = (
        f"validation_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}_"
        f"{args.run_id[-8:]}"
    )

    try:
        spark = make_spark()

        cutoff_batch_id = read_completed_batch_id()

        raw_cutoff = (
            spark.table(f"{CATALOG}.raw.kafka_messages")
            .filter(F.col("stream_batch_id") <= F.lit(cutoff_batch_id))
            .cache()
        )

        raw_cutoff.count()

        quarantine = spark.table(f"{CATALOG}.audit.quarantine_records")

        details: dict[str, Any] = {}
        bounded_tables: dict[str, DataFrame] = {}

        quality_ok = True

        for source_name, clean_table in CLEAN_TABLES.items():
            record_ids = source_record_ids(raw_cutoff, source_name)

            raw_count = record_ids.count()

            clean_df = bounded_clean(
                spark,
                clean_table,
                record_ids,
            )

            clean_count = clean_df.count()

            quarantine_count = (
                quarantine.filter(F.col("source_name") == source_name)
                .join(record_ids, "source_record_id", "inner")
                .count()
            )

            reconciled = raw_count == clean_count + quarantine_count

            details[source_name] = {
                "raw": raw_count,
                "clean": clean_count,
                "quarantine": quarantine_count,
                "reconciled": reconciled,
            }

            bounded_tables[source_name] = clean_df
            quality_ok = quality_ok and reconciled

        orders = bounded_tables["orders_cdc"]
        order_items = bounded_tables["order_items_cdc"]

        order_item_orphans = (
            order_items.filter(F.col("order_id").isNotNull())
            .select("order_id")
            .distinct()
            .join(
                orders.select("order_id").distinct(),
                "order_id",
                "left_anti",
            )
            .count()
        )

        product_ids = (
            spark.table(f"{CATALOG}.processed.product_catalog_clean")
            .select("product_id")
            .distinct()
        )

        clickstream = bounded_tables["clickstream"]
        web_logs = bounded_tables["web_logs"]

        clickstream_product_orphans = (
            clickstream.filter(
                F.col("product_id").isNotNull()
                & (F.length("product_id") > 0)
            )
            .join(product_ids, "product_id", "left_anti")
            .count()
        )

        eligible = (
            clickstream.filter(F.col("request_id").isNotNull())
            .count()
        )

        matched = (
            clickstream.filter(F.col("request_id").isNotNull())
            .join(
                web_logs.select("request_id").distinct(),
                "request_id",
                "inner",
            )
            .count()
        )

        request_correlation_coverage = (
            1.0 if eligible == 0 else matched / eligible
        )

        relationship_ok = (
            order_item_orphans == 0
            and clickstream_product_orphans == 0
        )

        scd2_ok, scd2_metrics = check_scd2(spark)

        coverage_status = (
            "PASSED"
            if request_correlation_coverage >= 0.95
            else "PARTIAL"
        )

        status = (
            "PASSED"
            if quality_ok and relationship_ok and scd2_ok
            else "FAILED"
        )

        payload = {
            "validation_id": validation_id,
            "status": status,
            "quality_status": "PASSED" if quality_ok else "FAILED",
            "relationship_status": (
                "PASSED" if relationship_ok else "FAILED"
            ),
            "scd2_status": "PASSED" if scd2_ok else "FAILED",
            "coverage_status": coverage_status,
            "cutoff": {
                "last_successful_stream_batch_id": cutoff_batch_id,
                "rule": (
                    "Only Raw records with stream_batch_id "
                    "<= cutoff are validated"
                ),
            },
            "details": {
                **details,
                "order_item_orphans": order_item_orphans,
                "clickstream_product_orphans": clickstream_product_orphans,
                "request_correlation_coverage": request_correlation_coverage,
                "scd2": scd2_metrics,
            },
        }

        spark.createDataFrame(
            [
                (
                    validation_id,
                    status,
                    f"stream_batch_id <= {cutoff_batch_id}",
                    json.dumps(
                        {
                            name: value["raw"]
                            for name, value in details.items()
                        }
                    ),
                    payload["quality_status"],
                    payload["relationship_status"],
                    payload["scd2_status"],
                    coverage_status,
                    json.dumps(payload["details"], default=str),
                    datetime.now(UTC),
                )
            ],
            """
            validation_id string,
            status string,
            cutoff_description string,
            source_snapshot_summary string,
            quality_status string,
            relationship_status string,
            scd2_status string,
            coverage_status string,
            details_json string,
            created_at timestamp
            """,
        ).writeTo(f"{CATALOG}.audit.validation_runs").append()

        write_report(payload)

        print(json.dumps(payload, default=str))

        return 0 if status == "PASSED" else 2

    except Exception as error:
        failure = {
            "validation_id": validation_id,
            "status": "FAILED",
            "error": f"{type(error).__name__}: {error}",
        }

        write_report(failure)
        print(json.dumps(failure))

        return 2

    finally:
        if raw_cutoff is not None:
            raw_cutoff.unpersist()

        if spark is not None:
            spark.stop()


if __name__ == "__main__":
    raise SystemExit(main())