#!/usr/bin/env python3
"""One Spark Structured Streaming application for all Kafka business topics.

The primary path always lands the original Kafka message in Raw Iceberg first.
Then it validates, deduplicates, enriches, and writes either Clean Iceberg or
Iceberg Quarantine. Watermarking is enabled for event-time state management,
but valid late events remain part of the primary data path and are flagged.
"""

from __future__ import annotations


import argparse
import json
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import maxminddb
from pyspark import StorageLevel
from pyspark.sql import DataFrame, SparkSession, Window, functions as F
from pyspark.sql.types import BooleanType, DoubleType, IntegerType, LongType, StringType, StructField, StructType

CATALOG = "ecommerce"
RUNTIME = Path("/opt/project/runtime")
PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", "/opt/project"))

_geoip_value = os.environ.get("GEOIP_DATABASE_PATH")
GEOIP_PATH = Path(_geoip_value) if _geoip_value else PROJECT_ROOT / "data/reference/GeoLite2-City.mmdb"

if not GEOIP_PATH.is_absolute():
    GEOIP_PATH = PROJECT_ROOT / GEOIP_PATH
TOPIC_TO_SOURCE = {
    "clickstream-events": "clickstream",
    "webserver-logs": "web_logs",
    "users-cdc": "users_cdc",
    "orders-cdc": "orders_cdc",
    "order-items-cdc": "order_items_cdc",
}
VALID_EVENT_TYPES = {"page_view", "product_view", "search", "scroll", "add_to_cart", "remove_from_cart", "checkout_start", "checkout_complete", "login", "logout"}
PRODUCT_EVENTS = {"product_view", "add_to_cart", "remove_from_cart", "checkout_start", "checkout_complete"}
CHECKOUT_EVENTS = {"checkout_start", "checkout_complete"}
GEO_SCHEMA = StructType([
    StructField("country_code", StringType()), StructField("country_name", StringType()), StructField("city", StringType()),
    StructField("latitude", DoubleType()), StructField("longitude", DoubleType()), StructField("timezone", StringType()),
])

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the all-source Spark Structured Streaming application")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--allowed-lateness-minutes", type=int, default=30)
    return parser.parse_args()


def utc_now() -> datetime:
    return datetime.now(UTC)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    temporary.replace(path)

def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def make_spark() -> SparkSession:
    return (
        SparkSession.builder.appName("streaming-ingestion")
        .config("spark.sql.catalog.ecommerce.jdbc.user", os.environ.get("POSTGRES_USER", "ecommerce_user"))
        .config("spark.sql.catalog.ecommerce.jdbc.password", os.environ.get("POSTGRES_PASSWORD", ""))
        .config("spark.sql.catalog.ecommerce.type", "jdbc")
        .config("spark.sql.catalog.ecommerce.cache-enabled", "false")
        .getOrCreate()
    )


def geo_lookup(
    ip_address: str | None,
) -> tuple[str | None, str | None, str | None, float | None, float | None, str | None]:
    """Enrich one IP address using the local MaxMind GeoLite2 City database."""
    if not ip_address or not GEOIP_PATH.is_file():
        return (None, None, None, None, None, None)

    try:
        with maxminddb.open_database(str(GEOIP_PATH)) as reader:
            record = reader.get(ip_address) or {}

        country = record.get("country") or {}
        city = record.get("city") or {}
        location = record.get("location") or {}

        names = country.get("names") or {}
        city_names = city.get("names") or {}

        return (
            country.get("iso_code"),
            names.get("en"),
            city_names.get("en"),
            location.get("latitude"),
            location.get("longitude"),
            location.get("time_zone"),
        )

    except Exception:
        return (None, None, None, None, None, None)

geo_udf = F.udf(geo_lookup, GEO_SCHEMA)

def append(df: DataFrame, table: str) -> None:
    if df.limit(1).count() > 0:
        df.writeTo(table).append()


