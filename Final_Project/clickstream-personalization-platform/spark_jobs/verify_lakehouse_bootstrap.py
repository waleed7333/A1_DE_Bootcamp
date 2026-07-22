#!/usr/bin/env python3
"""Read-only verification for the initialized Iceberg Lakehouse."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

PROJECT_DATA = Path("/opt/project/data")
PROJECT_RUNTIME = Path("/opt/project/runtime")
MANIFEST_PATH = PROJECT_DATA / "source" / "generation_manifest.json"
CATALOG = "ecommerce"
PROCESSED = (
    "product_catalog_clean",
    "clickstream_clean",
    "webserver_logs_clean",
    "users_cdc_clean",
    "orders_cdc_clean",
    "order_items_cdc_clean",
    "user_profile_scd2",
    "weather_clean",
    "holidays_clean",
)
AUDIT = (
    "pipeline_runs",
    "quality_metrics",
    "quarantine_records",
    "external_api_failures",
    "watermarks",
    "validation_runs",
    "serving_builds",
)
RAW = ("kafka_messages",)


def args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify initialized Iceberg tables")
    parser.add_argument("--run-id", required=True)
    return parser.parse_args()


def write_report(run_id: str, payload: dict) -> None:
    PROJECT_RUNTIME.mkdir(parents=True, exist_ok=True)
    (PROJECT_RUNTIME / f"verify_lakehouse_bootstrap_{run_id}.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )


def make_spark() -> SparkSession:
    return (
        SparkSession.builder.appName("verify-lakehouse-bootstrap")
        .config(
            "spark.sql.catalog.ecommerce.jdbc.user",
            os.environ.get("POSTGRES_USER", "ecommerce_user"),
        )
        .config(
            "spark.sql.catalog.ecommerce.jdbc.password", os.environ.get("POSTGRES_PASSWORD", "")
        )
        .config("spark.sql.catalog.ecommerce.type", "jdbc")
        .getOrCreate()
    )


def main() -> int:
    options = args()
    spark: SparkSession | None = None
    try:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        spark = make_spark()
        missing = []
        for namespace, names in (("raw", RAW), ("processed", PROCESSED), ("audit", AUDIT)):
            for name in names:
                table = f"{CATALOG}.{namespace}.{name}"
                if not spark.catalog.tableExists(table):
                    missing.append(table)
        if missing:
            raise RuntimeError(f"Missing Iceberg tables: {missing}")
        catalog = spark.table(f"{CATALOG}.processed.product_catalog_clean")
        row_count = catalog.count()
        expected = int(manifest["counts"]["products"])
        duplicate_count = catalog.groupBy("product_id").count().filter("count > 1").count()
        invalid_count = catalog.filter(
            F.col("price").isNull()
            | (F.col("price") < 0)
            | F.col("inventory").isNull()
            | (F.col("inventory") < 0)
        ).count()
        if row_count != expected or duplicate_count or invalid_count:
            raise RuntimeError(
                f"Product catalog failed: rows={row_count}/{expected}, duplicates={duplicate_count}, invalid={invalid_count}"
            )
        payload = {
            "status": "PASSED",
            "run_id": options.run_id,
            "finished_at_utc": datetime.now(UTC).isoformat(),
            "table_count": len(RAW) + len(PROCESSED) + len(AUDIT),
            "product_catalog_rows": row_count,
        }
        write_report(options.run_id, payload)
        print(json.dumps(payload))
        return 0
    except Exception as error:
        payload = {
            "status": "FAILED",
            "run_id": options.run_id,
            "finished_at_utc": datetime.now(UTC).isoformat(),
            "error": f"{type(error).__name__}: {error}",
        }
        write_report(options.run_id, payload)
        print(json.dumps(payload), file=sys.stderr)
        return 2
    finally:
        if spark is not None:
            spark.stop()


if __name__ == "__main__":
    raise SystemExit(main())
