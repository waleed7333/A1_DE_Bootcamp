#!/usr/bin/env python3
"""Fetch missing Open-Meteo historical weather coverage for clean clickstream events.

The job keeps the project reliable during local demos:
- It requests Open-Meteo once per location/date-range, not once per event hour.
- It uses a short HTTP timeout so an external API cannot block init for a long time.
- Missing weather values remain NULL.
- API failures are recorded in audit.external_api_failures.
"""

from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

import requests
from pyspark.sql import SparkSession, functions as F

CATALOG = "ecommerce"
API_URL = "https://archive-api.open-meteo.com/v1/archive"
REQUEST_TIMEOUT_SECONDS = 8


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Enrich Clickstream with historical weather"
    )
    parser.add_argument("--run-id", required=True)
    return parser.parse_args()


def make_spark() -> SparkSession:
    return (
        SparkSession.builder.appName("weather-enrichment")
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


def condition_name(code: int | None) -> str | None:
    mapping = {
        0: "clear",
        1: "mainly_clear",
        2: "partly_cloudy",
        3: "overcast",
        45: "fog",
        48: "rime_fog",
        51: "drizzle",
        53: "drizzle",
        55: "drizzle",
        61: "rain",
        63: "rain",
        65: "rain",
        71: "snow",
        73: "snow",
        75: "snow",
        80: "rain_showers",
        81: "rain_showers",
        82: "rain_showers",
        95: "thunderstorm",
    }

    return mapping.get(code, "other") if code is not None else None


def _safe_item(values: list[Any], index: int) -> Any:
    if index < 0 or index >= len(values):
        return None

    return values[index]


def _as_int(value: Any) -> int | None:
    if value is None:
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _request_weather(
    latitude: float,
    longitude: float,
    start_date: str,
    end_date: str,
) -> tuple[int | None, dict[str, Any]]:
    response = requests.get(
        API_URL,
        params={
            "latitude": latitude,
            "longitude": longitude,
            "start_date": start_date,
            "end_date": end_date,
            "hourly": "temperature_2m,precipitation,weather_code",
            "timezone": "UTC",
        },
        timeout=REQUEST_TIMEOUT_SECONDS,
    )

    response.raise_for_status()
    return response.status_code, response.json()


def _weather_result_row(
    weather_key: str,
    latitude: float,
    longitude: float,
    weather_hour: datetime,
    temperature_c: float | None,
    precipitation_mm: float | None,
    weather_code: int | None,
    coverage_status: str,
) -> tuple[Any, ...]:
    return (
        weather_key,
        latitude,
        longitude,
        weather_hour,
        temperature_c,
        precipitation_mm,
        weather_code,
        condition_name(weather_code),
        coverage_status,
        datetime.now(UTC),
    )


def _failure_row(
    run_id: str,
    request_key: str,
    http_status: int | None,
    error_message: str,
    status: str = "FAILED",
) -> tuple[Any, ...]:
    return (
        run_id,
        "open_meteo",
        request_key,
        http_status,
        error_message,
        1,
        status,
        datetime.now(UTC),
    )


def main() -> int:
    args = parse_args()
    spark: SparkSession | None = None

    try:
        spark = make_spark()
        spark.sparkContext.setLogLevel("WARN")

        source = (
            spark.table(f"{CATALOG}.processed.clickstream_clean")
            .filter(
                F.col("geo_latitude").isNotNull()
                & F.col("geo_longitude").isNotNull()
            )
            .select(
                F.round("geo_latitude", 3).alias("latitude"),
                F.round("geo_longitude", 3).alias("longitude"),
                F.date_trunc("hour", "event_timestamp").alias("weather_hour"),
            )
            .distinct()
            .withColumn(
                "weather_key",
                F.concat_ws(
                    "|",
                    "latitude",
                    "longitude",
                    F.date_format("weather_hour", "yyyy-MM-dd HH:mm:ss"),
                ),
            )
        )

        existing = (
            spark.table(f"{CATALOG}.processed.weather_clean")
            .select("weather_key")
            .distinct()
        )

        keys = (
            source
            .join(existing, "weather_key", "left_anti")
            .select("weather_key", "latitude", "longitude", "weather_hour")
            .orderBy("latitude", "longitude", "weather_hour")
        )

        rows = list(keys.toLocalIterator())

        successful: list[tuple[Any, ...]] = []
        failures: list[tuple[Any, ...]] = []

        grouped: dict[tuple[float, float], list[Any]] = defaultdict(list)

        today_utc = datetime.now(UTC).date()

        for row in rows:
            weather_hour = row["weather_hour"]
            latitude = float(row["latitude"])
            longitude = float(row["longitude"])
            weather_key = str(row["weather_key"])

            # Open-Meteo archive data may not be available for today/current live
            # records yet. Keep the value NULL instead of blocking or inventing it.
            if weather_hour.date() >= today_utc:
                successful.append(
                    _weather_result_row(
                        weather_key=weather_key,
                        latitude=latitude,
                        longitude=longitude,
                        weather_hour=weather_hour,
                        temperature_c=None,
                        precipitation_mm=None,
                        weather_code=None,
                        coverage_status="unavailable",
                    )
                )

                failures.append(
                    _failure_row(
                        run_id=args.run_id,
                        request_key=weather_key,
                        http_status=None,
                        error_message=(
                            "Open-Meteo archive data is not requested for "
                            "current or future UTC dates"
                        ),
                        status="SKIPPED",
                    )
                )

                continue

            grouped[(latitude, longitude)].append(row)

        for (latitude, longitude), group_rows in grouped.items():
            dates = sorted({item["weather_hour"].date().isoformat() for item in group_rows})
            start_date = dates[0]
            end_date = dates[-1]
            request_key = f"{latitude}|{longitude}|{start_date}|{end_date}"

            try:
                http_status, response_json = _request_weather(
                    latitude=latitude,
                    longitude=longitude,
                    start_date=start_date,
                    end_date=end_date,
                )

                hourly = response_json.get("hourly") or {}
                times = hourly.get("time") or []
                time_index = {value: index for index, value in enumerate(times)}

                temperatures = hourly.get("temperature_2m") or []
                precipitation = hourly.get("precipitation") or []
                weather_codes = hourly.get("weather_code") or []

                for item in group_rows:
                    weather_hour = item["weather_hour"]
                    weather_key = str(item["weather_key"])
                    timestamp = weather_hour.strftime("%Y-%m-%dT%H:00")
                    index = time_index.get(timestamp, -1)

                    if index < 0:
                        successful.append(
                            _weather_result_row(
                                weather_key=weather_key,
                                latitude=latitude,
                                longitude=longitude,
                                weather_hour=weather_hour,
                                temperature_c=None,
                                precipitation_mm=None,
                                weather_code=None,
                                coverage_status="missing",
                            )
                        )

                        failures.append(
                            _failure_row(
                                run_id=args.run_id,
                                request_key=weather_key,
                                http_status=http_status,
                                error_message=(
                                    "Requested weather hour is missing from "
                                    "Open-Meteo response"
                                ),
                            )
                        )

                        continue

                    code = _as_int(_safe_item(weather_codes, index))

                    successful.append(
                        _weather_result_row(
                            weather_key=weather_key,
                            latitude=latitude,
                            longitude=longitude,
                            weather_hour=weather_hour,
                            temperature_c=_safe_item(temperatures, index),
                            precipitation_mm=_safe_item(precipitation, index),
                            weather_code=code,
                            coverage_status="complete",
                        )
                    )

            except Exception as error:
                error_message = f"{type(error).__name__}: {error}"

                for item in group_rows:
                    weather_hour = item["weather_hour"]
                    weather_key = str(item["weather_key"])

                    successful.append(
                        _weather_result_row(
                            weather_key=weather_key,
                            latitude=latitude,
                            longitude=longitude,
                            weather_hour=weather_hour,
                            temperature_c=None,
                            precipitation_mm=None,
                            weather_code=None,
                            coverage_status="failed",
                        )
                    )

                failures.append(
                    _failure_row(
                        run_id=args.run_id,
                        request_key=request_key,
                        http_status=None,
                        error_message=error_message,
                    )
                )

        if successful:
            spark.createDataFrame(
                successful,
                (
                    "weather_key string, "
                    "latitude double, "
                    "longitude double, "
                    "weather_hour timestamp, "
                    "temperature_c double, "
                    "precipitation_mm double, "
                    "weather_code int, "
                    "weather_condition string, "
                    "coverage_status string, "
                    "fetched_at timestamp"
                ),
            ).writeTo(f"{CATALOG}.processed.weather_clean").append()

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
                    "location_requests": len(grouped),
                    "weather_rows_written": len(successful),
                    "failed_or_skipped_keys": len(failures),
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