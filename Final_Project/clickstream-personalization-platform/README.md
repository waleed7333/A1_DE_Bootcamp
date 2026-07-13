# Clickstream Personalization Platform

## 1. Executive Summary

**Clickstream Personalization Platform** is an end-to-end data engineering platform for collecting, processing, validating, enriching, auditing, serving, and visualizing e-commerce website behavior. The platform is designed for the project **Clickstream Analysis for Website Personalization** and demonstrates both real-time and scheduled batch data engineering patterns in a reproducible local environment.

The system combines website clickstream events, structured web server logs, product reference data, PostgreSQL transactional data, PostgreSQL profile changes captured through CDC, GeoIP enrichment, historical weather enrichment, and holiday enrichment. The final analytical model is published to ClickHouse and consumed by Power BI through dashboard-ready `v_*` serving views.

The project is not a simple dashboard over static CSV files. It implements a full data platform with source generation, heterogeneous ingestion, Kafka topics, CDC capture, streaming ingestion, batch enrichment, Iceberg lakehouse tables, audit evidence, quarantine records, validation reports, versioned serving builds, an operations console, and a Power BI report.

---

## 2. Business Problem

Modern e-commerce teams need to understand how users navigate a website before they buy, abandon, or continue browsing. Transactional order tables alone only show completed purchases. They do not explain the path a user followed, where the user dropped off, whether a slow endpoint affected the journey, whether a product received interest without conversion, or whether external context such as location, weather, or holidays influenced behavior.

This platform answers questions such as:

- Which sessions reached checkout and which sessions leaked before purchase?
- Which products receive product views and cart events but do not convert?
- Which user segments, locations, devices, browsers, or traffic sources produce stronger journeys?
- How do web server status codes and response times align with user experience?
- Which countries, cities, weather conditions, and holidays appear in the analytical context?
- Which products are strong candidates for personalization or recommendation actions?
- Can the platform prove that invalid and duplicate records were handled instead of silently dropped?

The result is a governed analytical flow from raw source data to Power BI dashboards, supported by audit and validation evidence.

---

## 3. Project Objectives

The platform implements the following objectives:

1. Collect behavioral, operational, transactional, reference, and external context data from multiple heterogeneous sources.
2. Use both continuous streaming and scheduled batch processing.
3. Preserve raw Kafka payloads for traceability and replay evidence.
4. Validate, deduplicate, enrich, and clean data before analytical use.
5. Capture PostgreSQL changes through Debezium CDC and preserve CDC metadata.
6. Build User Profile SCD Type 2 history from cleaned user CDC events.
7. Enrich behavioral data with GeoIP, historical weather, and holiday context.
8. Store clean and audit data in Apache Iceberg tables on MinIO.
9. Publish validated analytical data to ClickHouse for low-latency dashboard queries.
10. Expose Power BI-ready views only, keeping raw processing logic outside the dashboard.
11. Provide evidence screenshots, validation reports, and operational proof that the platform works.

---

## 4. Final Platform Scope

### 4.1 Included data sources

| Source | Type | Ingestion method | Processing style | Main target |
|---|---:|---|---|---|
| Clickstream Events | JSONL event stream | Direct publisher to Kafka topic `clickstream-events` | Spark Structured Streaming | `ecommerce.processed.clickstream_clean` |
| Web Server Logs | Structured JSON `.log` file | Filebeat tails the log file and sends records to Kafka topic `webserver-logs` | Spark Structured Streaming | `ecommerce.processed.webserver_logs_clean` |
| Product Catalog | Static CSV snapshot | Initial Spark batch load | Batch validation and one-time clean load | `ecommerce.processed.product_catalog_clean` |
| PostgreSQL Users | Relational source table | Debezium CDC to Kafka topic `users-cdc` | Streaming CDC clean + batch SCD2 | `users_cdc_clean`, `user_profile_scd2` |
| PostgreSQL Orders | Relational source table | Debezium CDC to Kafka topic `orders-cdc` | Streaming CDC clean | `orders_cdc_clean` |
| PostgreSQL Order Items | Relational source table | Debezium CDC to Kafka topic `order-items-cdc` | Streaming CDC clean | `order_items_cdc_clean` |
| MaxMind GeoLite2 City | Local `.mmdb` reference database | Local lookup inside Spark processing | GeoIP enrichment | Geo fields in clickstream and web log clean tables |
| Open-Meteo | Historical weather API | Scheduled Spark batch API pull | Batch enrichment | `ecommerce.processed.weather_clean` |
| Calendarific | Holiday API | Scheduled Spark batch API pull | Batch enrichment | `ecommerce.processed.holidays_clean` |

