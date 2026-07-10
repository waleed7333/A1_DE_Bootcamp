
# Project Architecture

## 1. Purpose

This document describes the architecture of the Clickstream Personalization Platform. It focuses on the system design, processing layers, core services, and runtime modes.

Detailed source contracts are documented in:

```text
docs/02_DATA_SOURCES_AND_CONTRACTS.md
```

Detailed data quality, Iceberg table layout, and pipeline processing are documented in:

```text
docs/03_PIPELINES_QUALITY_AND_LAKEHOUSE.md
```

Serving and dashboard design are documented in:

```text
docs/04_SERVING_AND_DASHBOARDS.md
```

---

## 2. Business Objective

The platform is designed to support e-commerce personalization and conversion analysis by integrating:

* User website behavior.
* Server-side request performance.
* Customer profile changes.
* Order and order item transactions.
* Product catalog attributes.
* Geo-location context.
* Weather and holiday context.

The analytical objective is to provide a reliable foundation for:

* Funnel leakage analysis.
* Journey and navigation analysis.
* Product engagement and conversion analysis.
* Revenue and order analysis.
* Personalization candidate discovery.
* Context-aware segmentation.
* Operational data quality monitoring.

---

## 3. Architecture Principles

The implementation follows these principles:

| Principle                      | Implementation                                                                                                                                   |
| ------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| Streaming and batch separation | Spark Structured Streaming handles continuous ingestion; Airflow-triggered Spark batch handles SCD2, enrichment, validation, and serving publish |
| Source contract preservation   | Each source has a defined format, topic, keys, and validation rules                                                                              |
| Lakehouse-first storage        | Clean processed data is stored in Apache Iceberg on MinIO                                                                                        |
| Explicit quality handling      | Invalid and duplicate records are tracked through audit and quarantine structures                                                                |
| Read-optimized serving         | ClickHouse provides OLAP tables and views for Power BI                                                                                           |
| Dashboard isolation            | Power BI reads ClickHouse serving views only                                                                                                     |
| Local reproducibility          | Docker Compose runs the full platform locally                                                                                                    |
| Minimal unsafe controls        | The monitoring interface is read-only and does not execute destructive actions                                                                   |

---

## 4. High-Level Architecture

The platform consists of the following layers:

```text
Data Sources
    ↓
Ingestion Layer
    ↓
Spark Processing Layer
    ↓
Iceberg Lakehouse on MinIO
    ↓
ClickHouse Serving Layer
    ↓
Power BI Dashboard
```

Airflow orchestrates scheduled batch jobs. Streamlit provides a read-only Operations Console.

---

## 5. Architecture Diagram

Recommended diagram path:

```text
diagrams/01_architecture_overview.png
```

The architecture diagram should include:

* Clickstream Events.
* Web Server Logs.
* Product Catalog.
* PostgreSQL Users, Orders, and Order Items.
* Debezium Connect.
* Filebeat.
* Kafka cluster.
* Spark Engine.
* MinIO and Apache Iceberg.
* Airflow.
* Open-Meteo API.
* Calendarific API.
* GeoLite2 database.
* ClickHouse.
* Power BI.
* Operations Console.

---

## 6. Core Services

| Service                      | Purpose                                            |
| ---------------------------- | -------------------------------------------------- |
| PostgreSQL                   | Source database for Users, Orders, and Order Items |
| ZooKeeper                    | Kafka coordination                                 |
| Kafka brokers                | Streaming ingestion backbone                       |
| Kafka UI                     | Kafka topic inspection                             |
| Debezium Connect             | PostgreSQL CDC capture                             |
| Filebeat                     | Web log shipping into Kafka                        |
| Spark Engine                 | Streaming and batch processing                     |
| MinIO                        | S3-compatible lakehouse object storage             |
| Apache Iceberg               | Lakehouse table format                             |
| Airflow                      | Scheduled batch orchestration                      |
| ClickHouse                   | OLAP serving database                              |
| Power BI                     | Business dashboard                                 |
| Streamlit Operations Console | Read-only monitoring interface                     |