def raw_new_records(spark: SparkSession, batch: DataFrame, batch_id: int) -> DataFrame:
    """Write each Kafka physical record once to immutable Raw Iceberg."""
    raw = batch.select(
        F.element_at(F.create_map(*sum(([F.lit(topic), F.lit(source)] for topic, source in TOPIC_TO_SOURCE.items()), [])), F.col("kafka_topic")).alias("source_name"),
        "kafka_topic", "kafka_partition", "kafka_offset", "kafka_timestamp",
        F.concat_ws("|", "kafka_topic", "kafka_partition", "kafka_offset").alias("source_record_id"),
        "raw_payload", F.lit(None).cast("string").alias("source_file"), F.current_timestamp().alias("ingested_at"), F.lit(batch_id).cast("long").alias("stream_batch_id"),
    )
    existing = spark.table(f"{CATALOG}.raw.kafka_messages").select("source_record_id").distinct()
    new = raw.join(existing, "source_record_id", "left_anti")
    append(new, f"{CATALOG}.raw.kafka_messages")
    # Return the full micro-batch. A replay may have landed Raw before a failure;
    # downstream functions skip physical records already present in Clean or Quarantine.
    return raw


def unprocessed_records(spark: SparkSession, records: DataFrame, clean_table: str, source_name: str) -> DataFrame:
    """Skip a Kafka physical record only after it reached Clean or Quarantine evidence."""
    clean_ids = spark.table(clean_table).select("source_record_id").where(F.col("source_record_id").isNotNull())
    quarantine_ids = spark.table(f"{CATALOG}.audit.quarantine_records").filter(F.col("source_name") == source_name).select("source_record_id").where(F.col("source_record_id").isNotNull())
    handled = clean_ids.unionByName(quarantine_ids).distinct()
    return records.join(handled, "source_record_id", "left_anti")


def quarantine(df: DataFrame, source_name: str, batch_id: int) -> int:
    rows = df.select(
        F.sha2(F.concat_ws("|", "source_record_id", "reason_code"), 256).alias("quarantine_id"), F.lit(source_name).alias("source_name"),
        "reason_code", "reason_description", "raw_payload", "kafka_topic", "kafka_partition", "kafka_offset", "source_record_id",
        F.lit(batch_id).cast("long").alias("stream_batch_id"), F.current_timestamp().alias("quarantined_at"),
    )
    count = rows.count()
    append(rows, f"{CATALOG}.audit.quarantine_records")
    return count


def deduplicate(spark: SparkSession, candidates: DataFrame, key: str, table: str) -> tuple[DataFrame, DataFrame]:
    """Keep the first valid business record and quarantine semantic duplicates."""
    order = Window.partitionBy(key).orderBy("kafka_partition", "kafka_offset")
    ranked = candidates.withColumn("_rn", F.row_number().over(order))
    first = ranked.filter("_rn = 1").drop("_rn")
    duplicate_in_batch = ranked.filter("_rn > 1").drop("_rn")
    existing = spark.table(table).select(key).where(F.col(key).isNotNull()).distinct()
    accepted = first.join(existing, key, "left_anti")
    duplicate_existing = first.join(existing, key, "left_semi")
    duplicates = duplicate_in_batch.unionByName(duplicate_existing, allowMissingColumns=True)
    return accepted, duplicates


def audit_run(spark: SparkSession, run_id: str, source: str, batch_id: int, input_count: int, accepted: int, invalid: int, duplicate: int) -> None:
    row = [(f"{run_id}_{source}_{batch_id}", "streaming_ingestion", source, "PASSED", utc_now(), utc_now(), input_count, accepted, invalid, duplicate, accepted, None, utc_now())]
    schema = "run_id string, job_name string, source_name string, status string, started_at timestamp, finished_at timestamp, input_count long, accepted_count long, invalid_count long, duplicate_count long, output_count long, error_message string, recorded_at timestamp"
    spark.createDataFrame(row, schema).writeTo(f"{CATALOG}.audit.pipeline_runs").append()
    metrics = [
        (f"{run_id}_{source}_{batch_id}", source, "input_records", str(input_count), "PASSED", utc_now()),
        (f"{run_id}_{source}_{batch_id}", source, "accepted_records", str(accepted), "PASSED", utc_now()),
        (f"{run_id}_{source}_{batch_id}", source, "invalid_records", str(invalid), "PASSED", utc_now()),
        (f"{run_id}_{source}_{batch_id}", source, "duplicate_records", str(duplicate), "PASSED", utc_now()),
    ]
    spark.createDataFrame(metrics, "run_id string, source_name string, metric_name string, metric_value string, status string, recorded_at timestamp").writeTo(f"{CATALOG}.audit.quality_metrics").append()