### 4.2 Explicit design decisions

- The lakehouse uses **MinIO + Apache Iceberg**, not HDFS.
- The weather source is **Open-Meteo Historical Weather API**, not OpenWeather.
- Power BI reads only from ClickHouse `v_*` views.
- ClickHouse is refreshed only through the `publish_serving` batch job after validation passes.
- Airflow orchestrates batch jobs only.
- Spark Structured Streaming runs independently from Airflow.
- Product Catalog is a static initial clean load only.
- SCD Type 2 applies only to User Profile data.
- Orders and Order Items are CDC-cleaned and served analytically, but they are not SCD2 dimensions.
- GeoIP enrichment uses `ip_address` as the source input; source records do not predefine final country or city.
- Invalid and duplicate source records are written to `ecommerce.audit.quarantine_records`.
- Valid records are written to `ecommerce.processed.*` clean tables.

---

## 5. Architecture Summary

The platform has two main processing paths.

### 5.1 Continuous streaming path

```text
Clickstream JSONL publisher
Web server .log file through Filebeat
PostgreSQL CDC through Debezium
        ↓
Kafka topics
        ↓
Spark Structured Streaming
        ↓
Raw Kafka messages + processed clean Iceberg tables + audit/quarantine evidence
```

Streaming handles source parsing, validation, deduplication, Kafka metadata preservation, raw-message persistence, GeoIP enrichment, CDC cleaning, late-arrival flagging, and quarantine routing.

### 5.2 Scheduled batch path

```text
Iceberg processed tables
        ↓
Airflow-triggered Spark batch jobs
        ↓
User SCD2, weather enrichment, holiday enrichment, lakehouse validation
        ↓
publish_serving
        ↓
ClickHouse physical tables and latest-active v_* views
        ↓
Power BI Import dashboard
```

Batch processing handles operations that are better executed on a schedule: SCD2 rebuild/incremental update, external API enrichment, validation, and serving publication.

---

## 6. Hybrid ETL / ELT Pattern

The platform follows a **hybrid ETL/ELT lakehouse pattern**.

| Stage | Pattern | Explanation |
|---|---|---|
| Kafka to `raw.kafka_messages` | ELT-style | Raw payloads are loaded first into the lakehouse for traceability and later validation/replay evidence. |
| Raw/stream data to processed clean tables | ETL-style | Spark parses, validates, deduplicates, enriches, and writes clean Iceberg tables. |
| CDC clean to User SCD2 | ETL-style | Spark batch transforms CDC events into historical user profile versions. |
| Processed data to weather/holiday context | ETL-style batch enrichment | Spark discovers required keys, calls external APIs, transforms responses, and writes clean enrichment tables. |
| Iceberg processed data to ClickHouse | ETL-style serving publish | Spark transforms validated lakehouse data into dimensions, facts, marts, and serving views. |

The important point is that the project is not pure ETL and not pure ELT. It loads raw evidence first where needed, then applies controlled Spark transformations before serving data to ClickHouse and Power BI.

---

## 7. Logical Bronze / Silver / Gold Flow

Bronze, Silver, and Gold are logical data zones, not separate tools.

