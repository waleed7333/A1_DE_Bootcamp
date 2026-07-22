# Pipelines, Quality, and Lakehouse

## Purpose

This document describes the processing architecture, data quality model, and Apache Iceberg lakehouse design used by **Clickstream Personalization Platform**.

The platform uses two coordinated processing paths:

```text
Continuous Spark Structured Streaming
Scheduled Airflow-triggered Spark Batch
```

The streaming path handles continuous ingestion, validation, enrichment, deduplication, quarantine routing, and clean table publication. The batch path handles slowly changing dimensions, external context enrichment, lakehouse validation, and serving publication.

Together, these paths convert heterogeneous source data into governed analytical tables that can be served to ClickHouse and consumed by Power BI.

---

## Processing Architecture

![Data Flow](../diagrams/02_data_flow.png)

The project separates processing into two distinct responsibilities:

| Processing Path | Responsibility |
|---|---|
| Spark Structured Streaming | Processes Kafka topics continuously into raw, processed, quarantine, and audit Iceberg tables. |
| Spark Batch | Executes scheduled analytical jobs for SCD2, weather enrichment, holiday enrichment, validation, and serving publication. |

The separation keeps real-time ingestion independent from scheduled analytical publication.

```text
Kafka topics
  → Spark Structured Streaming
  → Iceberg raw / processed / audit

Iceberg processed tables
  → Airflow-triggered Spark Batch
  → SCD2 / enrichment / validation / ClickHouse serving
```

---

## Pipeline Responsibilities

| Area | Responsibility |
|---|---|
| Ingestion | Read source data from Kafka topics, reference files, CDC streams, and scheduled context sources. |
| Raw preservation | Store Kafka payloads and metadata in a unified raw Iceberg table. |
| Parsing | Convert source payloads into structured records. |
| Validation | Enforce source-level and event-level data contracts. |
| Deduplication | Detect duplicate source records using source-specific identifiers. |
| Enrichment | Add GeoIP, user, product, weather, holiday, and context attributes where applicable. |
| CDC normalization | Convert Debezium envelopes into clean CDC event tables. |
| SCD Type 2 | Maintain current and historical user profile versions. |
| Quarantine | Store invalid and duplicate records with reason codes. |
| Audit | Record pipeline runs, quality metrics, watermarks, validation results, and serving evidence. |
| Serving publication | Publish curated dimensions, facts, marts, and stable views to ClickHouse. |

---

## Streaming Pipeline

The streaming pipeline is implemented with Spark Structured Streaming and consumes the project Kafka topics.

### Kafka Topics Processed

| Topic | Source | Clean Target |
|---|---|---|
| `clickstream-events` | Clickstream event publisher | `ecommerce.processed.clickstream_clean` |
| `webserver-logs` | Filebeat web log shipper | `ecommerce.processed.webserver_logs_clean` |
| `users-cdc` | Debezium users connector | `ecommerce.processed.users_cdc_clean` |
| `orders-cdc` | Debezium orders connector | `ecommerce.processed.orders_cdc_clean` |
| `order-items-cdc` | Debezium order items connector | `ecommerce.processed.order_items_cdc_clean` |

Every Kafka message is also preserved in:

```text
ecommerce.raw.kafka_messages
```

The raw table provides lineage, replay visibility, topic-level traceability, and offset-level evidence.

---

## Streaming Flow

The streaming job follows this processing flow:

```text
Read Kafka topics
  → Normalize Kafka metadata
  → Write raw Kafka messages
  → Parse source payloads
  → Apply validation rules
  → Detect duplicates
  → Enrich records
  → Write clean processed tables
  → Write quarantine records
  → Write quality metrics
  → Update pipeline runs and watermarks
```

This flow ensures that each record is either accepted into a clean analytical table or recorded as quality evidence.

---

## Raw Kafka Preservation

The raw layer captures Kafka messages before source-specific transformation.

### Table

```text
ecommerce.raw.kafka_messages
```

### Purpose

The raw table stores:

| Field Category | Examples |
|---|---|
| Kafka metadata | Topic, partition, offset, key, timestamp. |
| Source metadata | Source name and ingestion timestamp. |
| Payload | Raw Kafka message value. |
| Processing evidence | Pipeline run ID and ingestion metadata. |

### Role in the Platform

`raw.kafka_messages` is the immutable landing point for Kafka-based sources. It is used for lineage, ingestion evidence, audit inspection, and source-level traceability.

Only Kafka-based sources are written to this table:

```text
clickstream-events
webserver-logs
users-cdc
orders-cdc
order-items-cdc
```

Reference and context sources such as product catalog, GeoIP, weather, and holidays are handled through batch or enrichment paths and do not enter the raw Kafka table.

---

## Clickstream Processing

Clickstream events are validated, deduplicated, enriched, and written to the clean lakehouse table.

### Input

```text
Kafka topic: clickstream-events
```

### Output

```text
ecommerce.processed.clickstream_clean
```

### Processing Steps

| Step | Description |
|---|---|
| Parse JSON | Converts raw JSON payloads into structured event records. |
| Validate identity | Checks required event, session, timestamp, actor, and event-type fields. |
| Validate event-specific fields | Enforces product and checkout requirements based on event type. |
| Deduplicate | Detects duplicate `event_id` records. |
| Enrich GeoIP | Adds country, city, coordinates, and timezone from IP address. |
| Normalize timestamps | Produces timestamp and date fields used by downstream analysis. |
| Publish clean data | Writes accepted records to `clickstream_clean`. |
| Route evidence | Writes rejected and duplicate records to quarantine and quality metrics. |

### Analytical Role

The clean clickstream table is the foundation for:

- Event volume analysis.
- Session analysis.
- User journey reconstruction.
- Funnel progression.
- Product engagement.
- Search behavior.
- Cart behavior.
- Checkout behavior.
- Personalization candidate generation.
- Geo and context analytics.

---

## Web Log Processing

Web server logs are processed from Filebeat-shipped Kafka messages.

### Input

```text
Kafka topic: webserver-logs
```

### Output

```text
ecommerce.processed.webserver_logs_clean
```

### Processing Steps

| Step | Description |
|---|---|
| Parse log JSON | Converts `.log` JSON lines into structured web request records. |
| Validate required fields | Checks request ID, timestamp, HTTP method, path, status code, and latency fields. |
| Deduplicate | Detects duplicate request records. |
| Enrich GeoIP | Adds geographical context from IP address. |
| Normalize request metrics | Structures response code and response time values. |
| Publish clean data | Writes accepted records to `webserver_logs_clean`. |
| Route evidence | Writes invalid and duplicate records to quarantine and quality metrics. |

### Analytical Role

The clean web log table supports:

- Web experience analysis.
- HTTP status distribution.
- Response latency monitoring.
- Request path analysis.
- Clickstream-to-request correlation through `request_id`.
- Geo-based web traffic analysis.

---

## CDC Processing

The platform captures PostgreSQL changes through Debezium and processes them with Spark Structured Streaming.

### CDC Topics

| Topic | Source Table | Clean Target |
|---|---|---|
| `users-cdc` | `users` | `ecommerce.processed.users_cdc_clean` |
| `orders-cdc` | `orders` | `ecommerce.processed.orders_cdc_clean` |
| `order-items-cdc` | `order_items` | `ecommerce.processed.order_items_cdc_clean` |

### CDC Responsibilities

| Responsibility | Description |
|---|---|
| Debezium envelope parsing | Reads `before`, `after`, `op`, source metadata, and timestamps. |
| Operation normalization | Preserves insert, update, delete, and snapshot operations. |
| Source ordering | Retains `source_lsn` and `source_ts_ms` for lineage and ordering. |
| Clean CDC publication | Writes structured CDC events to clean Iceberg tables. |
| Audit evidence | Records CDC pipeline metrics and quarantine records when needed. |

### CDC Analytical Role

CDC clean tables provide:

- Transactional change history.
- User profile change history.
- Order and order item facts.
- Input for SCD Type 2.
- Serving-layer facts and dimensions.
- CDC lineage through source metadata.

---

## Batch Pipeline

Scheduled analytical processing is orchestrated by Airflow through the `analytics_refresh` workflow.

![Analytics Refresh Orchestration](../diagrams/06_analytics_refresh_orchestration.png)

### Batch Jobs

| Job | Input | Output |
|---|---|---|
| `user_scd2` | `users_cdc_clean` | `user_profile_scd2` |
| `weather_enrichment` | `clickstream_clean` location-hour combinations | `weather_clean` |
| `holiday_enrichment` | Country-date combinations | `holidays_clean` |
| `validate_lakehouse` | Raw, processed, audit, and relationship tables | `validation_runs`, reports |
| `publish_serving` | Clean Iceberg tables and marts | ClickHouse serving tables and views |

The batch pipeline transforms clean lakehouse data into historical dimensions, contextual enrichment tables, validation evidence, and serving-ready analytical outputs.