def payload_for_web_log(raw_payload: F.Column) -> F.Column:
    """Use Filebeat's top-level NDJSON payload or its original message fallback."""
    return F.when(F.get_json_object(raw_payload, "$.log_id").isNotNull(), raw_payload).otherwise(F.coalesce(F.get_json_object(raw_payload, "$.message"), F.get_json_object(raw_payload, "$.event.original"), raw_payload))


def process_clickstream(spark: SparkSession, records: DataFrame, batch_id: int, run_id: str, allowed_lateness: int) -> None:
    records = unprocessed_records(spark, records, f"{CATALOG}.processed.clickstream_clean", "clickstream")
    if records.limit(1).count() == 0:
        return
    parsed = records.select(
        "raw_payload", "kafka_topic", "kafka_partition", "kafka_offset", "source_record_id",
        F.get_json_object("raw_payload", "$.contract_version").alias("contract_version"), F.get_json_object("raw_payload", "$.event_id").alias("event_id"),
        F.to_timestamp(F.get_json_object("raw_payload", "$.event_timestamp"), "yyyy-MM-dd'T'HH:mm:ssX").alias("event_timestamp"), F.get_json_object("raw_payload", "$.session_id").alias("session_id"),
        F.get_json_object("raw_payload", "$.visitor_id").alias("visitor_id"), F.get_json_object("raw_payload", "$.request_id").alias("request_id"), F.get_json_object("raw_payload", "$.user_id").alias("user_id"),
        F.get_json_object("raw_payload", "$.event_type").alias("event_type"), F.get_json_object("raw_payload", "$.page_url").alias("page_url"), F.get_json_object("raw_payload", "$.search_query").alias("search_query"),
        F.get_json_object("raw_payload", "$.product_id").alias("product_id"), F.get_json_object("raw_payload", "$.checkout_id").alias("checkout_id"), F.get_json_object("raw_payload", "$.order_id").alias("order_id"),
        F.get_json_object("raw_payload", "$.ip_address").alias("ip_address"), F.get_json_object("raw_payload", "$.device_type").alias("device_type"), F.get_json_object("raw_payload", "$.browser").alias("browser"),
        F.get_json_object("raw_payload", "$.operating_system").alias("operating_system"), F.get_json_object("raw_payload", "$.traffic_source").alias("traffic_source"),
        F.get_json_object("raw_payload", "$.scroll_depth_pct").cast("int").alias("scroll_depth_pct"), F.get_json_object("raw_payload", "$.time_on_page_seconds").cast("int").alias("time_on_page_seconds"),
    )
    invalid_reason = F.when(F.get_json_object("raw_payload", "$").isNull(), F.lit("MALFORMED_JSON")).when(F.col("contract_version") != "1.0", F.lit("UNSUPPORTED_CONTRACT_VERSION")).when(F.col("event_id").isNull() | (F.length("event_id") == 0), F.lit("MISSING_EVENT_ID")).when(F.col("event_timestamp").isNull(), F.lit("INVALID_EVENT_TIMESTAMP")).when(F.col("session_id").isNull() | (F.length("session_id") == 0), F.lit("MISSING_SESSION_ID")).when(F.col("visitor_id").isNull() | (F.length("visitor_id") == 0), F.lit("MISSING_VISITOR_ID")).when(~F.col("event_type").isin(*VALID_EVENT_TYPES), F.lit("UNSUPPORTED_EVENT_TYPE")).when(F.col("event_type").isin(*PRODUCT_EVENTS) & (F.col("product_id").isNull() | (F.length("product_id") == 0)), F.lit("MISSING_PRODUCT_ID")).when(F.col("event_type").isin(*CHECKOUT_EVENTS) & (F.col("checkout_id").isNull() | (F.length("checkout_id") == 0)), F.lit("MISSING_CHECKOUT_ID"))
    invalid = parsed.withColumn("reason_code", invalid_reason).filter(F.col("reason_code").isNotNull()).withColumn("reason_description", F.col("reason_code"))
    valid = parsed.withColumn("reason_code", invalid_reason).filter(F.col("reason_code").isNull()).drop("reason_code")
    accepted, duplicates = deduplicate(spark, valid, "event_id", f"{CATALOG}.processed.clickstream_clean")
    invalid_count = quarantine(invalid, "clickstream", batch_id)
    duplicates = duplicates.withColumn("reason_code", F.lit("DUPLICATE_EVENT_ID")).withColumn("reason_description", F.lit("event_id already exists in Clean data or this micro-batch"))
    duplicate_count = quarantine(duplicates, "clickstream", batch_id)
    max_time = accepted.agg(F.max("event_timestamp").alias("max_time")).collect()[0]["max_time"] if accepted.limit(1).count() else None
    ready = accepted.withColumn("late_arrival", F.lit(False) if max_time is None else (F.col("event_timestamp") < F.lit(max_time) - F.expr(f"INTERVAL {allowed_lateness} MINUTES"))).withColumn("geo", geo_udf("ip_address")).select(
        "event_id", "contract_version", "event_timestamp", "session_id", "visitor_id", "request_id", "user_id", "event_type", "page_url", "search_query", "product_id", "checkout_id", "order_id", "ip_address", "device_type", "browser", "operating_system", "traffic_source", "scroll_depth_pct", "time_on_page_seconds", "late_arrival",
        F.col("geo.country_code").alias("geo_country_code"), F.col("geo.country_name").alias("geo_country_name"), F.col("geo.city").alias("geo_city"), F.col("geo.latitude").alias("geo_latitude"), F.col("geo.longitude").alias("geo_longitude"), F.col("geo.timezone").alias("geo_timezone"),
        F.lit("clickstream_events.jsonl").alias("source_file"), "kafka_topic", "kafka_partition", "kafka_offset", "source_record_id", F.current_timestamp().alias("processed_at"),
    )
    accepted_count = ready.count()
    append(ready, f"{CATALOG}.processed.clickstream_clean")
    audit_run(spark, run_id, "clickstream", batch_id, records.count(), accepted_count, invalid_count, duplicate_count)