| Logical zone | Project implementation | Purpose |
|---|---|---|
| Bronze | `ecommerce.raw.kafka_messages` | Preserve raw Kafka payloads with topic, partition, offset, timestamp, source file, and stream batch ID. |
| Silver | `ecommerce.processed.*` Iceberg tables | Store validated, deduplicated, enriched, and structured clean data. |
| Audit sidecar | `ecommerce.audit.*` Iceberg tables | Store run evidence, quality metrics, quarantine records, external API failures, validation results, serving build records, and watermarks. |
| Gold | ClickHouse database `personalization_olap` | Store dashboard-ready physical dimensions, facts, marts, and latest-active `v_*` views. |
| Presentation | Power BI report | Display funnel, revenue, journey, personalization, context, and product analysis. |

---

## 8. Technology Stack and Tool Justification

| Tool | Role in the platform | Why it was selected | Project features used |
|---|---|---|---|
| Docker Compose | Local orchestration layer | Runs the full data platform reproducibly on one machine without external managed services. | Multi-container networking, service dependencies, health checks, resource limits, host port mapping. |
| PostgreSQL 16 | Operational relational source database and Iceberg JDBC catalog backend | Provides realistic relational source tables and logical replication support for Debezium CDC. Also stores Iceberg catalog metadata through the JDBC catalog. | `users`, `orders`, `order_items`, WAL logical replication, replication slots, `wal_level=logical`, Iceberg catalog metadata. |
| ZooKeeper | Kafka coordination service for Confluent Kafka 7.3.2 | Required because this Kafka image runs in ZooKeeper mode. | Broker coordination and metadata management. |
| Apache Kafka | Streaming backbone | Decouples producers from Spark consumers and provides ordered topic partitions with offsets for traceability. | Three brokers, RF=3, partitions=3, min ISR=2, business topics, Debezium internal topics, Kafka offsets. |
| Kafka UI | Kafka observability UI | Makes topics, partitions, offsets, and internal topics visible during validation. | Topic inspection for `clickstream-events`, `webserver-logs`, `users-cdc`, `orders-cdc`, `order-items-cdc`, and Debezium internal topics. |
| Debezium Connect | CDC capture from PostgreSQL | Captures table snapshots and later inserts/updates/deletes without building custom CDC logic. | Initial snapshot events, CDC operation codes, before/after images, source LSN, source timestamps, Kafka Connect internal topics. |
| Filebeat | Web log ingestion | Represents a realistic log-shipping path for `.log` files instead of treating all sources as identical application events. | Tails `data/source/web_logs/webserver_access.log`, stores registry state, publishes structured log lines to Kafka. |
| Spark Structured Streaming | Continuous processing engine | Handles real-time ingestion from Kafka topics and writes clean data to Iceberg. | Kafka reads, micro-batch processing, event-time watermarking, validation, deduplication, GeoIP enrichment, CDC parsing, quarantine writes, checkpointing. |
| Spark Batch | Scheduled analytical processing engine | Executes jobs that should run after clean data exists or require external API calls. | Product catalog load, User SCD2, weather enrichment, holiday enrichment, lakehouse validation, serving publish. |
| Apache Iceberg | Lakehouse table format | Provides managed table metadata, partitioning, schema control, snapshot-style storage, and table access through Spark. | Raw, processed, and audit namespaces; Parquet data files; table properties; partitioning by date/category/source. |
| MinIO | S3-compatible object storage | Provides local object storage for the Iceberg warehouse while preserving a cloud-like storage interface. | Bucket `ecommerce-lakehouse`, warehouse path `s3://ecommerce-lakehouse/warehouse`, S3 path-style access. |
| Airflow | Batch orchestration and monitoring | Schedules and monitors the refresh sequence without controlling the streaming job. | DAG `analytics_refresh`, sequential tasks, request bridge to the single Spark engine, retries, hourly schedule. |
| ClickHouse | OLAP serving database | Provides fast dashboard queries over dimensions, facts, and marts without making Power BI scan raw lakehouse tables. | MergeTree-style physical tables, database `personalization_olap`, serving control table, regular `v_*` views for the latest active build. |
| Power BI | Business intelligence dashboard | Presents final analytical metrics for project evaluation and business interpretation. | Import mode, ClickHouse views, two dashboard pages, funnel metrics, personalization candidates, context analysis. |
| Streamlit | Read-only Operations Console | Provides a lightweight UI for platform status and validation evidence without destructive controls. | Health/status display, runtime/report reading, ClickHouse checks, evidence summaries. |
| MaxMind GeoLite2 City | GeoIP reference enrichment | Converts IP addresses into country, city, coordinates, and timezone. | Local `.mmdb` lookup during Spark processing for clickstream and web log records. |
| Open-Meteo | Historical weather context | Provides weather attributes by latitude, longitude, and hour without requiring an API key. | Scheduled historical API pulls, weather code interpretation, skipped current/future dates recorded as external API evidence. |
| Calendarific | Holiday context | Adds country/year holiday context for downstream behavior analysis. | Scheduled API pulls by country/year, holiday name/type/date enrichment, failure tracking. |