---

## 7. Ingestion Layer

The ingestion layer accepts three main ingestion styles:

### 7.1 Kafka streaming ingestion

Used for:

* Clickstream Events.
* Web Server Logs.
* Debezium CDC events.

Kafka topics:

```text
clickstream-events
webserver-logs
users-cdc
orders-cdc
order-items-cdc
```

Debezium internal topics:

```text
debezium-connect-configs
debezium-connect-offsets
debezium-connect-status
```

### 7.2 Filebeat log ingestion

Web server logs are generated as structured `.log` NDJSON files and shipped through Filebeat into Kafka topic:

```text
webserver-logs
```

### 7.3 Batch source ingestion

Product Catalog is loaded as a static CSV snapshot into Iceberg.

External APIs are queried through scheduled batch jobs.

---

## 8. Processing Layer

The platform uses one Spark Engine container for both streaming and batch workloads.

### 8.1 Spark Structured Streaming

Spark Structured Streaming consumes Kafka topics and writes:

* Raw Kafka payloads.
* Clean processed records.
* Quarantine and audit evidence.

Streaming sources:

```text
clickstream-events
webserver-logs
users-cdc
orders-cdc
order-items-cdc
```

### 8.2 Spark Batch Jobs

Spark batch jobs are orchestrated by Airflow or project orchestration commands.

Main batch jobs:

```text
user_scd2
weather_enrichment
holiday_enrichment
validate_lakehouse
publish_serving
```

---

## 9. Lakehouse Storage Layer

The lakehouse uses:

```text
MinIO + Apache Iceberg
```

The warehouse path is:

```text
s3://ecommerce-lakehouse/warehouse/
```

The lakehouse stores:

* Raw Kafka messages.
* Processed clean tables.
* User SCD Type 2 table.
* Weather and holiday enrichment tables.
* Audit and validation tables.
* Quarantine records.

---

## 10. Serving Layer

ClickHouse is used as the analytical serving layer.

Database:

```text
personalization_olap
```

Serving data is generated by:

```text
publish_serving
```

Power BI reads only ClickHouse `v_*` views in Import mode.

---

## 11. Monitoring Layer

The project includes a Streamlit-based Operations Console.

The console is used to monitor:

* Platform health.
* Streaming state.
* CDC status.
* SCD2 quality.
* Data quality and quarantine.
* Lakehouse validation.
* ClickHouse serving status.
* Alerts and suggested actions.

The Operations Console is separate from the Power BI business dashboard.

---

## 12. Runtime Modes

The project supports the following operational modes:

| Mode             | Purpose                                                       |
| ---------------- | ------------------------------------------------------------- |
| Live Mode        | Runs the full platform with live ingestion and processing     |
| Serving Mode     | Keeps serving and dashboard components available for analysis |
| Maintenance Mode | Used when stopping services or cleaning dynamic state         |

---

## 13. End-to-End Data Movement

The main end-to-end movement is:

```text
Clickstream / Logs / CDC
    → Kafka
    → Spark Structured Streaming
    → Iceberg clean tables
    → Batch validation and enrichment
    → ClickHouse serving tables
    → Power BI dashboards
```

Product Catalog follows a static batch load path:

```text
Product Catalog CSV
    → Spark Batch
    → Iceberg product_catalog_clean
    → ClickHouse product dimension and marts
```

Weather and holiday enrichment follow scheduled batch paths:

```text
clickstream_clean context keys
    → External API enrichment
    → Iceberg enrichment tables
    → ClickHouse contextual marts
```

---

## 14. Architecture Boundaries

The implementation intentionally keeps the following boundaries:

* Product Catalog is not a CDC source.
* SCD Type 2 applies only to User Profile.
* Orders and Order Items are modeled as CDC-derived facts and transaction records, not SCD2 dimensions.
* Power BI does not read Iceberg directly.
* ClickHouse is refreshed through `publish_serving`, not automatically after every streaming micro-batch.
* The Operations Console is read-only.

---