def process_web_logs(spark: SparkSession, records: DataFrame, batch_id: int, run_id: str, allowed_lateness: int) -> None:
    records = unprocessed_records(spark, records, f"{CATALOG}.processed.webserver_logs_clean", "web_logs")
    if records.limit(1).count() == 0:
        return
    payload = payload_for_web_log(F.col("raw_payload"))
    parsed = records.select("raw_payload", "kafka_topic", "kafka_partition", "kafka_offset", "source_record_id", payload.alias("payload")).select(
        "raw_payload", "kafka_topic", "kafka_partition", "kafka_offset", "source_record_id", F.get_json_object("payload", "$.contract_version").alias("contract_version"), F.get_json_object("payload", "$.log_id").alias("log_id"), F.get_json_object("payload", "$.request_id").alias("request_id"),
        F.to_timestamp(F.get_json_object("payload", "$.timestamp"), "yyyy-MM-dd'T'HH:mm:ssX").alias("log_timestamp"), F.get_json_object("payload", "$.ip_address").alias("ip_address"), F.get_json_object("payload", "$.http_method").alias("http_method"), F.get_json_object("payload", "$.endpoint").alias("endpoint"), F.get_json_object("payload", "$.status_code").cast("int").alias("status_code"), F.get_json_object("payload", "$.response_time_ms").cast("int").alias("response_time_ms"), F.get_json_object("payload", "$.user_agent").alias("user_agent"), F.get_json_object("payload", "$.bytes_sent").cast("long").alias("bytes_sent"),
    )
    invalid_reason = F.when(F.get_json_object("raw_payload", "$").isNull(), F.lit("MALFORMED_JSON")).when(F.col("contract_version") != "1.0", F.lit("UNSUPPORTED_CONTRACT_VERSION")).when(F.col("log_id").isNull() | (F.length("log_id") == 0), F.lit("MISSING_LOG_ID")).when(F.col("request_id").isNull() | (F.length("request_id") == 0), F.lit("MISSING_REQUEST_ID")).when(F.col("log_timestamp").isNull(), F.lit("INVALID_LOG_TIMESTAMP")).when(F.col("endpoint").isNull() | (F.length("endpoint") == 0), F.lit("MISSING_ENDPOINT")).when(F.col("status_code").isNull() | (F.col("status_code") < 100) | (F.col("status_code") > 599), F.lit("INVALID_STATUS_CODE")).when(F.col("response_time_ms").isNull() | (F.col("response_time_ms") < 0), F.lit("INVALID_RESPONSE_TIME"))
    invalid = parsed.withColumn("reason_code", invalid_reason).filter(F.col("reason_code").isNotNull()).withColumn("reason_description", F.col("reason_code"))
    valid = parsed.withColumn("reason_code", invalid_reason).filter(F.col("reason_code").isNull()).drop("reason_code")
    accepted, duplicates = deduplicate(spark, valid, "log_id", f"{CATALOG}.processed.webserver_logs_clean")
    invalid_count = quarantine(invalid, "web_logs", batch_id)
    duplicates = duplicates.withColumn("reason_code", F.lit("DUPLICATE_LOG_ID")).withColumn("reason_description", F.lit("log_id already exists in Clean data or this micro-batch"))
    duplicate_count = quarantine(duplicates, "web_logs", batch_id)
    max_time = accepted.agg(F.max("log_timestamp").alias("max_time")).collect()[0]["max_time"] if accepted.limit(1).count() else None
    ready = accepted.withColumn("late_arrival", F.lit(False) if max_time is None else (F.col("log_timestamp") < F.lit(max_time) - F.expr(f"INTERVAL {allowed_lateness} MINUTES"))).withColumn("geo", geo_udf("ip_address")).select(
        "log_id", "contract_version", "request_id", "log_timestamp", "ip_address", "http_method", "endpoint", "status_code", "response_time_ms", "user_agent", "bytes_sent", "late_arrival", F.col("geo.country_code").alias("geo_country_code"), F.col("geo.country_name").alias("geo_country_name"), F.col("geo.city").alias("geo_city"), F.col("geo.latitude").alias("geo_latitude"), F.col("geo.longitude").alias("geo_longitude"), F.col("geo.timezone").alias("geo_timezone"), F.lit("webserver_access.log").alias("source_file"), "kafka_topic", "kafka_partition", "kafka_offset", "source_record_id", F.current_timestamp().alias("processed_at"),
    )
    accepted_count = ready.count()
    append(ready, f"{CATALOG}.processed.webserver_logs_clean")
    audit_run(spark, run_id, "web_logs", batch_id, records.count(), accepted_count, invalid_count, duplicate_count)


