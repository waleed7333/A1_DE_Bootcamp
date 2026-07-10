
# Pipelines, Data Quality, and Lakehouse

## 1. Purpose

This document describes the project processing pipelines, data quality controls, audit design, quarantine handling, and lakehouse table layout.

Source contracts are documented in:

```text
docs/02_DATA_SOURCES_AND_CONTRACTS.md
```

Serving design is documented in:

```text
docs/04_SERVING_AND_DASHBOARDS.md
```

---

## 2. Processing Paths

The platform has two main processing paths:

| Path           | Processing Engine             | Purpose                                                                                         |
| -------------- | ----------------------------- | ----------------------------------------------------------------------------------------------- |
| Streaming path | Spark Structured Streaming    | Continuous ingestion, validation, deduplication, GeoIP enrichment, clean Iceberg writes         |
| Batch path     | Airflow-triggered Spark batch | Product load, User SCD2, weather enrichment, holiday enrichment, validation, ClickHouse publish |

---

## 3. Streaming Pipeline

### 3.1 Inputs

Spark Structured Streaming consumes:

```text
clickstream-events
webserver-logs
users-cdc
orders-cdc
order-items-cdc
```

### 3.2 Raw persistence

Kafka messages are persisted to:

```text
raw.kafka_messages
```

This preserves Kafka-level metadata such as:

```text
source_name
kafka_topic
kafka_partition
kafka_offset
kafka_timestamp
source_record_id
raw_payload
source_file
ingested_at
stream_batch_id
```

### 3.3 Clean streaming outputs

Streaming jobs produce:

```text
processed.clickstream_clean
processed.webserver_logs_clean
processed.users_cdc_clean
processed.orders_cdc_clean
processed.order_items_cdc_clean
```

### 3.4 Streaming responsibilities

The streaming pipeline performs:

* JSON parsing.
* Contract validation.
* Duplicate detection.
* Late arrival tracking.
* CDC payload parsing.
* GeoIP enrichment for clickstream and web logs.
* Kafka metadata preservation.
* Clean Iceberg table writes.
* Quarantine and audit updates.

---

## 4. CDC Pipeline

### 4.1 CDC flow

```text
PostgreSQL
    → Debezium Connect
    → Kafka CDC topics
    → Spark Structured Streaming
    → CDC clean Iceberg tables
```

### 4.2 CDC topics

```text
users-cdc
orders-cdc
order-items-cdc
```

### 4.3 CDC clean tables

```text
processed.users_cdc_clean
processed.orders_cdc_clean
processed.order_items_cdc_clean
```

### 4.4 User SCD Type 2

User Profile history is built from:

```text
processed.users_cdc_clean
```

Target table:

```text
processed.user_profile_scd2
```

SCD Type 2 applies only to Users.

Orders and Order Items remain CDC-derived clean tables and are later published as serving facts.

---

## 5. Batch Pipeline

Batch jobs are orchestrated by Airflow or by the project analytics refresh command.

Main batch sequence:

```text
user_scd2
    → weather_enrichment
    → holiday_enrichment
    → validate_lakehouse
    → publish_serving
```

Recommended diagram:

```text
diagrams/06_orchestration_flow.png
```

---

## 6. Product Catalog Batch Load

Product Catalog is loaded as a static CSV snapshot.

Input:

```text
data/source/product_catalog.csv
```

Output:

```text
processed.product_catalog_clean
```

Product Catalog is not streamed and does not use CDC.

---

## 7. User SCD Type 2 Batch

### 7.1 Input

```text
processed.users_cdc_clean
```

### 7.2 Output

```text
processed.user_profile_scd2
```

### 7.3 Main SCD2 fields

```text
user_id
email
first_name
last_name
membership_type
account_status
country_code
city
is_deleted
effective_from
effective_to
is_current
version_sequence
source_lsn
created_at
updated_at
processed_at
```

### 7.4 Validation expectations

The SCD2 table must satisfy:

```text
duplicate_current_users = 0
invalid_effective_ranges = 0
```

---

## 8. Weather Enrichment Batch

### 8.1 Input

Weather keys are discovered from:

```text
processed.clickstream_clean
```

Required fields:

```text
geo_latitude
geo_longitude
event_timestamp
```

### 8.2 External source

```text
Open-Meteo Historical Weather API
```

### 8.3 Output

```text
processed.weather_clean
```

### 8.4 Operational behavior

Current-day weather can be unavailable by design when using the historical archive. The enrichment job tracks coverage status and records failures in audit structures when applicable.

---

## 9. Holiday Enrichment Batch

### 9.1 Input

Holiday keys are discovered from:

```text
processed.clickstream_clean
```