---

## 9. Kafka Topics

The platform uses the following business topics:

| Topic | Source | Purpose |
|---|---|---|
| `clickstream-events` | Clickstream source publisher | Website behavioral event stream. |
| `webserver-logs` | Filebeat | Structured web access log stream. |
| `users-cdc` | Debezium | CDC events from PostgreSQL `users`. |
| `orders-cdc` | Debezium | CDC events from PostgreSQL `orders`. |
| `order-items-cdc` | Debezium | CDC events from PostgreSQL `order_items`. |

Debezium Connect also uses internal Kafka Connect topics:

```text
debezium-connect-configs
debezium-connect-offsets
debezium-connect-status
```

---

## 10. Iceberg Lakehouse Tables

### 10.1 Raw namespace

| Table | Purpose |
|---|---|
| `ecommerce.raw.kafka_messages` | Stores raw Kafka payloads with topic, partition, offset, timestamp, source record ID, source file, ingestion time, and stream batch ID. |

### 10.2 Processed namespace

| Table | Purpose |
|---|---|
| `ecommerce.processed.product_catalog_clean` | Static validated product catalog loaded once from CSV. |
| `ecommerce.processed.clickstream_clean` | Valid clickstream events enriched with GeoIP fields and Kafka metadata. |
| `ecommerce.processed.webserver_logs_clean` | Valid web log records enriched with GeoIP fields and Kafka metadata. |
| `ecommerce.processed.users_cdc_clean` | Clean Debezium CDC events for users. |
| `ecommerce.processed.orders_cdc_clean` | Clean Debezium CDC events for orders. |
| `ecommerce.processed.order_items_cdc_clean` | Clean Debezium CDC events for order items. |
| `ecommerce.processed.user_profile_scd2` | Historical Type 2 user profile table. |
| `ecommerce.processed.weather_clean` | Historical weather enrichment by latitude, longitude, and hour. |
| `ecommerce.processed.holidays_clean` | Holiday enrichment by country and year. |

### 10.3 Audit namespace

| Table | Purpose |
|---|---|
| `ecommerce.audit.pipeline_runs` | Records run-level status and counts. |
| `ecommerce.audit.quality_metrics` | Stores quality metric counters by run/source/metric. |
| `ecommerce.audit.quarantine_records` | Stores invalid and duplicate records with reason codes and raw payloads. |
| `ecommerce.audit.external_api_failures` | Tracks API failures and intentionally skipped API requests. |
| `ecommerce.audit.watermarks` | Stores incremental processing watermarks, especially for User SCD2. |
| `ecommerce.audit.validation_runs` | Stores validation outcomes and reconciliation evidence. |
| `ecommerce.audit.serving_builds` | Stores serving publication evidence and row-count summaries. |

---

## 11. Data Quality, Audit, and Reconciliation

The platform separates valid analytical records from rejected evidence.