def process_cdc(spark: SparkSession, records: DataFrame, batch_id: int, run_id: str, source: str, table: str, key: str) -> None:
    records = unprocessed_records(spark, records, f"{CATALOG}.processed.{table}", source)
    if records.limit(1).count() == 0:
        return
    payload = F.coalesce(F.get_json_object("raw_payload", "$.payload"), F.col("raw_payload"))
    parsed = records.select("raw_payload", "kafka_topic", "kafka_partition", "kafka_offset", "source_record_id", payload.alias("payload")).select(
        "raw_payload", "kafka_topic", "kafka_partition", "kafka_offset", "source_record_id", F.get_json_object("payload", "$.op").alias("operation"), F.get_json_object("payload", "$.before").alias("before_json"), F.get_json_object("payload", "$.after").alias("after_json"), F.coalesce(F.get_json_object("payload", "$.source.lsn").cast("long"), F.col("kafka_offset")).alias("source_lsn"), F.get_json_object("payload", "$.ts_ms").cast("long").alias("source_ts_ms"), F.get_json_object("payload", f"$.after.{key}").alias("after_key"), F.get_json_object("payload", f"$.before.{key}").alias("before_key"), F.get_json_object("payload", "$.after.user_id").alias("user_id_after"), F.get_json_object("payload", "$.before.user_id").alias("user_id_before"), F.get_json_object("payload", "$.after.checkout_id").alias("checkout_id_after"), F.get_json_object("payload", "$.before.checkout_id").alias("checkout_id_before"), F.get_json_object("payload", "$.source.table").alias("source_table"),
    ).withColumn(key, F.coalesce("after_key", "before_key")).withColumn("user_id", F.coalesce("user_id_after", "user_id_before")).withColumn("checkout_id", F.coalesce("checkout_id_after", "checkout_id_before"))
    invalid_reason = F.when(F.get_json_object("raw_payload", "$").isNull(), F.lit("MALFORMED_JSON")).when(~F.col("operation").isin("r", "c", "u", "d"), F.lit("INVALID_CDC_OPERATION")).when(F.col(key).isNull() | (F.length(F.col(key)) == 0), F.lit("MISSING_CDC_PRIMARY_KEY")).when(F.col("source_lsn").isNull(), F.lit("MISSING_SOURCE_LSN"))
    invalid = parsed.withColumn("reason_code", invalid_reason).filter(F.col("reason_code").isNotNull()).withColumn("reason_description", F.col("reason_code"))
    valid = parsed.withColumn("reason_code", invalid_reason).filter(F.col("reason_code").isNull()).drop("reason_code").withColumn("cdc_event_id", F.sha2(F.concat_ws("|", "source_table", "source_lsn", F.col(key), "operation", "kafka_partition", "kafka_offset"), 256))
    accepted, duplicates = deduplicate(spark, valid, "cdc_event_id", f"{CATALOG}.processed.{table}")
    invalid_count = quarantine(invalid, source, batch_id)
    duplicates = duplicates.withColumn("reason_code", F.lit("DUPLICATE_CDC_EVENT")).withColumn("reason_description", F.lit("CDC event already exists"))
    duplicate_count = quarantine(duplicates, source, batch_id)
    extra = []
    if table == "users_cdc_clean":
        columns = ["cdc_event_id", "user_id", "operation", "before_json", "after_json", "source_lsn", "source_ts_ms", "kafka_topic", "kafka_partition", "kafka_offset", "source_record_id"]
    elif table == "orders_cdc_clean":
        columns = ["cdc_event_id", "order_id", "user_id", "checkout_id", "operation", "before_json", "after_json", "source_lsn", "source_ts_ms", "kafka_topic", "kafka_partition", "kafka_offset", "source_record_id"]
    else:
        columns = ["cdc_event_id", "order_item_id", "order_id", "product_id", "operation", "before_json", "after_json", "source_lsn", "source_ts_ms", "kafka_topic", "kafka_partition", "kafka_offset", "source_record_id"]
        # Parse order-item relationships from both images.
        accepted = accepted.withColumn("order_id", F.coalesce(F.get_json_object("after_json", "$.order_id"), F.get_json_object("before_json", "$.order_id"))).withColumn("product_id", F.coalesce(F.get_json_object("after_json", "$.product_id"), F.get_json_object("before_json", "$.product_id")))
    ready = accepted.select(*columns, F.current_timestamp().alias("processed_at"))
    accepted_count = ready.count()
    append(ready, f"{CATALOG}.processed.{table}")
    audit_run(spark, run_id, source, batch_id, records.count(), accepted_count, invalid_count, duplicate_count)