---

## User SCD Type 2 Pipeline

![CDC and SCD2 Flow](../diagrams/04_cdc_scd2_flow.png)

The user SCD Type 2 pipeline builds historical user profile state from clean user CDC events.

### Input

```text
ecommerce.processed.users_cdc_clean
```

### Output

```text
ecommerce.processed.user_profile_scd2
```

### Responsibility

The job maintains user profile history by:

| Step | Description |
|---|---|
| Read clean CDC | Loads validated user CDC events. |
| Order changes | Uses source metadata to process changes consistently. |
| Detect profile changes | Compares relevant user attributes across versions. |
| Close previous version | Sets `effective_to` and marks previous profile as not current. |
| Open new version | Creates a new active version with `is_current = true`. |
| Preserve lineage | Carries source CDC metadata into the SCD2 table. |

### SCD2 Fields

| Field | Purpose |
|---|---|
| `user_id` | User business key. |
| `membership_type` | User membership tier. |
| `account_status` | Account state. |
| `country_code` | User country context. |
| `city` | User city context. |
| `effective_from` | Start timestamp for the version. |
| `effective_to` | End timestamp for the version. |
| `is_current` | Current active profile flag. |
| `source_lsn` | CDC ordering reference. |
| `source_ts_ms` | Source change timestamp. |

The SCD2 table supports current-user serving views and historical user profile analysis.

---

## Weather Enrichment Pipeline

The weather enrichment pipeline adds environmental context to location and hour combinations observed in clean clickstream activity.

### Input

```text
ecommerce.processed.clickstream_clean
```

### Output

```text
ecommerce.processed.weather_clean
```

### Processing Contract

| Step | Description |
|---|---|
| Derive location-hour keys | Extracts distinct latitude, longitude, and hourly timestamps from clickstream records. |
| Build weather keys | Creates stable weather lookup keys. |
| Fetch weather context | Calls Open-Meteo historical weather API. |
| Normalize response | Converts temperature, precipitation, weather code, and condition values into clean fields. |
| Upsert enrichment rows | Updates weather records by `weather_key` and inserts missing records. |
| Record failures | Writes external API failure evidence when calls cannot be completed. |

### Main Output Fields

| Field | Description |
|---|---|
| `weather_key` | Stable location-hour key. |
| `latitude` | Lookup latitude. |
| `longitude` | Lookup longitude. |
| `weather_hour` | Hourly weather timestamp. |
| `temperature_c` | Temperature in Celsius. |
| `precipitation_mm` | Precipitation in millimeters. |
| `weather_code` | Weather code returned by the provider. |
| `weather_condition` | Normalized weather condition label. |
| `coverage_status` | Weather coverage status. |
| `fetched_at` | Fetch timestamp. |

Weather enrichment supports context-aware engagement, revenue, and personalization analysis.

---

## Holiday Enrichment Pipeline

The holiday enrichment pipeline adds country-level calendar context to analytical dates.

### Input

```text
Country and date combinations from clean analytical data
```

### Output

```text
ecommerce.processed.holidays_clean
```

### Processing Contract

| Step | Description |
|---|---|
| Derive country-year keys | Extracts required countries and years from observed activity. |
| Fetch holiday data | Calls Calendarific API for the required country-year combinations. |
| Normalize response | Converts API responses into country, date, name, type, and year fields. |
| Publish clean context | Writes holiday records to `holidays_clean`. |
| Record failures | Writes external API failure evidence when enrichment requests cannot be completed. |

### Main Output Fields

| Field | Description |
|---|---|
| `holiday_key` | Stable country-date holiday key. |
| `country_code` | Country code. |
| `holiday_date` | Holiday date. |
| `holiday_name` | Holiday name. |
| `holiday_type` | Holiday type or category. |
| `year` | Holiday year. |
| `fetched_at` | Fetch timestamp. |

Holiday enrichment supports country-level context analysis and holiday-aware dashboard visuals.

---

## Lakehouse Design

![Lakehouse Zones](../diagrams/03_lakehouse_zones.png)

The lakehouse is implemented with Apache Iceberg tables stored on MinIO.

```text
S3-compatible warehouse:
s3://ecommerce-lakehouse/warehouse/
```

The Iceberg catalog is organized into three namespaces:

```text
ecommerce.raw
ecommerce.processed
ecommerce.audit
```

Each namespace has a dedicated responsibility.

---

## Raw Zone

The raw zone preserves source messages before transformation.