```text
Raw input
   ↓
Validation + deduplication
   ↓
Valid records      → ecommerce.processed.* clean tables
Invalid records    → ecommerce.audit.quarantine_records
Duplicate records  → ecommerce.audit.quarantine_records
Counts and status  → ecommerce.audit.quality_metrics / pipeline_runs / validation_runs
```

The reconciliation principle is:

```text
Input = Accepted Clean + Rejected Quarantine + Duplicates
```

This rule is visible in validation evidence and in the audit screenshots. The quarantine table includes `source_name`, `reason_code`, `reason_description`, raw payload, Kafka topic, Kafka partition, Kafka offset, source record ID, stream batch ID, and quarantine timestamp. This makes the rejection explainable and traceable.

---

## 12. Serving Layer and Power BI

ClickHouse database:

```text
personalization_olap
```

Power BI reads only the `v_*` views.

| View | Purpose |
|---|---|
| `v_dim_date` | Date dimension for filtering and time analysis. |
| `v_dim_product` | Product dimension. |
| `v_dim_user_current` | Current user dimension for the latest active serving build. |
| `v_fact_clickstream_event` | Event-level clickstream fact. |
| `v_fact_order` | Order header fact. |
| `v_fact_order_item` | Order item fact. |
| `v_mart_journey_session` | Session-level journey and funnel mart. |
| `v_mart_navigation_paths` | Navigation transition/path mart. |
| `v_mart_product_performance_daily` | Product engagement and conversion mart. |
| `v_mart_web_experience_daily` | Web endpoint experience mart. |
| `v_mart_context_impact_daily` | Geo/weather/holiday context mart. |
| `v_mart_personalization_candidates` | Products/segments suitable for personalization analysis. |

Important serving rule:

```text
v_* views represent the latest ACTIVE serving build, not all historical serving builds.
```

The physical ClickHouse tables can contain rows for multiple serving builds. The `v_*` views filter those physical tables to the active build using `serving_control`.

---

## 13. Power BI Dashboard Overview

The Power BI report is stored in:

```text
powerBI/project_clickstream.pbix
```

The report has two main dashboard pages:

1. **Growth and Funnel Intelligence**  
   Focuses on sessions, checkout starts, checkout completions, revenue, conversion leakage, product performance, and journey behavior.

2. **Personalization and Context Intelligence**  
   Focuses on personalization candidates, product interest, country/city/device/context behavior, weather/holiday impact, and web experience indicators.

Power BI uses Import mode and connects to ClickHouse serving views only. This keeps the dashboard fast and avoids embedding data engineering logic directly into dashboard visuals.

---

## 14. Evidence Screenshots Guide

This section documents what each screenshot proves. These images are part of the project evidence package and should remain in the `screenshots/` directory.

