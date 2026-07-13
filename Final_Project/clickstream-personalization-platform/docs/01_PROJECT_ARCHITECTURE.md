# Project Architecture

## 1. Purpose

This document defines the final architecture of the Clickstream Personalization Platform. It describes the service layout, processing paths, runtime boundaries, architectural decisions, and operational responsibilities of the platform components.

The architecture is designed to satisfy a complete data engineering workflow: heterogeneous source ingestion, streaming processing, scheduled batch processing, governed lakehouse storage, quality/audit evidence, serving publication, dashboard consumption, and operational monitoring.

---

## 2. Business and Analytical Objective

The platform supports e-commerce clickstream personalization and conversion intelligence. It combines user behavior, website request performance, product metadata, user profile changes, order transactions, order line items, GeoIP context, weather context, and holiday context into a single governed analytical platform.

The architecture is intended to support these analytical outcomes:

- Funnel leakage analysis from product view to add-to-cart to checkout start to checkout completion.
- Journey and navigation analysis across sessions and page transitions.
- Product engagement and conversion analysis.
- Revenue and order analysis from transactional CDC sources.
- Web experience analysis using HTTP status codes, endpoints, and response times.
- Geographic analysis using GeoLite2 enrichment.
- Context analysis using historical weather and holiday enrichment.
- Personalization candidate discovery for products or segments with high interest and lower conversion.

---

## 3. Architecture Principles

| Principle | Implementation |
|---|---|
| Streaming and batch separation | Spark Structured Streaming processes Kafka topics continuously. Airflow triggers only scheduled Spark batch jobs. |
| Lakehouse-first design | Raw, processed, and audit data are stored in Apache Iceberg tables on MinIO. |
| Traceability | Raw Kafka payloads are preserved in `ecommerce.raw.kafka_messages` with topic, partition, offset, timestamp, and batch metadata. |
| Explicit quality routing | Valid records go to `ecommerce.processed.*`; invalid and duplicate records go to `ecommerce.audit.quarantine_records`. |
| CDC preservation | Debezium CDC metadata such as operation type, before image, after image, source LSN, source timestamp, and Kafka metadata is preserved in clean CDC tables. |
| Controlled SCD2 | User Profile SCD Type 2 is built by a Spark batch job from cleaned user CDC events. |
| Serving isolation | ClickHouse receives validated, dashboard-ready dimensions, facts, and marts. Power BI reads ClickHouse `v_*` views only. |
| Operational evidence | Pipeline runs, quality metrics, validation runs, serving builds, watermarks, and API failures are stored for proof and troubleshooting. |
| Local reproducibility | Docker Compose runs the full platform locally with explicit service definitions and resource limits. |
| Read-only monitoring | The Streamlit Operations Console reads evidence and status; it does not perform destructive operations. |

---

## 4. High-Level Architecture

The platform is organized into the following layers:

```text
Sources
  ↓
Ingestion
  ↓
Spark Processing
  ↓
Apache Iceberg Lakehouse on MinIO
  ↓
Validation and Serving Publication
  ↓
ClickHouse OLAP Serving Layer
  ↓
Power BI Dashboard
```

The platform contains two major compute paths:

1. **Continuous streaming path** for clickstream, web logs, and PostgreSQL CDC.
2. **Scheduled batch path** for User SCD2, weather enrichment, holiday enrichment, lakehouse validation, and ClickHouse serving publication.

---

## 5. Core Services

| Service | Container / component | Architectural responsibility |
|---|---|---|
| PostgreSQL | `clickstream-postgres` | Source database for users, orders, and order items; logical replication source for Debezium; JDBC catalog backend for Iceberg metadata. |
| ZooKeeper | `clickstream-zookeeper` | Coordination service for the Confluent Kafka 7.3.2 cluster. |
| Kafka brokers | `clickstream-kafka1`, `clickstream-kafka2`, `clickstream-kafka3` | Distributed streaming backbone with three brokers, replication factor 3, partitions 3, and min ISR 2. |
| Kafka UI | `clickstream-kafka-ui` | Topic and partition inspection UI for validation evidence. |
| Debezium Connect | `clickstream-debezium-connect` | Captures PostgreSQL snapshots and CDC changes into Kafka topics. |
| MinIO | `clickstream-minio` | S3-compatible object store for the Iceberg warehouse bucket. |
| Filebeat | `clickstream-filebeat` | Tails structured `.log` web logs and publishes them to Kafka. |
| Spark Engine | `clickstream-spark-engine` | Single Spark container for Structured Streaming and all Spark batch jobs. |
| Airflow | `clickstream-airflow` | Schedules and monitors the batch refresh DAG. |
| ClickHouse | `clickstream-clickhouse` | OLAP serving layer for Power BI. |
| Observability UI | `clickstream-observability-ui` | Read-only Streamlit console for platform status and evidence. |
| Power BI | `powerBI/project_clickstream.pbix` | Final dashboard and semantic visualization layer. |

