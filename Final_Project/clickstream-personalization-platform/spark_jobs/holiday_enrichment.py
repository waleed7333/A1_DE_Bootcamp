#!/usr/bin/env python3
"""Fetch missing Calendarific holiday coverage for clickstream countries and years."""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from typing import Any

import requests
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

CATALOG = "ecommerce"
API_URL = "https://calendarific.com/api/v2/holidays"
REQUEST_TIMEOUT_SECONDS = 10


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Enrich Clickstream with public holidays")
    parser.add_argument("--run-id", required=True)
    return parser.parse_args()


def make_spark() -> SparkSession:
    return (
        SparkSession.builder.appName("holiday-enrichment")
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


def _failure_row(
    run_id: str,
    request_key: str,
    http_status: int | None,
    error_message: str,
) -> tuple[Any, ...]:
    return (
        run_id,
        "calendarific",
        request_key,
        http_status,
        error_message,
        1,
        "FAILED",
        datetime.now(UTC),
    )


def main() -> int:
    args = parse_args()
    spark: SparkSession | None = None

    try:
        api_key = os.environ.get("CALENDARIFIC_API_KEY", "").strip()

        if not api_key or "CHANGE_ME" in api_key:
            raise RuntimeError("CALENDARIFIC_API_KEY is required")

        spark = make_spark()
        spark.sparkContext.setLogLevel("WARN")

        requested = (
            spark.table(f"{CATALOG}.processed.clickstream_clean")
            .filter(F.col("geo_country_code").isNotNull())
            .select(
                F.col("geo_country_code").alias("country_code"),
                F.year("event_timestamp").alias("year"),
            )
            .distinct()
        )

        existing = (
            spark.table(f"{CATALOG}.processed.holidays_clean")
            .select("country_code", "year")
            .distinct()
        )

        keys = requested.join(existing, ["country_code", "year"], "left_anti").orderBy(
            "country_code", "year"
        )

        rows = list(keys.toLocalIterator())

        holidays: list[tuple[Any, ...]] = []
        failures: list[tuple[Any, ...]] = []

        for row in rows:
            country = str(row["country_code"])
            year = int(row["year"])
            request_key = f"{country}|{year}"

            try:
                response = requests.get(
                    API_URL,
                    params={
                        "api_key": api_key,
                        "country": country,
                        "year": year,
                    },
                    timeout=REQUEST_TIMEOUT_SECONDS,
                )

                http_status = response.status_code
                response.raise_for_status()

                values = (response.json().get("response") or {}).get("holidays") or []

                for item in values:
                    date_value = (item.get("date") or {}).get("iso")

                    if not date_value:
                        continue

                    holiday_type = ",".join(item.get("type") or [])
                    holiday_name = item.get("name") or "Unknown"

                    holidays.append(
                        (
                            f"{country}|{date_value}|{holiday_name}",
                            country,
                            date_value,
                            holiday_name,
                            holiday_type,
                            year,
                            "complete",
                            datetime.now(UTC),
                        )
                    )

                if not values:
                    holidays.append(
                        (
                            f"{country}|{year}|NO_HOLIDAYS",
                            country,
                            f"{year}-01-01",
                            "No returned holidays",
                            "",
                            year,
                            "partial",
                            datetime.now(UTC),
                        )
                    )

            except Exception as error:
                failures.append(
                    _failure_row(
                        run_id=args.run_id,
                        request_key=request_key,
                        http_status=locals().get("http_status"),
                        error_message=f"{type(error).__name__}: Calendarific request failed",
                    )
                )

        if holidays:
            (
                spark.createDataFrame(
                    holidays,
                    (
                        "holiday_key string, "
                        "country_code string, "
                        "holiday_date string, "
                        "holiday_name string, "
                        "holiday_type string, "
                        "year int, "
                        "coverage_status string, "
                        "fetched_at timestamp"
                    ),
                )
                .withColumn("holiday_date", F.to_date("holiday_date"))
                .writeTo(f"{CATALOG}.processed.holidays_clean")
                .append()
            )

        if failures:
            spark.createDataFrame(
                failures,
                (
                    "run_id string, "
                    "api_name string, "
                    "request_key string, "
                    "http_status int, "
                    "error_message string, "
                    "retry_count int, "
                    "status string, "
                    "occurred_at timestamp"
                ),
            ).writeTo(f"{CATALOG}.audit.external_api_failures").append()

        print(
            json.dumps(
                {
                    "status": "PASSED",
                    "requested_keys": len(rows),
                    "holiday_rows_written": len(holidays),
                    "failed_keys": len(failures),
                },
                sort_keys=True,
            )
        )

        return 0

    except Exception as error:
        print(
            json.dumps(
                {
                    "status": "FAILED",
                    "error": f"{type(error).__name__}: {error}",
                },
                sort_keys=True,
            )
        )

        return 2

    finally:
        if spark is not None:
            spark.stop()


if __name__ == "__main__":
    raise SystemExit(main())
