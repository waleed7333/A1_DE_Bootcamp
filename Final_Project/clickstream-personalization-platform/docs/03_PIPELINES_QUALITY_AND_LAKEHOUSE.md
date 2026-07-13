# Pipelines, Data Quality, and Lakehouse Design

## 1. Purpose

This document explains the processing pipelines, lakehouse zones, Iceberg table layout, quality controls, quarantine handling, validation logic, watermarks, and reconciliation strategy used by the Clickstream Personalization Platform.

The project uses one Spark engine for both continuous Structured Streaming and scheduled batch jobs. The pipelines are intentionally separated by operational purpose: streaming handles continuous ingestion and cleaning, while batch handles SCD2, external enrichment, validation, and serving publication.

---

## 2. Processing Path Summary

| Path | Inputs | Engine | Outputs |
|---|---|---|---|
| Streaming clickstream | Kafka `clickstream-events` | Spark Structured Streaming | Raw Kafka messages, `clickstream_clean`, quarantine, quality metrics. |
| Streaming web logs | Kafka `webserver-logs` | Spark Structured Streaming | Raw Kafka messages, `webserver_logs_clean`, quarantine, quality metrics. |
| Streaming CDC | Kafka `users-cdc`, `orders-cdc`, `order-items-cdc` | Spark Structured Streaming | CDC clean Iceberg tables. |
| Product catalog bootstrap | Static CSV | Spark batch | `product_catalog_clean`. |
| User SCD2 | `users_cdc_clean` | Spark batch | `user_profile_scd2`, `audit.watermarks`. |
| Weather enrichment | `clickstream_clean` GeoIP coordinates | Spark batch + Open-Meteo | `weather_clean`, `external_api_failures`. |
| Holiday enrichment | `clickstream_clean` country/year | Spark batch + Calendarific | `holidays_clean`, `external_api_failures`. |
| Validation | Iceberg raw, processed, and audit tables | Spark batch | `validation_runs`, `reports/validation_latest.json`. |
| Serving publish | Validated Iceberg tables | Spark batch + ClickHouse | ClickHouse dims/facts/marts/views, `serving_builds`, `reports/serving_latest.json`. |

---

## 3. Lakehouse Storage Design

The lakehouse is implemented using Apache Iceberg tables stored on MinIO object storage. Spark accesses the lakehouse through the Iceberg catalog named `ecommerce`.

| Namespace | Purpose |
|---|---|
| `ecommerce.raw` | Raw payload preservation. |
| `ecommerce.processed` | Clean, structured, deduplicated, enriched tables. |
| `ecommerce.audit` | Quality, quarantine, validation, serving, API, and watermark evidence. |

Iceberg table properties use Parquet and zstd compression. Tables are partitioned by relevant fields such as ingestion date, event date, processed date, category, source name, or year depending on the table.

---

## 4. Raw Zone

### 4.1 `ecommerce.raw.kafka_messages`

The raw table stores original Kafka payloads from streaming sources. It preserves enough metadata to prove where each raw record came from.

Main fields:

| Field | Meaning |
|---|---|
| `source_name` | Logical source name such as `clickstream`, `web_logs`, or CDC source. |
| `kafka_topic` | Kafka topic name. |
| `kafka_partition` | Kafka partition. |
| `kafka_offset` | Kafka offset. |
| `kafka_timestamp` | Kafka timestamp. |
| `source_record_id` | Source record identifier created from topic/partition/offset or source key. |
| `raw_payload` | Original raw Kafka value. |
| `source_file` | Source file path when available. |
| `ingested_at` | Processing ingestion timestamp. |
| `stream_batch_id` | Spark micro-batch ID. |

The raw zone supports traceability, replay reasoning, validation evidence, and reconciliation.

---

## 5. Processed Zone

The processed zone contains clean tables that are suitable for analytical processing and serving publication.

| Table | Contents |
|---|---|
| `product_catalog_clean` | Valid static product reference data. |
| `clickstream_clean` | Valid clickstream events with GeoIP enrichment and Kafka metadata. |
| `webserver_logs_clean` | Valid web log records with GeoIP enrichment and Kafka metadata. |
| `users_cdc_clean` | Valid user CDC events with Debezium and Kafka metadata. |
| `orders_cdc_clean` | Valid order CDC events with Debezium and Kafka metadata. |
| `order_items_cdc_clean` | Valid order item CDC events with Debezium and Kafka metadata. |
| `user_profile_scd2` | Type 2 user profile history. |
| `weather_clean` | Historical weather enrichment by location and hour. |
| `holidays_clean` | Holiday enrichment by country and year/date. |