---

## 6. Source Layer

The source layer contains multiple heterogeneous source types:

- Clickstream JSONL events.
- Web server structured `.log` records.
- Static product catalog CSV.
- PostgreSQL `users`, `orders`, and `order_items` tables.
- MaxMind GeoLite2 City local reference database.
- Open-Meteo Historical Weather API.
- Calendarific Holiday API.

The sources are intentionally varied to demonstrate different ingestion patterns: direct Kafka publishing, log shipping, static batch loading, CDC capture, local reference lookup, and scheduled API pulls.

---

## 7. Ingestion Layer

### 7.1 Clickstream ingestion

Clickstream events are generated into a JSONL source file and published directly to Kafka topic `clickstream-events`. This path represents application event publishing. It does not use Filebeat because clickstream records are application events rather than log records.

### 7.2 Web log ingestion

Web server records are generated as structured `.log` lines under `data/source/web_logs/webserver_access.log`. Filebeat tails this file and publishes records to Kafka topic `webserver-logs`. This path represents realistic infrastructure log shipping.

### 7.3 CDC ingestion

PostgreSQL tables are seeded first and then captured by Debezium Connect. Debezium writes CDC events into Kafka topics:

```text
users-cdc
orders-cdc
order-items-cdc
```

CDC messages include operation type and source metadata needed for downstream processing.

### 7.4 Static reference ingestion

Product Catalog is loaded once from `data/reference/product_catalog.csv` into the clean Iceberg table `ecommerce.processed.product_catalog_clean`. It is static by design and is not represented as a CDC stream.

### 7.5 External context ingestion

Open-Meteo and Calendarific are not streamed. They are pulled by scheduled Spark batch jobs after clean clickstream data provides the required geographic, date, and hour keys.

---

## 8. Spark Processing Layer

Spark is the only data processing engine in the project.

### 8.1 Spark Structured Streaming responsibilities

Spark Structured Streaming continuously consumes Kafka topics and performs:

- JSON parsing.
- Contract version validation.
- Required-key validation.
- Event-type validation.
- Product-event validation.
- Checkout-event validation.
- CDC payload validation.
- Deduplication.
- Kafka metadata preservation.
- Raw payload persistence.
- GeoIP enrichment from the local GeoLite2 database.
- Late-arrival flagging.
- Quarantine routing.
- Clean Iceberg table writes.

### 8.2 Spark Batch responsibilities

Spark batch jobs perform:

- Product Catalog bootstrap.
- User SCD Type 2 construction.
- Weather enrichment.
- Holiday enrichment.
- Lakehouse validation.
- ClickHouse serving publication.
- Audit/evidence output generation.

---

## 9. Lakehouse Layer

The lakehouse is implemented using Apache Iceberg on top of MinIO object storage.

Iceberg catalog name:

```text
ecommerce
```

MinIO bucket:

```text
ecommerce-lakehouse
```

Warehouse path:

```text
s3://ecommerce-lakehouse/warehouse
```

The lakehouse is organized into three namespaces:

| Namespace | Purpose |
|---|---|
| `ecommerce.raw` | Raw Kafka payload preservation. |
| `ecommerce.processed` | Clean, structured, enriched data. |
| `ecommerce.audit` | Quality, quarantine, validation, serving, API, and watermark evidence. |

---

## 10. Airflow Scope

Airflow orchestrates only scheduled batch processing. It does not run or control Spark Structured Streaming.

Airflow DAG:

```text
analytics_refresh
```

Batch sequence:

```text
user_scd2
  ↓
weather_enrichment
  ↓
holiday_enrichment
  ↓
validate_lakehouse
  ↓
publish_serving
```

This separation prevents the common architecture mistake of treating Airflow as the controller for all Spark workloads. The streaming job is a continuously running ingestion process; Airflow is used for scheduled analytics refresh tasks.

---

## 11. Serving Layer