def process_batch(
    spark: SparkSession,
    run_id: str,
    dataframe: DataFrame,
    batch_id: int,
    allowed_lateness: int,
) -> None:
    """Process one Kafka micro-batch with small local caches.

    The initial project data is small. Caching prevents Spark from repeatedly
    rebuilding the same Kafka micro-batch for every validation and write step.
    """
    batch = dataframe.persist(StorageLevel.MEMORY_ONLY)

    try:
        topic_counts = {
            row["kafka_topic"]: int(row["count"])
            for row in batch.groupBy("kafka_topic").count().collect()
        }

        raw = raw_new_records(spark, batch, batch_id)

        for topic, source in TOPIC_TO_SOURCE.items():
            subset = ( raw.filter(F.col("kafka_topic") == topic) .persist(StorageLevel.MEMORY_ONLY) )

            try:
                if source == "clickstream":
                    process_clickstream( spark, subset, batch_id, run_id, allowed_lateness, )

                elif source == "web_logs":
                    process_web_logs( spark, subset, batch_id, run_id, allowed_lateness, )

                elif source == "users_cdc":
                    process_cdc( spark, subset, batch_id, run_id, source, "users_cdc_clean", "user_id", )

                elif source == "orders_cdc":
                    process_cdc( spark, subset, batch_id, run_id, source, "orders_cdc_clean", "order_id", )

                elif source == "order_items_cdc":
                    process_cdc( spark, subset, batch_id, run_id, source, "order_items_cdc_clean", "order_item_id", )

            finally:
                subset.unpersist()

        previous = read_json(RUNTIME / "streaming_status.json")

        processed = {
            name: int(value)
            for name, value in ( previous.get("processed_source_records") or {} ).items()
        }

        for topic, count in topic_counts.items():
            source = TOPIC_TO_SOURCE.get(topic)

            if source:
                processed[source] = processed.get(source, 0) + count

        write_json(
            RUNTIME / "streaming_status.json",
            {
                "status": "RUNNING",
                "run_id": run_id,
                "last_successful_batch_id": int(batch_id),
                "last_micro_batch_id": int(batch_id),
                "last_successful_batch_input_count": sum(topic_counts.values()),
                "last_successful_batch_at_utc": utc_now().isoformat(),
                "processed_source_records": processed,
                "allowed_lateness_minutes": allowed_lateness,
            },
        )

    finally:
        batch.unpersist()