| Screenshot | What it shows | Why it matters | What it proves |
|---|---|---|---|
| `screenshots/01_docker_compose_healthy.png` | Docker Compose service status. | Confirms the local platform can run as a complete multi-container system. | Core services are up and healthy. |
| `screenshots/02_main_status_healthy_1.png` | First part of `python main.py status`. | Shows the project-level health command works. | The CLI can summarize platform state. |
| `screenshots/02_main_status_healthy_2.png` | Second part of `python main.py status`. | Completes the runtime status evidence. | Health reporting covers more than container status. |
| `screenshots/03_kafka_topics.png` | Kafka UI topic list. | Demonstrates Kafka topic creation and Debezium internal topics. | Business topics and `debezium-connect-*` topics exist. |
| `screenshots/04_minio_warehouse_bucket_1.png` | MinIO bucket/warehouse view. | Shows the object store used by Iceberg. | The lakehouse warehouse exists on MinIO. |
| `screenshots/04_minio_warehouse_bucket_2.png` | Additional MinIO warehouse objects. | Shows persisted Iceberg object structure. | Lakehouse metadata/data objects are stored under the bucket. |
| `screenshots/04_minio_warehouse_bucket_3.png` | Additional MinIO warehouse detail. | Supports lakehouse storage evidence. | Iceberg storage is backed by MinIO objects. |
| `screenshots/05_spark_streaming_status.png` | Spark streaming status evidence. | Shows streaming ingestion is running and processing. | Spark Structured Streaming is active independently from Airflow. |
| `screenshots/06_airflow_or_refresh_jobs_passed_1.png` | Batch refresh job evidence. | Shows scheduled/triggered batch tasks passed. | Airflow/Spark batch sequence completed successfully. |
| `screenshots/06_airflow_or_refresh_jobs_passed_2.png` | Additional batch refresh evidence. | Completes the batch orchestration proof. | Validation and serving jobs are part of the refresh cycle. |
| `screenshots/07_validation_latest_passed_1.png` | Validation report status. | Shows lakehouse validation result. | The validation stage passed. |
| `screenshots/07_validation_latest_passed_2.png` | Validation report details. | Shows reconciliation and quality checks. | Raw, clean, quarantine, relationship, SCD2, and coverage checks are recorded. |
| `screenshots/08_serving_latest_passed.png` | Serving publication report. | Shows ClickHouse publication status. | A serving build was produced successfully. |
| `screenshots/09_clean_processed_table_counts.png` | Clean Iceberg processed table counts. | Shows valid records landed in clean tables. | Valid records are stored in `ecommerce.processed.*`. |
| `screenshots/10_quarantine_counts.png` | Quarantine counts by source and reason. | This is the primary rejected-record evidence. | Invalid and duplicate records are stored in `ecommerce.audit.quarantine_records`. |
| `screenshots/11_duplicate_record_samples.png` | Duplicate record samples. | Shows duplicates are traceable to Kafka metadata. | Duplicate records preserve topic, partition, offset, and reason code. |
| `screenshots/12_invalid_record_samples.png` | Invalid record samples. | Shows invalid records are preserved with rejection reasons. | Malformed/missing/unsupported records are not silently dropped. |
| `screenshots/13_quality_metrics_summary.png` | Quality metric totals. | Shows metrics by source and metric name. | Accepted, invalid, and duplicate counters are captured in audit. |
| `screenshots/14_clickhouse_row_counts.png` | ClickHouse serving row counts. | Confirms serving data exists after publication. | ClickHouse contains dashboard-ready dimensions, facts, and marts. |
| `screenshots/15_clickhouse_geo_weather_context_1.png` | Geo/weather context evidence. | Shows contextual enrichment is available in serving outputs. | Geo and weather context contribute to analytics. |
| `screenshots/15_clickhouse_geo_weather_context_2.png` | Additional context evidence. | Complements the first context screenshot. | Context fields are usable for downstream dashboard analysis. |
| `screenshots/16_powerbi_dashboard_growth_funnel.png` | Power BI growth/funnel dashboard page. | Shows the final business-facing dashboard. | The project produces a usable analytical report. |
| `screenshots/17_powerbi_dashboard_personalization.png` | Power BI personalization/context dashboard page. | Shows personalization-oriented analysis. | The report supports context and recommendation candidate analysis. |
| `screenshots/18_powerbi_data_model.png` | Power BI model view. | Shows selected ClickHouse views and relationships. | Power BI is modeled from serving views rather than raw source tables. |

---

## 15. Architecture and Data Flow Diagrams Guide