ClickHouse is the OLAP serving layer. It stores dashboard-ready physical tables and exposes `v_*` views for Power BI.

The serving publication job reads validated Iceberg tables, builds dimensions, facts, and marts, writes them into ClickHouse, and registers the active serving build.

Power BI does not read directly from Kafka, PostgreSQL, MinIO, Iceberg raw tables, or audit tables. It reads ClickHouse `v_*` views only.

---

## 12. Operations Layer

The Operations Console is a Streamlit application. It provides read-only visibility into:

- Service health.
- Runtime evidence.
- Report files.
- ClickHouse serving status.
- Kafka and ingestion status.
- Batch and validation status.
- Quality and quarantine evidence.

It is intentionally read-only and does not reset, stop, or mutate infrastructure.

---

## 13. Runtime Modes

The project supports practical runtime modes through `main.py` commands:

| Command | Purpose |
|---|---|
| `python main.py init` | Build the platform from a clean state and run the initial setup sequence. |
| `python main.py start` | Start an existing platform without deleting data. |
| `python main.py status` | Print health and evidence status. |
| `python main.py stop` | Stop containers without deleting dynamic data. |
| `python main.py reset --confirm` | Delete dynamic state and rebuild when explicitly confirmed. |

The CLI deliberately exposes a small set of normal operator commands. Internal Spark jobs are not intended to be the primary user-facing CLI.

---

## 14. Architecture Diagrams

The primary diagrams are stored under `diagrams/`:

| Diagram | Purpose |
|---|---|
| `diagrams/01_architecture_overview.png` | Complete end-to-end platform overview. |
| `diagrams/02_data_flow.png` | Main data flow through streaming, CDC, batch, lakehouse, serving, and Power BI. |
| `diagrams/03_lakehouse_zones.png` | Raw, processed, audit, quarantine, and serving zones. |
| `diagrams/04_cdc_scd2_flow.png` | PostgreSQL CDC and User SCD2 processing. |
| `diagrams/05_clickhouse_olap_model.png` | ClickHouse dimensional, fact, and mart model. |
| `diagrams/06_analytics_refresh_orchestration.png` | Airflow batch refresh sequence. |
| `diagrams/07_data_quality_audit_reconciliation.png` | Validation, quarantine, metrics, and reconciliation flow. |
| `diagrams/08_business_key_relationships.png` | Business key relationships across sources. |
| `diagrams/09_bronze_silver_gold_flow.png` | Logical Bronze/Silver/Gold data flow. |

The README provides a more detailed explanation of what each diagram shows and what project decision it represents.

---

## 15. Key Architecture Decisions

| Decision | Reason |
|---|---|
| Use Kafka for streaming input | Provides topic-based decoupling, partitions, offsets, replay ability, and CDC integration. |
| Use three Kafka brokers | Demonstrates replicated streaming infrastructure rather than a single local broker. |
| Use Filebeat for web logs | Represents realistic log shipping and separates web logs from application clickstream events. |
| Use Debezium for CDC | Provides reliable change capture with before/after images and LSN metadata. |
| Use one Spark container | Reduces local resource usage while still demonstrating Spark Structured Streaming and Spark batch jobs. |
| Use Iceberg on MinIO | Provides lakehouse table management on object storage with a local S3-compatible environment. |
| Use Airflow only for batch | Keeps streaming independent and uses orchestration where scheduled sequencing is useful. |
| Use ClickHouse for serving | Provides fast OLAP queries and keeps Power BI away from raw lakehouse logic. |
| Use `v_*` ClickHouse views | Ensures Power BI reads only the latest active serving build. |
| Use audit/quarantine tables | Makes data quality handling explicit and provable. |

---

## 16. Architecture Risks and Controls

| Risk | Control |
|---|---|
| Local machine memory pressure | Low-memory service limits, one Spark container, Airflow parallelism set to one, recommended Docker memory documented. |
| Dirty or malformed source records | Validation rules and quarantine records with reason codes. |
| Duplicate source records | Deduplication and duplicate quarantine routing. |
| CDC state ambiguity | Debezium metadata and SCD2 watermarks preserve ordering evidence. |
| External API current-day gaps | Open-Meteo current/future timestamps are intentionally skipped and recorded in `external_api_failures` with status `SKIPPED`. |
| Serving stale data | ClickHouse serving builds and validation reports show which validated snapshot was published. |
| Dashboard reading the wrong layer | Power BI is documented and modeled to use ClickHouse `v_*` views only. |