Required fields:

```text
geo_country_code
event_timestamp
geo_timezone
```

### 9.2 External source

```text
Calendarific API
```

### 9.3 Output

```text
processed.holidays_clean
```

API failures are tracked in:

```text
audit.external_api_failures
```

---

## 10. Data Quality Model

The project uses explicit reconciliation:

```text
Input = Accepted Clean + Rejected Quarantine + Duplicates
```

This prevents silent record loss and allows source-level quality reporting.

---

## 11. Quality Controls

| Control                   | Purpose                                                             |
| ------------------------- | ------------------------------------------------------------------- |
| Required field validation | Ensures mandatory identifiers and timestamps exist                  |
| Event type validation     | Enforces the clickstream event contract                             |
| Product event validation  | Ensures product events have `product_id`                            |
| Checkout validation       | Ensures checkout events have required checkout/order keys           |
| CDC operation validation  | Ensures CDC events use supported Debezium operation values          |
| Duplicate detection       | Prevents duplicate records from entering clean analytics            |
| Late arrival tracking     | Tracks records arriving outside expected event-time windows         |
| API coverage tracking     | Separates expected coverage gaps from actual failures               |
| SCD2 validation           | Ensures user profile history has valid current rows and date ranges |
| Serving validation        | Ensures ClickHouse publish is based on validated lakehouse data     |

---

## 12. Quarantine

Invalid and duplicate records are tracked through quarantine structures.

Quarantine records include:

* Source name.
* Record identifier.
* Raw payload or source reference.
* Rejection reason.
* Processing timestamp.
* Pipeline run identifier when available.

Quarantine allows the project to retain evidence of rejected records without allowing them into clean analytical tables.

---

## 13. Audit Tables

The project maintains audit tables for operational transparency.

| Table                         | Purpose                                                      |
| ----------------------------- | ------------------------------------------------------------ |
| `audit.pipeline_runs`         | Pipeline execution evidence                                  |
| `audit.quality_metrics`       | Source-level input, accepted, rejected, and duplicate counts |
| `audit.quarantine_records`    | Invalid and duplicate record evidence                        |
| `audit.external_api_failures` | Weather and holiday API failure records                      |
| `audit.watermarks`            | Streaming and batch watermark evidence                       |
| `audit.validation_runs`       | Lakehouse validation results                                 |
| `audit.serving_builds`        | ClickHouse serving build evidence                            |

---

## 14. Lakehouse Zones

The project uses logical processing zones rather than relying on generic Bronze/Silver/Gold naming.

| Zone       | Purpose                                                                         |
| ---------- | ------------------------------------------------------------------------------- |
| Source     | Local generated files, PostgreSQL source tables, external APIs, GeoIP reference |
| Raw        | Preserved Kafka payloads and Kafka metadata                                     |
| Processed  | Validated, deduplicated, enriched Iceberg tables                                |
| Audit      | Quality metrics, runs, failures, validation, serving builds                     |
| Quarantine | Invalid and duplicate record evidence                                           |
| Serving    | ClickHouse dimensions, facts, marts, and views                                  |

Recommended diagram:

```text
diagrams/03_lakehouse_zones.png
```

---

## 15. Iceberg Tables

### 15.1 Raw table

```text
raw.kafka_messages
```

### 15.2 Processed tables

```text
processed.product_catalog_clean
processed.clickstream_clean
processed.webserver_logs_clean
processed.users_cdc_clean
processed.orders_cdc_clean
processed.order_items_cdc_clean
processed.user_profile_scd2
processed.weather_clean
processed.holidays_clean
```

### 15.3 Audit tables

```text
audit.pipeline_runs
audit.quality_metrics
audit.quarantine_records
audit.external_api_failures
audit.watermarks
audit.validation_runs
audit.serving_builds
```

---

## 16. Validation Reports

The latest validation report is written to:

```text
reports/validation_latest.json
```

The validation report is used to verify:

* Required Iceberg tables exist.
* Required row counts are present.
* SCD2 constraints are satisfied.
* Quarantine and audit checks are available.
* Lakehouse data is ready for serving publish.

---

## 17. Serving Publish Dependency

ClickHouse serving publish should run after lakehouse validation passes.

Expected sequence:

```text
validate_lakehouse
    → publish_serving
```

If validation fails, serving publish should not be treated as reliable.

---

## 18. Data Quality Diagram

Recommended diagram:

```text
diagrams/07_data_quality_reconciliation.png
```

The diagram should show:

```text
Input Records
    → Validation and Deduplication
    → Accepted Clean
    → Rejected Quarantine
    → Duplicates
    → Audit Metrics
    → Validation Report
```

---