| Diagram | What it explains | Main components | Project decision represented |
|---|---|---|---|
| `diagrams/01_architecture_overview.png` | End-to-end platform architecture. | Sources, Kafka, Filebeat, Debezium, Spark, MinIO/Iceberg, Airflow, ClickHouse, Power BI, Operations Console. | The platform uses separate streaming, batch, lakehouse, serving, and dashboard layers. |
| `diagrams/02_data_flow.png` | Main data movement from sources to analytics. | Streaming sources, CDC sources, batch sources, clean tables, serving layer. | Data flows through controlled ingestion and Spark processing before serving. |
| `diagrams/02_data_flow_alternative.png` | Alternative visual layout of the data flow. | Same core flow with a different diagram arrangement. | Provides a secondary view if the first data flow is not used in slides. |
| `diagrams/03_lakehouse_zones.png` | Lakehouse storage and processing zones. | Raw, processed, audit, quarantine, serving. | Iceberg namespaces separate raw evidence, clean tables, and audit evidence. |
| `diagrams/04_cdc_scd2_flow.png` | PostgreSQL CDC and User SCD Type 2 flow. | PostgreSQL, Debezium, Kafka CDC topics, Spark CDC cleaning, `user_profile_scd2`. | CDC is captured continuously; User SCD2 is produced by batch. |
| `diagrams/05_clickhouse_olap_model.png` | ClickHouse OLAP model for Power BI. | Dimensions, facts, marts, `v_*` views. | Power BI reads dashboard-ready views only. |
| `diagrams/06_analytics_refresh_orchestration.png` | Airflow analytics refresh sequence. | `user_scd2`, `weather_enrichment`, `holiday_enrichment`, `validate_lakehouse`, `publish_serving`. | Serving publication only happens after validation passes. |
| `diagrams/07_data_quality_audit_reconciliation.png` | Data quality, quarantine, and reconciliation. | Accepted records, rejected records, duplicate records, audit metrics, validation evidence. | Invalid/duplicate records are preserved in audit instead of being silently dropped. |
| `diagrams/08_business_key_relationships.png` | Business key relationships across sources. | `request_id`, `user_id`, `checkout_id`, `order_id`, `product_id`, `ip_address`, context keys. | The analytical model depends on consistent business keys across heterogeneous sources. |
| `diagrams/09_bronze_silver_gold_flow.png` | Logical Bronze/Silver/Gold flow. | Sources, ingestion, Bronze raw, Spark processing, Silver clean, audit sidecar, Gold ClickHouse, Power BI. | Bronze/Silver/Gold are logical zones in the lakehouse/serving design. |

---

## 16. How to Run the Project

### 16.1 Prerequisites

- Docker and Docker Compose.
- At least 10 GB available Docker memory is recommended.
- Python environment for running the local CLI.
- A local `.env` file created from `.env.example`.
- A local MaxMind GeoLite2 City database file at:

```text
data/reference/GeoLite2-City.mmdb
```

The `.mmdb` file is licensed/local reference data and is intentionally not committed.

### 16.2 Prepare environment

```bash
cp .env.example .env
```

Edit `.env` and set secure values for PostgreSQL, MinIO, ClickHouse, and Calendarific.

### 16.3 Initialize the full platform

```bash
python main.py init
```

This command performs the first complete platform setup, including source generation, infrastructure startup, topic setup, lakehouse bootstrap, PostgreSQL seed loading, CDC connector creation, and initial analytics refresh steps.

### 16.4 Start an existing platform

```bash
python main.py start
```

This command starts the existing platform without deleting state.

### 16.5 Check platform status

```bash
python main.py status
```

This command prints service and evidence status.

### 16.6 Stop services without deleting data

```bash
python main.py stop
```

### 16.7 Reset dynamic state

```bash
python main.py reset --confirm
```

This command is destructive. It is used only when the dynamic platform state must be rebuilt.

---

## 17. Useful Validation Commands

### 17.1 Show audit and clean evidence together

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

### 17.2 Print only quarantine counts for screenshots

```bash
docker compose exec -T spark-engine bash -lc '
cd /opt/project
PYTHONPATH=/opt/project/spark_jobs \
spark-submit --master local[2] \
  --conf spark.ui.enabled=false \
  /opt/project/spark_jobs/inspect_audit_counts.py \
  2>/tmp/audit_spark_noise.log \
| awk "
index(\$0, \"2. QUARANTINE COUNTS BY SOURCE AND REASON\") {flag=1}
index(\$0, \"3. DUPLICATE RECORD SAMPLES\") {flag=0}
flag
"
'
```