def main() -> int:
    args = parse_args()
    spark = make_spark()
    topics = ",".join(TOPIC_TO_SOURCE)
    try:
        kafka = (
            spark.readStream.format("kafka").option("kafka.bootstrap.servers", "kafka1:19092,kafka2:19092,kafka3:19092")
            .option("subscribe", topics).option("startingOffsets", "earliest").option("failOnDataLoss", "true")
            .load().select(F.col("topic").alias("kafka_topic"), F.col("partition").cast("int").alias("kafka_partition"), F.col("offset").cast("long").alias("kafka_offset"), F.col("timestamp").alias("kafka_timestamp"), F.col("value").cast("string").alias("raw_payload"))
        )
        # Watermark bounds event-time state. It is never used to discard the Raw/Clean primary path.
        event_time = F.coalesce(F.to_timestamp(F.get_json_object("raw_payload", "$.event_timestamp"), "yyyy-MM-dd'T'HH:mm:ssX"), F.to_timestamp(F.get_json_object("raw_payload", "$.timestamp"), "yyyy-MM-dd'T'HH:mm:ssX"), F.col("kafka_timestamp"))
        stream = kafka.withColumn("event_time", event_time).withWatermark("event_time", f"{args.allowed_lateness_minutes} minutes")
        checkpoint = "/opt/project/runtime/checkpoints/streaming_ingestion"
        write_json(
        RUNTIME / "streaming_status.json",
        {
            "status": "STARTING",
            "run_id": args.run_id,
            "started_at_utc": utc_now().isoformat(),
            "processed_source_records": {},
            "allowed_lateness_minutes": args.allowed_lateness_minutes,
        },
        )

        query = (
            stream.writeStream
            .queryName("streaming-ingestion")
            .option("checkpointLocation", checkpoint)
            .trigger(processingTime="5 seconds")
            .foreachBatch(
                lambda df, batch_id: process_batch(
                    spark,
                    args.run_id,
                    df.drop("event_time"),
                    batch_id,
                    args.allowed_lateness_minutes,
                )
            )
            .start()
        )

        query.awaitTermination()
        return 0
    except KeyboardInterrupt:
        return 0
    except Exception as error:
        write_json(RUNTIME / "streaming_status.json", {"status": "FAILED", "run_id": args.run_id, "error": f"{type(error).__name__}: {error}", "updated_at_utc": utc_now().isoformat()})
        raise
    finally:
        spark.stop()


if __name__ == "__main__":
    raise SystemExit(main())