---

## 6. Audit Zone

The audit zone stores evidence rather than business facts.

| Table | Purpose |
|---|---|
| `pipeline_runs` | Run status and run-level counts. |
| `quality_metrics` | Quality metric counters by source and metric name. |
| `quarantine_records` | Invalid and duplicate records with reasons and raw payloads. |
| `external_api_failures` | API failures and expected skips. |
| `watermarks` | Incremental job progress. |
| `validation_runs` | Validation and reconciliation results. |
| `serving_builds` | ClickHouse serving build evidence. |

Audit does not store every valid record. Valid records are stored in `ecommerce.processed.*`. Audit records document what happened, what failed, what was skipped, what was rejected, and what was published.

---

## 7. Streaming Ingestion Pipeline

### 7.1 Streaming inputs

Spark Structured Streaming consumes:

```text
clickstream-events
webserver-logs
users-cdc
orders-cdc
order-items-cdc
```

### 7.2 Common streaming behavior

For each relevant topic, the pipeline handles:

- Kafka read.
- Raw payload preservation.
- Source-specific parsing.
- Validation.
- Deduplication where applicable.
- Clean table write.
- Quarantine write for invalid or duplicate records.
- Quality metric write.
- Pipeline run evidence write.

### 7.3 Clickstream processing

Clickstream processing validates required fields and source contract rules. Clean records are enriched with GeoLite2 fields using `ip_address` and written to `clickstream_clean`.

Rejected examples include:

- Missing event ID.
- Unsupported event type.
- Missing product ID for product-related events.
- Unsupported contract version.
- Malformed JSON.
- Duplicate event ID.

### 7.4 Web log processing

Web log processing validates log-specific requirements and enriches valid records with GeoIP fields. Clean records are written to `webserver_logs_clean`.

Rejected examples include:

- Missing log ID.
- Invalid status code.
- Unsupported contract version.
- Duplicate log ID.

### 7.5 CDC processing

CDC processing reads Debezium messages, extracts operation metadata, preserves before/after JSON, and writes clean CDC events for users, orders, and order items.

CDC clean tables are event tables. They preserve change history and source metadata; they are not directly equivalent to current-state dimensions.

---

## 8. Product Catalog Bootstrap

Product Catalog is loaded once during lakehouse bootstrap.

The job:

1. Reads `data/reference/product_catalog.csv`.
2. Verifies the file against the generation manifest checksum.
3. Validates product IDs, names, categories, prices, and inventory.
4. Rejects the load if invalid or duplicate product records exist.
5. Writes the clean product catalog into `product_catalog_clean` if the table is empty.

Product Catalog is intentionally static and clean. It is not a CDC source and does not have incremental product snapshots in this project.

---

## 9. User SCD Type 2 Pipeline

The User SCD2 job is a scheduled Spark batch job. It reads `users_cdc_clean` and writes `user_profile_scd2`.

The SCD2 output preserves:

- `effective_from`.
- `effective_to`.
- `is_current`.
- `version_sequence`.
- `is_deleted`.
- `source_lsn`.
- Profile attributes such as email, name, membership type, account status, country, and city.

The job uses CDC ordering information such as `source_lsn` and `source_ts_ms` to process user changes. It records incremental progress in `ecommerce.audit.watermarks`.

SCD2 is applied only to users. Orders and order items remain CDC-cleaned event sources and are later transformed into serving facts.

---

## 10. Weather Enrichment Pipeline

The weather job reads clean clickstream data after GeoIP enrichment. It derives distinct latitude, longitude, and hour combinations and requests historical weather data from Open-Meteo.

The job writes:

```text
ecommerce.processed.weather_clean
```

Important behavior:

- Weather requests are grouped to avoid one API call per event.
- Weather data is historical.
- Current or future UTC timestamps are skipped by design.
- Skipped or failed API requests are recorded in `ecommerce.audit.external_api_failures`.

This makes the job operationally explainable when current-day weather rows are unavailable.

---

## 11. Holiday Enrichment Pipeline

The holiday job reads distinct country/year combinations from clean clickstream GeoIP context and requests holiday data from Calendarific.

The job writes:

```text
ecommerce.processed.holidays_clean
```

The holiday data is used for context-aware analytics in ClickHouse marts.

---

## 12. Validation Pipeline

The validation job checks whether the lakehouse is internally consistent before serving publication.

Validation includes:

- Raw-to-clean-to-quarantine reconciliation.
- Quality status checks.
- Relationship checks.
- SCD2 checks.
- Context coverage checks.
- Orphan checks for product/order relationships.
- Request correlation coverage.

Validation writes evidence to:

```text
ecommerce.audit.validation_runs
reports/validation_latest.json
```

Serving publication should proceed only after validation passes.

---

## 13. Serving Publication Pipeline

The serving job reads validated Iceberg tables and writes ClickHouse physical tables. It then records the active serving build.

Serving outputs include:

- Dimensions.
- Facts.
- Marts.
- Regular `v_*` views exposing the latest active build.
- Serving build evidence.

Serving evidence is written to:

```text
ecommerce.audit.serving_builds
reports/serving_latest.json
```

---

## 14. Data Quality Routing

Quality routing is explicit:

```text
Valid records      → ecommerce.processed.*
Invalid records    → ecommerce.audit.quarantine_records
Duplicate records  → ecommerce.audit.quarantine_records
Metrics/status     → ecommerce.audit.quality_metrics and pipeline_runs
Validation proof   → ecommerce.audit.validation_runs
Serving proof      → ecommerce.audit.serving_builds
```

The quarantine table stores enough data to explain why a record was rejected and where it came from.

---

## 15. Quarantine Record Structure

`ecommerce.audit.quarantine_records` contains:

| Field | Meaning |
|---|---|
| `quarantine_id` | Unique quarantine record ID. |
| `source_name` | Source that produced the rejected record. |
| `reason_code` | Machine-readable reason. |
| `reason_description` | Human-readable explanation. |
| `raw_payload` | Original raw data. |
| `kafka_topic` | Kafka topic. |
| `kafka_partition` | Kafka partition. |
| `kafka_offset` | Kafka offset. |
| `source_record_id` | Source record reference. |
| `stream_batch_id` | Spark micro-batch ID. |
| `quarantined_at` | Timestamp when quarantine was written. |

This design supports evidence screenshots showing both aggregate counts and individual invalid/duplicate samples.

---

## 16. Reconciliation Rule

The reconciliation rule is:

```text
Input = Accepted Clean + Rejected Quarantine + Duplicates
```

In validation reports, this appears as raw, clean, quarantine, and `reconciled=true` fields for streaming sources. It proves that invalid and duplicate records were accounted for rather than ignored.

---

## 17. Watermarking

The project uses two different watermark concepts.

### 17.1 Spark event-time watermark

Spark Structured Streaming uses event-time watermarking to bound event-time state and support streaming reliability. The allowed lateness setting is controlled by:

```text
streaming.allowed_lateness_minutes: 30
```

Late records are also flagged with `late_arrival` in clean clickstream and web log tables.

### 17.2 Incremental processing watermark

The User SCD2 batch job stores progress in `ecommerce.audit.watermarks`, using CDC progress such as `source_lsn`. This prevents already-processed CDC records from being processed again in incremental SCD2 logic.

These two watermark types solve different problems and should not be described as the same mechanism.

---

## 18. Late Arrival Handling

Late arrival handling does not mean that the project silently drops valid late records. Valid late records can be accepted and flagged with `late_arrival=true` when they fall outside the allowed event-time window relative to observed stream time.

This allows downstream analysis to distinguish normal events from late-arriving events without losing them.

---

## 19. Evidence Commands

The audit inspection job prints evidence for screenshots:

```bash
docker compose exec -T spark-engine bash -lc '
cd /opt/project
PYTHONPATH=/opt/project/spark_jobs \
spark-submit --master local[2] \
  --conf spark.ui.enabled=false \
  /opt/project/spark_jobs/inspect_audit_counts.py \
  2>/tmp/audit_spark_noise.log
'
```

The `2>/tmp/audit_spark_noise.log` redirection hides long Spark startup logs and leaves the evidence tables readable in the terminal.

---

## 20. Pipeline Guarantees and Non-Guarantees

### 20.1 Guarantees implemented

- Raw Kafka payload preservation.
- Clean table writes for valid data.
- Quarantine writes for invalid and duplicate data.
- CDC metadata preservation.
- User SCD2 history.
- External API skip/failure evidence.
- Validation before serving publication.
- Serving build evidence.

### 20.2 Not implemented as production features

- Managed cloud deployment.
- Full automated schema evolution demonstration.
- ML-based recommendation scoring.
- Real-time dashboard refresh directly from Kafka.
- Product CDC.
- Order SCD2.

These are valid future enhancements but are outside the approved project scope.