### 17.3 Print only clean processed counts for screenshots

```bash
docker compose exec -T spark-engine bash -lc '
cd /opt/project
PYTHONPATH=/opt/project/spark_jobs \
spark-submit --master local[2] \
  --conf spark.ui.enabled=false \
  /opt/project/spark_jobs/inspect_audit_counts.py \
  2>/tmp/audit_spark_noise.log \
| awk "
index(\$0, \"1. CLEAN PROCESSED TABLE ROW COUNTS\") {flag=1}
index(\$0, \"2. QUARANTINE COUNTS BY SOURCE AND REASON\") {flag=0}
flag
"
'
```

---

## 18. Repository Structure

```text
clickstream-personalization-platform/
├── airflow/
│   └── dags/
│       └── analytics_refresh.py
├── clickhouse/
│   └── users.d/
│       └── operations-limits.xml
├── config/
│   ├── filebeat.yml
│   ├── settings.yaml
│   └── spark-defaults.conf
├── data/
│   ├── clickhouse/
│   ├── minio/
│   ├── reference/
│   │   └── product_catalog.csv
│   └── source/
├── diagrams/
├── docker/
│   ├── Dockerfile.airflow
│   ├── Dockerfile.observability
│   └── Dockerfile.spark
├── docs/
│   ├── 01_PROJECT_ARCHITECTURE.md
│   ├── 02_DATA_SOURCES_AND_CONTRACTS.md
│   ├── 03_PIPELINES_QUALITY_AND_LAKEHOUSE.md
│   ├── 04_SERVING_AND_DASHBOARDS.md
│   └── 05_OPERATIONS_VALIDATION_AND_LIMITATIONS.md
├── observability_ui/
├── powerBI/
│   └── project_clickstream.pbix
├── screenshots/
├── spark_jobs/
├── src/platform_core/
├── tests/
├── docker-compose.yml
├── main.py
├── README.md
└── requirements.txt
```

---

## 19. Documentation Index

| Document | Purpose |
|---|---|
| `docs/01_PROJECT_ARCHITECTURE.md` | Architecture, service roles, processing paths, and key design decisions. |
| `docs/02_DATA_SOURCES_AND_CONTRACTS.md` | Source-by-source contracts, keys, validation rules, and downstream usage. |
| `docs/03_PIPELINES_QUALITY_AND_LAKEHOUSE.md` | Streaming, CDC, batch jobs, Iceberg tables, audit, quarantine, watermarks, and reconciliation. |
| `docs/04_SERVING_AND_DASHBOARDS.md` | ClickHouse serving model, `v_*` views, Power BI model, and dashboard scenarios. |
| `docs/05_OPERATIONS_VALIDATION_AND_LIMITATIONS.md` | Runbook, validation commands, screenshots, known limitations, challenges, and GitHub cleanup. |

---

## 20. Known Limitations

- The platform is local Docker Compose infrastructure, not a managed cloud deployment.
- The dataset is deterministic and project-sized, not production-scale traffic.
- Open-Meteo historical archive requests intentionally skip current or future UTC timestamps.
- Power BI uses Import mode and requires refresh after ClickHouse serving publication.
- The Operations Console is read-only and is not designed to start, stop, or reset services.
- The project demonstrates controlled SCD2 for users only; it does not implement SCD2 for orders or products.
- Product Catalog is intentionally static and clean; it is not modeled as a product CDC stream.

---

## 21. Future Enhancements

Potential extensions include:

- Managed cloud deployment using managed Kafka, object storage, and data warehouse services.
- Automated CI checks that run source generation and contract validation in a disposable environment.
- Schema evolution demonstrations using Iceberg table evolution.
- A richer backfill workflow for weather and holiday enrichment.
- Expanded personalization scoring using machine learning features.
- Additional dashboard drill-through pages for segment, product, and journey analysis.
- Alerting integration for validation failures or serving freshness issues.