| Table | Purpose |
|---|---|
| `raw.kafka_messages` | Unified Kafka raw landing table for streaming sources. |

### Raw Zone Responsibilities

| Responsibility | Description |
|---|---|
| Preserve payloads | Stores raw Kafka values before source-specific processing. |
| Preserve Kafka metadata | Stores topic, partition, offset, and message metadata. |
| Support lineage | Allows source-level tracing from clean records back to Kafka input. |
| Support audit | Provides evidence that messages entered the processing layer. |

---

## Processed Zone

The processed zone stores clean analytical tables.

| Table | Built From | Purpose |
|---|---|---|
| `product_catalog_clean` | Product Catalog CSV | Product reference data. |
| `clickstream_clean` | Clickstream Kafka topic | Validated and enriched behavioral events. |
| `webserver_logs_clean` | Web log Kafka topic | Validated and enriched web request records. |
| `users_cdc_clean` | Users CDC topic | Clean user CDC event history. |
| `orders_cdc_clean` | Orders CDC topic | Clean order CDC event history. |
| `order_items_cdc_clean` | Order Items CDC topic | Clean order item CDC event history. |
| `user_profile_scd2` | Users CDC clean table | Current and historical user profile dimension. |
| `weather_clean` | Weather API | Weather context records. |
| `holidays_clean` | Holiday API | Holiday context records. |

### Processed Zone Responsibilities

| Responsibility | Description |
|---|---|
| Store accepted records | Holds only records that passed validation and processing rules. |
| Normalize schemas | Provides structured tables with typed fields. |
| Enable enrichment | Stores GeoIP, context, and profile enrichment outputs. |
| Support serving | Acts as the source layer for ClickHouse publication. |
| Support validation | Provides the trusted analytical base for quality and relationship checks. |

---

## Audit Zone

The audit zone stores operational evidence.

| Table | Purpose |
|---|---|
| `pipeline_runs` | Pipeline execution metadata and statuses. |
| `quality_metrics` | Input, accepted, rejected, and duplicate counts. |
| `external_api_failures` | External enrichment failure evidence. |
| `validation_runs` | Lakehouse validation result history. |
| `serving_builds` | Serving publication history. |
| `watermarks` | Streaming and batch watermark evidence. |
| `quarantine_records` | Invalid and duplicate record evidence. |

### Audit Zone Responsibilities

| Responsibility | Description |
|---|---|
| Execution evidence | Records when jobs run and how they complete. |
| Quality evidence | Tracks counts across accepted, rejected, and duplicate records. |
| Quarantine evidence | Stores records that do not meet source contracts. |
| Validation evidence | Captures validation status and result details. |
| Serving evidence | Records ClickHouse serving build publication status. |
| Operational visibility | Feeds status reports and the Operations Console. |

---

## Iceberg Table Partitioning

Iceberg tables are partitioned according to their access patterns.

| Table | Partition Strategy |
|---|---|
| `raw.kafka_messages` | `days(ingested_at), source_name` |
| `processed.product_catalog_clean` | `category` |
| `processed.clickstream_clean` | `days(event_timestamp)` |
| `processed.webserver_logs_clean` | `days(log_timestamp)` |
| `processed.users_cdc_clean` | `days(processed_at)` |
| `processed.orders_cdc_clean` | `days(processed_at)` |
| `processed.order_items_cdc_clean` | `days(processed_at)` |
| `processed.user_profile_scd2` | `days(effective_from)` |
| `processed.weather_clean` | `days(weather_hour)` |
| `processed.holidays_clean` | `year` |
| `audit.pipeline_runs` | `days(recorded_at)` |
| `audit.quality_metrics` | `days(recorded_at)` |
| `audit.quarantine_records` | `days(quarantined_at), source_name` |
| `audit.external_api_failures` | `days(occurred_at)` |
| `audit.watermarks` | `days(updated_at)` |
| `audit.validation_runs` | `days(created_at)` |
| `audit.serving_builds` | `days(created_at)` |

The partitioning model supports date-based analysis, source-level filtering, audit inspection, and efficient access to commonly queried time windows.

---

## Storage Format

The lakehouse uses Iceberg-managed Parquet tables with compression and table metadata.

| Feature | Purpose |
|---|---|
| Parquet | Columnar storage for analytical workloads. |
| Compression | Reduces storage footprint and improves scan efficiency. |
| Iceberg metadata | Maintains table snapshots, schemas, partition information, and file manifests. |
| Partition pruning | Reduces scanned data for time-based and source-based queries. |
| Predicate pushdown | Allows query engines to skip irrelevant data where supported. |
| Schema evolution support | Allows managed table changes through Iceberg table metadata. |

