#!/usr/bin/env python3
"""Publish one validated Iceberg snapshot to a versioned ClickHouse serving model."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from pyspark.sql import DataFrame, SparkSession, Window, functions as F
from pyspark.sql.types import DecimalType

from serving_common import CATALOG, DATABASE, TABLES, clickhouse_client, current_items, current_orders, ensure_schema, make_spark, write_dataframe

REPORTS = Path("/opt/project/reports")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Publish a validated serving build to ClickHouse")
    parser.add_argument("--run-id", required=True)
    return parser.parse_args()


def build_id(run_id: str) -> str:
    return f"build_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}_{run_id[-8:]}"


def latest_validation_id(spark: SparkSession) -> str:
    row = spark.table(f"{CATALOG}.audit.validation_runs").filter("status = 'PASSED'").orderBy(F.col("created_at").desc()).limit(1).collect()
    if not row:
        raise RuntimeError("No PASSED Lakehouse validation is available for serving publication")
    return str(row[0]["validation_id"])


def add_build(df: DataFrame, identifier: str) -> DataFrame:
    return df.withColumn("serving_build_id", F.lit(identifier))


def asof_attributes( facts: DataFrame, timestamp_col: str, user_col: str, spark: SparkSession, prefix: str, ) -> DataFrame:
    """Attach user attributes as-of fact time, with current-profile fallback.

    Historical demo facts may be older than the first SCD2 effective_from because
    the initial Debezium snapshot happens at init time. In that case, the current
    profile is used as a safe demo fallback instead of returning unknown values.
    """
    profiles = (
        spark.table(f"{CATALOG}.processed.user_profile_scd2")
        .select( "user_id", "membership_type", "account_status", "country_code", "city", "effective_from", "effective_to", ) .alias("p")
    )

    current_profiles = ( spark.table(f"{CATALOG}.processed.user_profile_scd2") .filter("is_current = true") .select(
            F.col("user_id").alias("__current_user_id"),
            F.col("membership_type").alias("__current_membership_type"),
            F.col("account_status").alias("__current_account_status"),
            F.col("country_code").alias("__current_country_code"),
            F.col("city").alias("__current_city"),
        )
        .alias("c")
    )

    fact_alias = facts.alias("f")

    asof_condition = (
        (F.col(f"f.{user_col}") == F.col("p.user_id"))
        & (F.col(f"f.{timestamp_col}") >= F.col("p.effective_from"))
        & (
            F.col("p.effective_to").isNull()
            | (F.col(f"f.{timestamp_col}") < F.col("p.effective_to"))
        )
    )

    current_condition = (
        F.col(f"f.{user_col}") == F.col("c.__current_user_id")
    )

    return (
        fact_alias
        .join(profiles, asof_condition, "left")
        .join(current_profiles, current_condition, "left")
        .select(
            "f.*",
            F.coalesce(
                F.col("p.membership_type"),
                F.col("c.__current_membership_type"),
                F.lit("unknown"),
            ).alias(f"membership_type_at_{prefix}"),
            F.coalesce(
                F.col("p.country_code"),
                F.col("c.__current_country_code"),
                F.lit("unknown"),
            ).alias(f"country_at_{prefix}"),
            F.coalesce(
                F.col("p.city"),
                F.col("c.__current_city"),
                F.lit("unknown"),
            ).alias(f"city_at_{prefix}"),
            F.coalesce(
                F.col("p.account_status"),
                F.col("c.__current_account_status"),
                F.lit("unknown"),
            ).alias(f"account_status_at_{prefix}"),
        )
    )


def build_frames(spark: SparkSession) -> dict[str, DataFrame]:
    """Create the small serving model from verified Iceberg tables."""
    products = spark.table(f"{CATALOG}.processed.product_catalog_clean").select("product_id", "product_name", "category", "price", "inventory")
    current_profiles = spark.table(f"{CATALOG}.processed.user_profile_scd2").filter("is_current = true").select("user_id", "membership_type", "account_status", "country_code", "city", "is_deleted", "effective_from")
    raw_events = spark.table(f"{CATALOG}.processed.clickstream_clean")

    event_enriched = (
        asof_attributes( raw_events, "event_timestamp", "user_id", spark, "event",).select( 
            "event_id", "event_timestamp", F.to_date("event_timestamp").alias("event_date"), 
            "session_id", "request_id", "user_id", "event_type", "page_url", "product_id", 
            "checkout_id", "order_id", "device_type", "traffic_source", "time_on_page_seconds", 
            F.col("late_arrival").cast("int").alias("late_arrival"), 
            F.coalesce( F.col("geo_country_code"), F.lit("unknown"), ).alias("country_code"), 
            F.coalesce( F.col("geo_city"), F.lit("unknown"), ).alias("city"), 
            F.col("geo_latitude").alias("context_geo_latitude"), 
            F.col("geo_longitude").alias("context_geo_longitude"), 
            F.col("geo_timezone").alias("context_geo_timezone"), 
            F.col("membership_type_at_event"), 
            )
    )

    # This dataframe must match ClickHouse fact_clickstream_event exactly.
    events = event_enriched.select( "event_id", "event_timestamp", "event_date", "session_id", "request_id", "user_id", 
                                   "event_type", "page_url", "product_id", "checkout_id", "order_id", "device_type", 
                                   "traffic_source", "time_on_page_seconds", "late_arrival", "country_code", "city", 
                                   "membership_type_at_event", )
    orders_base = current_orders(spark)
    orders = asof_attributes(orders_base, "order_timestamp", "user_id", spark, "order").withColumn("confirmed_purchase", ((F.col("order_status").isin("shipped", "delivered")) & (F.col("payment_status") == "paid")).cast("int")).withColumn("recognized_revenue", F.when(F.col("confirmed_purchase") == 1, F.col("total_amount")).otherwise(F.lit(0).cast(DecimalType(18,2)))).select(
        "order_id", "user_id", "checkout_id", "order_timestamp", F.to_date("order_timestamp").alias("order_date"), "order_status", "payment_status", "total_amount", "confirmed_purchase", "recognized_revenue",
        F.col("country_at_order").alias("country_code"), F.col("city_at_order").alias("city"), F.col("membership_type_at_order"),
    )
    items = current_items(spark).join(orders.select("order_id", "user_id", "order_timestamp", "order_date", "confirmed_purchase", "country_code", "city"), "order_id", "inner").select("order_item_id", "order_id", "user_id", "order_timestamp", "order_date", "product_id", "quantity", "unit_price", "line_total", "confirmed_purchase", "country_code", "city")

    dates = events.select(F.col("event_date").alias("activity_date")).unionByName(orders.select(F.col("order_date").alias("activity_date"))).distinct().filter("activity_date is not null").select(
        "activity_date", F.year("activity_date").cast("int").alias("calendar_year"), F.month("activity_date").cast("int").alias("calendar_month"), F.dayofmonth("activity_date").cast("int").alias("day_of_month"), F.date_format("activity_date", "EEEE").alias("day_name")
    )

    purchase_by_checkout = orders.filter("confirmed_purchase = 1").select("checkout_id", F.lit(1).alias("confirmed_purchase"))
    session = events.groupBy("session_id").agg(
        F.min("event_timestamp").alias("session_start"), F.max("event_timestamp").alias("session_end"), F.min("event_date").alias("activity_date"),
        F.first("user_id", ignorenulls=True).alias("user_id"), F.first("country_code", ignorenulls=True).alias("country_code"), F.first("city", ignorenulls=True).alias("city"), F.first("traffic_source", ignorenulls=True).alias("traffic_source"), F.first("device_type", ignorenulls=True).alias("device_type"),
        F.count("event_id").cast("int").alias("event_count"), F.sum(F.when(F.col("event_type").isin("page_view", "product_view"), 1).otherwise(0)).cast("int").alias("page_navigation_count"),
        F.sum(F.when(F.col("event_type") == "product_view", 1).otherwise(0)).cast("int").alias("product_view_count"), F.sum(F.when(F.col("event_type") == "add_to_cart", 1).otherwise(0)).cast("int").alias("add_to_cart_count"),
        F.sum(F.when(F.col("event_type") == "checkout_start", 1).otherwise(0)).cast("int").alias("checkout_start_count"), F.sum(F.when(F.col("event_type") == "checkout_complete", 1).otherwise(0)).cast("int").alias("checkout_complete_count"),
        F.sum(F.coalesce("time_on_page_seconds", F.lit(0))).cast("int").alias("engaged_seconds"), F.first("checkout_id", ignorenulls=True).alias("checkout_id"),
    ).join(purchase_by_checkout, "checkout_id", "left").withColumn("confirmed_purchase", F.coalesce("confirmed_purchase", F.lit(0)).cast("int")).withColumn("bounce", ((F.col("page_navigation_count") == 1) & (F.col("product_view_count") == 0) & (F.col("add_to_cart_count") == 0) & (F.col("engaged_seconds") < 30)).cast("int")).withColumn("cart_abandoned", ((F.col("add_to_cart_count") > 0) & (F.col("confirmed_purchase") == 0)).cast("int")).drop("checkout_id")

    product_views = events.filter("event_type = 'product_view'").groupBy("event_date", "product_id", "country_code", "city").agg(F.count("event_id").cast("int").alias("product_views"))
    paid_items = items.filter("confirmed_purchase = 1").groupBy("order_date", "product_id", "country_code", "city").agg(F.countDistinct("order_id").cast("int").alias("paid_orders"), F.countDistinct("user_id").cast("int").alias("customer_count"), F.sum("quantity").cast("long").alias("units_sold"), F.sum("line_total").cast(DecimalType(18,2)).alias("recognized_revenue"))
    product_mart = paid_items.join(products, "product_id", "left").join(product_views, (F.col("order_date") == F.col("event_date")) & (paid_items.product_id == product_views.product_id) & (paid_items.country_code == product_views.country_code) & (paid_items.city == product_views.city), "left").select(F.col("order_date").alias("activity_date"), paid_items.product_id, "product_name", "category", paid_items.country_code, paid_items.city, "paid_orders", "customer_count", "units_sold", "recognized_revenue", F.coalesce("product_views", F.lit(0)).cast("int").alias("product_views"))

    logs = spark.table(f"{CATALOG}.processed.webserver_logs_clean").select("request_id", "response_time_ms", "status_code")
    experience = events.join(logs, "request_id", "left").groupBy("event_date", "page_url", "country_code", "city", "traffic_source", "device_type").agg(
        F.count("event_id").cast("int").alias("event_count"), F.countDistinct("session_id").cast("int").alias("session_count"), F.avg("time_on_page_seconds").alias("avg_engaged_time_seconds"),
        F.avg("response_time_ms").alias("avg_response_time_ms"), F.expr("percentile_approx(response_time_ms, 0.95)").cast("double").alias("p95_response_time_ms"),
        F.sum(F.when(F.col("status_code") >= 400, 1).otherwise(0)).cast("int").alias("error_count"),
        (F.sum(F.when(F.col("status_code").isNotNull(), 1).otherwise(0)) / F.count("event_id")).alias("request_correlation_coverage"),
    ).withColumn("error_rate", F.when(F.col("event_count") > 0, F.col("error_count") / F.col("event_count")).otherwise(F.lit(0.0))).select(F.col("event_date").alias("activity_date"), "page_url", "country_code", "city", "traffic_source", "device_type", "event_count", "session_count", F.coalesce("avg_engaged_time_seconds", F.lit(0.0)).alias("avg_engaged_time_seconds"), F.coalesce("avg_response_time_ms", F.lit(0.0)).alias("avg_response_time_ms"), F.coalesce("p95_response_time_ms", F.lit(0.0)).alias("p95_response_time_ms"), "error_count", "error_rate", "request_correlation_coverage")

    nav_events = events.filter(F.col("event_type").isin("page_view", "product_view")).withColumn("previous_page", F.lag("page_url").over(Window.partitionBy("session_id").orderBy("event_timestamp", "event_id"))).filter(F.col("previous_page").isNull() | (F.col("previous_page") != F.col("page_url"))).withColumn("to_page", F.lead("page_url").over(Window.partitionBy("session_id").orderBy("event_timestamp", "event_id"))).filter(F.col("to_page").isNotNull() & (F.col("page_url") != F.col("to_page")))
    navigation = nav_events.groupBy("event_date", F.col("page_url").alias("from_page"), "to_page", "country_code", "city", "traffic_source", "device_type").agg(F.count("event_id").cast("long").alias("transition_count"), F.countDistinct("session_id").cast("int").alias("session_count")).select(F.col("event_date").alias("activity_date"), "from_page", "to_page", "country_code", "city", "traffic_source", "device_type", "transition_count", "session_count")

    confirmed_pairs = items.filter("confirmed_purchase = 1").select("user_id", "product_id").distinct()
    cancelled_pairs = current_items(spark).join(orders.filter(F.col("order_status") == "cancelled").select("order_id", "user_id"), "order_id").select("user_id", "product_id").distinct()
    interest = events.filter(F.col("event_type").isin("product_view", "add_to_cart", "checkout_start")).filter(F.col("product_id").isNotNull()).groupBy("user_id", "product_id", "membership_type_at_event", "country_code", "city").agg(
        F.sum(F.when(F.col("event_type") == "product_view", 1).otherwise(0)).cast("int").alias("product_view_count"), F.sum(F.when(F.col("event_type") == "add_to_cart", 1).otherwise(0)).cast("int").alias("add_to_cart_count"), F.sum(F.when(F.col("event_type") == "checkout_start", 1).otherwise(0)).cast("int").alias("checkout_start_count"), F.max("event_timestamp").alias("last_interest_at")
    )
    candidates = interest.join(confirmed_pairs, ["user_id", "product_id"], "left_anti").join(cancelled_pairs, ["user_id", "product_id"], "left_anti").join(current_profiles.filter("account_status = 'active' AND is_deleted = false").select("user_id"), "user_id", "inner").join(products, "product_id", "left").filter((F.col("product_view_count") >= 2) | (F.col("add_to_cart_count") >= 1) | (F.col("checkout_start_count") >= 1)).withColumn("candidate_reason", F.when(F.col("checkout_start_count") >= 1, F.lit("checkout_started_without_paid_purchase")).when(F.col("add_to_cart_count") >= 1, F.lit("cart_interest_without_paid_purchase")).otherwise(F.lit("repeat_product_interest"))).select("user_id", "product_id", "product_name", "category", F.col("membership_type_at_event").alias("membership_type"), "country_code", "city", "product_view_count", "add_to_cart_count", "checkout_start_count", "last_interest_at", "candidate_reason")

    order_daily = orders.filter("confirmed_purchase = 1").groupBy("order_date", "country_code", "city").agg(F.sum("confirmed_purchase").cast("int").alias("confirmed_purchase_count"), F.sum("recognized_revenue").cast(DecimalType(18,2)).alias("recognized_revenue"))

    # Context joins are used only by mart_context_impact_daily.
    # GeoIP fields stay outside fact_clickstream_event.

    weather = (
        spark.table(f"{CATALOG}.processed.weather_clean")
        .filter("coverage_status = 'complete'")
        .select(
            F.col("latitude").alias("weather_latitude"),
            F.col("longitude").alias("weather_longitude"),
            F.col("weather_hour").alias("weather_utc_hour"),
            "temperature_c",
            "precipitation_mm",
        )
    )

    holiday_days = (
        spark.table(f"{CATALOG}.processed.holidays_clean")
        .filter("coverage_status = 'complete'")
        .select(
            F.col("country_code").alias("holiday_country_code"),
            F.col("holiday_date").alias("holiday_local_date"),
        )
        .groupBy(
            "holiday_country_code",
            "holiday_local_date",
        )
        .agg(
            F.lit(1).cast("int").alias("is_holiday")
        )
    )

    event_context = (
        event_enriched
        .withColumn(
            "event_weather_hour",
            F.date_trunc("hour", "event_timestamp"),
        )
        .withColumn(
            "event_local_date",
            F.expr(
                "to_date(from_utc_timestamp(event_timestamp, context_geo_timezone))"
            ),
        )
    )

    event_context = (
        event_context
        .join(
            weather,
            (
                F.round(
                    event_context["context_geo_latitude"],
                    3,
                )
                == weather["weather_latitude"]
            )
            & (
                F.round(
                    event_context["context_geo_longitude"],
                    3,
                )
                == weather["weather_longitude"]
            )
            & (
                event_context["event_weather_hour"]
                == weather["weather_utc_hour"]
            ),
            "left",
        )
        .drop(
            "weather_latitude",
            "weather_longitude",
            "weather_utc_hour",
        )
    )

    event_context = (
        event_context
        .join(
            holiday_days,
            (
                event_context["country_code"]
                == holiday_days["holiday_country_code"]
            )
            & (
                event_context["event_local_date"]
                == holiday_days["holiday_local_date"]
            ),
            "left",
        )
        .drop(
            "holiday_country_code",
            "holiday_local_date",
        )
    )

    context_base = (
        event_context
        .groupBy(
            "event_date",
            "country_code",
            "city",
        )
        .agg(
            F.countDistinct("session_id")
            .cast("int")
            .alias("session_count"),
            F.count("event_id")
            .cast("int")
            .alias("event_count"),
            F.sum(
                F.when(
                    F.col("event_type") == "product_view",
                    1,
                ).otherwise(0)
            )
            .cast("int")
            .alias("product_view_count"),
            F.sum(
                F.when(
                    F.col("event_type") == "add_to_cart",
                    1,
                ).otherwise(0)
            )
            .cast("int")
            .alias("add_to_cart_count"),
            F.avg("temperature_c").alias("avg_temperature_c"),
            F.avg("precipitation_mm").alias("precipitation_mm"),
            F.max(
                F.coalesce(
                    F.col("is_holiday"),
                    F.lit(0),
                )
            )
            .cast("int")
            .alias("is_holiday"),
        )
    )

    context = (
        context_base.alias("ctx")
        .join(
            order_daily.alias("ord"),
            (
                F.col("ctx.event_date")
                == F.col("ord.order_date")
            )
            & (
                F.col("ctx.country_code")
                == F.col("ord.country_code")
            )
            & (
                F.col("ctx.city")
                == F.col("ord.city")
            ),
            "left",
        )
        .select(
            F.col("ctx.event_date").alias("activity_date"),
            F.col("ctx.country_code").alias("country_code"),
            F.col("ctx.city").alias("city"),
            F.col("ctx.session_count").alias("session_count"),
            F.col("ctx.event_count").alias("event_count"),
            F.col("ctx.product_view_count").alias("product_view_count"),
            F.col("ctx.add_to_cart_count").alias("add_to_cart_count"),
            F.coalesce(
                F.col("ord.confirmed_purchase_count"),
                F.lit(0),
            )
            .cast("int")
            .alias("confirmed_purchase_count"),
            F.coalesce(
                F.col("ord.recognized_revenue"),
                F.lit(0).cast(DecimalType(18, 2)),
            )
            .alias("recognized_revenue"),
            F.col("ctx.avg_temperature_c").alias("avg_temperature_c"),
            F.col("ctx.precipitation_mm").alias("precipitation_mm"),
            F.col("ctx.is_holiday").alias("is_holiday"),
        )
    )

    return {"dim_date": dates, "dim_product": products, "dim_user_current": current_profiles, "fact_clickstream_event": events, "fact_order": orders, "fact_order_item": items, "mart_journey_session": session, "mart_product_performance_daily": product_mart, "mart_web_experience_daily": experience, "mart_navigation_paths": navigation, "mart_personalization_candidates": candidates, "mart_context_impact_daily": context}


def main() -> int:
    args = parse_args()
    spark: SparkSession | None = None
    build = build_id(args.run_id)
    client = None
    try:
        spark = make_spark("publish-clickhouse")
        validation_id = latest_validation_id(spark)
        frames = build_frames(spark)
        client = clickhouse_client()
        ensure_schema(client)
        counts: dict[str, int] = {}
        for table in TABLES:
            counts[table] = write_dataframe(client, table, add_build(frames[table], build), list(frames[table].columns) + ["serving_build_id"])
        required = ("fact_clickstream_event", "fact_order", "mart_journey_session", "mart_web_experience_daily")
        if any(counts.get(name, 0) == 0 for name in required):
            raise RuntimeError(f"Serving build has an empty required table: {counts}")
        client.insert(f"{DATABASE}.serving_control", [[build, datetime.now(UTC), "ACTIVE"]], column_names=["active_build_id", "activated_at", "status"])
        spark.createDataFrame([(build, validation_id, "ACTIVE", json.dumps(counts, sort_keys=True), None, datetime.now(UTC), datetime.now(UTC))], "serving_build_id string, validation_id string, status string, row_count_summary string, error_message string, activated_at timestamp, created_at timestamp").writeTo(f"{CATALOG}.audit.serving_builds").append()
        payload = {"status": "PASSED", "serving_build_id": build, "validation_id": validation_id, "counts": counts, "activated_at_utc": datetime.now(UTC).isoformat()}
        REPORTS.mkdir(parents=True, exist_ok=True)
        (REPORTS / "serving_latest.json").write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
        print(json.dumps(payload, default=str))
        return 0
    except Exception as error:
        if spark is not None:
            try:
                spark.createDataFrame([(build, None, "FAILED", "{}", f"{type(error).__name__}: {error}", None, datetime.now(UTC))], "serving_build_id string, validation_id string, status string, row_count_summary string, error_message string, activated_at timestamp, created_at timestamp").writeTo(f"{CATALOG}.audit.serving_builds").append()
            except Exception:
                pass
        failure = {"status": "FAILED", "error": f"{type(error).__name__}: {error}"}
        REPORTS.mkdir(parents=True, exist_ok=True)
        (REPORTS / "serving_latest.json").write_text(json.dumps(failure, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(failure))
        return 2
    finally:
        if spark is not None:
            spark.stop()


if __name__ == "__main__":
    raise SystemExit(main())