Iceberg provides a structured table abstraction over object storage, making the lakehouse queryable and auditable.

---

## Data Quality Model

![Data Quality and Audit Reconciliation](../diagrams/07_data_quality_audit_reconciliation.png)

The project treats data quality as part of normal pipeline execution.

The central reconciliation contract is:

```text
Input records = Accepted records + Rejected records + Duplicate records
```

This model ensures every record processed by the pipeline has an explainable outcome.

---

## Validation Categories

| Category | Description |
|---|---|
| Required field validation | Ensures source-specific keys and timestamps are present. |
| Event contract validation | Checks event-specific requirements such as product and checkout fields. |
| CDC validation | Ensures Debezium records are normalized and source metadata is preserved. |
| Duplicate detection | Identifies duplicate records by source business keys. |
| Relationship checks | Validates analytical links such as request, product, order, checkout, and user relationships. |
| SCD2 checks | Validates current profile state and historical profile consistency. |
| Context checks | Validates weather and holiday enrichment coverage where applicable. |
| Serving checks | Confirms ClickHouse serving outputs and stable views are available for reporting. |

---

## Quarantine Model

Invalid and duplicate records are written to:

```text
ecommerce.audit.quarantine_records
```

### Quarantine Responsibilities

| Responsibility | Description |
|---|---|
| Preserve rejected records | Keeps invalid records visible for inspection. |
| Classify issues | Stores structured reason codes for invalid, duplicate, parse, or contract-related records. |
| Support evidence | Provides proof of how records were handled. |
| Protect clean tables | Prevents invalid records from entering processed analytical tables. |

### Quarantine Record Information

| Field | Purpose |
|---|---|
| `source_name` | Identifies the source or Kafka topic. |
| `record_key` | Stores the source-level record key when available. |
| `reason_code` | Describes why the record was quarantined. |
| `raw_payload` | Preserves the rejected source payload or representative content. |
| `pipeline_run_id` | Links the record to a pipeline run. |
| `quarantined_at` | Records when the record was quarantined. |

The quarantine model keeps clean analytical tables reliable while preserving evidence for invalid or duplicate inputs.

---

## Quality Metrics Model

Quality metrics are written to:

```text
ecommerce.audit.quality_metrics
```

### Metric Contract

| Field | Purpose |
|---|---|
| `pipeline_run_id` | Identifies the pipeline run. |
| `source_name` | Identifies the source being measured. |
| `input_records` | Total number of records read. |
| `accepted_records` | Number of records written to clean tables. |
| `rejected_records` | Number of invalid records routed to quarantine. |
| `duplicate_records` | Number of duplicate records detected. |
| `recorded_at` | Timestamp when the metric was recorded. |

### Metric Usage

Quality metrics support:

- Pipeline reconciliation.
- Source health review.
- Quarantine analysis.
- Validation reports.
- Operations Console evidence.

---

## Watermark Model

Watermark records are written to:

```text
ecommerce.audit.watermarks
```

Watermarks provide evidence of processing progress across streaming and batch jobs.

| Field | Purpose |
|---|---|
| `source_name` | Source or processing area. |
| `watermark_name` | Name of the tracked watermark. |
| `watermark_value` | Last observed value or progress marker. |
| `updated_at` | Timestamp when the watermark was updated. |

Watermarks help the platform expose processing progress and currentness through operational evidence.

---

## External API Failure Model

External enrichment failures are written to:

```text
ecommerce.audit.external_api_failures
```

### Purpose

The failure table preserves structured evidence for external API calls that cannot be completed successfully.

| Field | Purpose |
|---|---|
| `run_id` | Batch run identifier. |
| `provider` | External provider name. |
| `request_key` | Country, date, location, or time key for the request. |
| `http_status` | HTTP response status when available. |
| `error_message` | Error detail. |
| `attempt_count` | Number of attempts represented by the record. |
| `status` | Normalized status value. |
| `occurred_at` | Timestamp when the failure was recorded. |

The table keeps external context enrichment auditable and visible to validation and operations layers.

---

## Lakehouse Validation

The `validate_lakehouse` Spark batch job validates the lakehouse after enrichment jobs complete and before serving publication is finalized.

### Validation Areas

| Area | Validation Purpose |
|---|---|
| Raw and clean table presence | Confirms expected Iceberg tables exist and can be queried. |
| Record reconciliation | Validates accepted, rejected, and duplicate record accounting. |
| Required clean outputs | Confirms core processed tables contain analytical data. |
| Relationship coverage | Checks important relationships across clickstream, web logs, orders, order items, users, and products. |
| SCD2 state | Validates current user profile rows and historical state behavior. |
| Context enrichment | Verifies weather and holiday context tables are available. |
| Audit evidence | Confirms validation and quality evidence is recorded. |

### Validation Output

Validation results are written to:

```text
ecommerce.audit.validation_runs
reports/validation_latest.json
```

The latest validation report is used by CLI status output and the Operations Console.

---

## Serving Publication

The `publish_serving` Spark batch job publishes curated analytical outputs from the lakehouse to ClickHouse.

### Input

```text
Iceberg processed and analytical tables
```

### Output

```text
ClickHouse physical serving tables
ClickHouse stable v_* views
Iceberg audit serving build evidence
reports/serving_latest.json
```

### Serving Responsibilities

| Responsibility | Description |
|---|---|
| Build dimensions | Publishes date, product, and current user dimensions. |
| Build facts | Publishes clickstream, order, and order item fact tables. |
| Build marts | Publishes journey, navigation, product, web experience, context, and personalization marts. |
| Version outputs | Assigns a `serving_build_id` to each serving publication. |
| Activate latest build | Marks the latest successful build as active. |
| Validate views | Confirms the stable twelve Power BI views are available. |
| Record evidence | Writes serving build status and row count summary. |

The serving layer is described in detail in [Serving and Dashboards](04_SERVING_AND_DASHBOARDS.md).

---

## Final Iceberg Table Contract

The platform maintains the following Iceberg table contract.

| Namespace | Tables |
|---|---|
| `ecommerce.raw` | `kafka_messages` |
| `ecommerce.processed` | `product_catalog_clean`, `clickstream_clean`, `webserver_logs_clean`, `users_cdc_clean`, `orders_cdc_clean`, `order_items_cdc_clean`, `user_profile_scd2`, `weather_clean`, `holidays_clean` |
| `ecommerce.audit` | `pipeline_runs`, `quality_metrics`, `external_api_failures`, `validation_runs`, `serving_builds`, `watermarks`, `quarantine_records` |

This contract separates raw source preservation, clean analytical processing, and operational evidence.

---

## Pipeline-to-Table Matrix

| Pipeline Stage | Main Outputs |
|---|---|
| Kafka raw capture | `raw.kafka_messages` |
| Clickstream cleaning | `processed.clickstream_clean`, `audit.quarantine_records`, `audit.quality_metrics` |
| Web log cleaning | `processed.webserver_logs_clean`, `audit.quarantine_records`, `audit.quality_metrics` |
| Users CDC cleaning | `processed.users_cdc_clean`, `audit.quality_metrics` |
| Orders CDC cleaning | `processed.orders_cdc_clean`, `audit.quality_metrics` |
| Order items CDC cleaning | `processed.order_items_cdc_clean`, `audit.quality_metrics` |
| User SCD2 batch | `processed.user_profile_scd2`, `audit.pipeline_runs` |
| Weather enrichment | `processed.weather_clean`, `audit.external_api_failures` |
| Holiday enrichment | `processed.holidays_clean`, `audit.external_api_failures` |
| Lakehouse validation | `audit.validation_runs`, `reports/validation_latest.json` |
| Serving publication | `audit.serving_builds`, `reports/serving_latest.json`, ClickHouse serving tables and views |

---

## Analytical Readiness

The lakehouse is considered analytically ready when:

```text
Core processed tables are populated.
Quality metrics reconcile input, accepted, rejected, and duplicate records.
Quarantine records are available for invalid and duplicate inputs.
User SCD2 has a current profile view of users.
Weather and holiday context tables are available.
Lakehouse validation is recorded.
Serving publication is completed.
ClickHouse stable views are available for Power BI.
```

These conditions are checked through batch validation, serving evidence, CLI status output, and the Operations Console.

---

## Processing Contract Summary

The final processing and lakehouse contract is:

```text
Kafka streaming sources
  → raw.kafka_messages
  → processed clean tables
  → audit quality and quarantine evidence

Clean CDC events
  → user_profile_scd2

Clean behavioral and context data
  → weather and holiday enrichment
  → validation evidence
  → ClickHouse serving publication
```

The lakehouse stores the trusted analytical foundation of the platform. ClickHouse exposes the final serving views, and Power BI consumes those views through a governed reporting model.