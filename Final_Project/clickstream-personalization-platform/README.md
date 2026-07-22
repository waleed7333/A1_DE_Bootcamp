# Clickstream Personalization Platform

<p align="center">
  <strong>End-to-end data engineering platform for clickstream analytics, user journey intelligence, personalization signals, and Power BI decision reporting.</strong>
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white">
  <img alt="Docker Compose" src="https://img.shields.io/badge/Docker%20Compose-Orchestration-2496ED?style=for-the-badge&logo=docker&logoColor=white">
  <img alt="Apache Kafka" src="https://img.shields.io/badge/Apache%20Kafka-Streaming-231F20?style=for-the-badge&logo=apachekafka&logoColor=white">
  <img alt="Apache Spark" src="https://img.shields.io/badge/Apache%20Spark-3.5-FDEE21?style=for-the-badge&logo=apachespark&logoColor=black">
  <img alt="Apache Iceberg" src="https://img.shields.io/badge/Apache%20Iceberg-Lakehouse-4B8BBE?style=for-the-badge">
</p>

<p align="center">
  <img alt="Apache Airflow" src="https://img.shields.io/badge/Apache%20Airflow-Orchestration-017CEE?style=for-the-badge&logo=apacheairflow&logoColor=white">
  <img alt="ClickHouse" src="https://img.shields.io/badge/ClickHouse-OLAP%20Serving-FFCC01?style=for-the-badge&logo=clickhouse&logoColor=black">
  <img alt="Power BI" src="https://img.shields.io/badge/Power%20BI-Dashboard-F2C811?style=for-the-badge&logo=powerbi&logoColor=black">
  <img alt="Ruff" src="https://img.shields.io/badge/Ruff-Linting-261230?style=for-the-badge">
  <img alt="Pytest" src="https://img.shields.io/badge/Pytest-Validated-0A9EDC?style=for-the-badge&logo=pytest&logoColor=white">
</p>

---

## Overview

**Clickstream Personalization Platform** is a complete local data engineering platform for collecting, processing, validating, enriching, serving, and visualizing e-commerce behavioral data.

The platform combines real-time clickstream activity, structured web server logs, transactional PostgreSQL data, Debezium CDC streams, product reference data, GeoIP enrichment, weather context, and holiday context into an Apache Iceberg lakehouse. Curated analytical data is then published to ClickHouse and consumed by Power BI through a stable set of serving views.

The project is organized as a production-style data platform with clear separation between ingestion, streaming processing, scheduled batch jobs, lakehouse storage, serving publication, validation, observability, and dashboard consumption.

---

## Table of Contents

- [Platform Snapshot](#platform-snapshot)
- [Business Purpose](#business-purpose)
- [Architecture](#architecture)
- [Core Capabilities](#core-capabilities)
- [Data Sources](#data-sources)
- [Processing Model](#processing-model)
- [Lakehouse Design](#lakehouse-design)
- [Serving Layer](#serving-layer)
- [Power BI Dashboard](#power-bi-dashboard)
- [Operations Console](#operations-console)
- [Validation and Evidence](#validation-and-evidence)
- [Technology Stack](#technology-stack)
- [Repository Structure](#repository-structure)
- [Run the Platform](#run-the-platform)
- [Developer Quality Checks](#developer-quality-checks)
- [Documentation](#documentation)

---

## Platform Snapshot

| Area | Implementation |
|---|---|
| Ingestion | Kafka, Filebeat, Debezium CDC, scheduled API pulls |
| Streaming | Spark Structured Streaming over Kafka topics |
| Batch Processing | Airflow-triggered Spark jobs |
| Lakehouse | Apache Iceberg tables on MinIO object storage |
| Audit and Quality | Quarantine records, quality metrics, validation runs, serving build evidence |
| Serving | ClickHouse database `personalization_olap` |
| Dashboard | Power BI Import model over ClickHouse `v_*` views |
| Operations | Streamlit Operations Console |
| Project Control | `main.py` command-line workflow |
| Code Quality | Black, Ruff, Pytest |

---

## Business Purpose

E-commerce platforms need more than order totals. They need to understand how users arrive, browse, search, view products, add items to cart, reach checkout, abandon sessions, complete purchases, and respond to contextual signals.

This platform supports analytical scenarios such as:

- User journey and session behavior analysis.
- Funnel progression from product interest to purchase.
- Product engagement and revenue performance.
- Web experience analysis using access logs and response metrics.
- Personalization candidate discovery based on behavioral signals.
- Geo, weather, and holiday context analysis.
- Validation of accepted, rejected, duplicated, and quarantined records.
- Versioned serving builds for consistent dashboard refreshes.

The final dashboard is built on curated serving views rather than raw files or internal tables, keeping the reporting layer clean and governed.

---

## Architecture

![Architecture Overview](diagrams/01_architecture_overview.png)

The platform separates source generation, ingestion, processing, storage, orchestration, serving, and reporting into independent layers. Streaming workloads continuously process Kafka topics into Iceberg, while scheduled batch workloads enrich, validate, and publish analytical outputs to ClickHouse.

```text
Sources
  ↓
Kafka / Debezium / Filebeat / Batch APIs
  ↓
Spark Structured Streaming + Spark Batch
  ↓
Apache Iceberg on MinIO
  ↓
ClickHouse Serving Layer
  ↓
Power BI Dashboard
````

---

## Core Capabilities

| Capability             | Description                                                                                        |
| ---------------------- | -------------------------------------------------------------------------------------------------- |
| Multi-source ingestion | Integrates behavioral events, web logs, CDC streams, reference data, GeoIP, weather, and holidays. |
| Real-time processing   | Spark Structured Streaming reads Kafka topics and writes raw, clean, and audit data into Iceberg.  |
| CDC handling           | Debezium captures PostgreSQL changes for users, orders, and order items.                           |
| SCD Type 2             | User profile history is maintained using Spark batch processing over clean CDC events.             |
| Lakehouse storage      | Iceberg organizes raw, processed, and audit data with partitioned Parquet storage.                 |
| Data quality           | Invalid and duplicate records are tracked through quarantine and quality metrics.                  |
| External enrichment    | Weather and holiday context is added through scheduled Spark batch jobs.                           |
| Serving publication    | ClickHouse stores dimensions, facts, marts, and latest-active serving views.                       |
| BI consumption         | Power BI reads curated ClickHouse `v_*` views in Import mode.                                      |
| Operations evidence    | Health, validation, serving, and pipeline evidence is surfaced through CLI reports and Streamlit.  |

---

## Data Sources

The project integrates heterogeneous sources that represent a realistic e-commerce data environment.

| Source             | Format / System                | Ingestion Method                                    | Purpose                                                                                                                        |
| ------------------ | ------------------------------ | --------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| Clickstream Events | JSONL                          | Local publisher to Kafka topic `clickstream-events` | Website behavioral events such as page views, product views, cart actions, checkout events, search, scroll, login, and logout. |
| Web Server Logs    | `.log` JSON lines              | Filebeat to Kafka topic `webserver-logs`            | Request-level web experience data including paths, methods, status codes, latency, user agent, and request correlation.        |
| Product Catalog    | CSV                            | Spark batch load                                    | Static product reference data used for product, category, price, and inventory context.                                        |
| Users              | PostgreSQL table               | Debezium CDC topic `users-cdc`                      | User profile changes and account attributes.                                                                                   |
| Orders             | PostgreSQL table               | Debezium CDC topic `orders-cdc`                     | Order-level transactional records.                                                                                             |
| Order Items        | PostgreSQL table               | Debezium CDC topic `order-items-cdc`                | Line-item level product sales records.                                                                                         |
| GeoIP              | MaxMind GeoLite2 City database | Local Spark enrichment                              | Country, city, coordinates, and timezone enrichment from IP addresses.                                                         |
| Weather            | Open-Meteo historical API      | Airflow-triggered Spark batch                       | Weather context by location and hour.                                                                                          |
| Holidays           | Calendarific API               | Airflow-triggered Spark batch                       | Holiday context by country and year.                                                                                           |

Key analytical relationships are maintained through identifiers such as:

```text
event_id
request_id
session_id
visitor_id
user_id
checkout_id
order_id
product_id
event_timestamp
```

---

## Processing Model

The platform has two coordinated processing paths.

### Continuous Streaming Path

```text
Clickstream publisher
Web log shipper
Debezium CDC topics
        ↓
Kafka
        ↓
Spark Structured Streaming
        ↓
Iceberg raw, processed, quarantine, and audit tables
```

The streaming path handles:

* Kafka topic reads.
* Raw message preservation.
* Clickstream validation.
* Web log validation.
* CDC event cleaning.
* GeoIP enrichment.
* Deduplication.
* Quarantine routing.
* Quality metric updates.
* Watermark and run evidence.

### Scheduled Batch Path

```text
Iceberg processed tables
        ↓
Airflow DAG analytics_refresh
        ↓
Spark batch jobs
        ↓
SCD2, context enrichment, validation, and serving publication
        ↓
ClickHouse serving views
```

The batch path handles:

* User SCD Type 2 processing.
* Weather enrichment.
* Holiday enrichment.
* Lakehouse validation.
* ClickHouse serving publication.
* Serving build evidence.

---

## Lakehouse Design

Apache Iceberg is used as the managed lakehouse table layer on top of MinIO object storage.

The Iceberg catalog is organized into three namespaces:

| Namespace             | Purpose                                                                                                               |
| --------------------- | --------------------------------------------------------------------------------------------------------------------- |
| `ecommerce.raw`       | Raw Kafka payload preservation.                                                                                       |
| `ecommerce.processed` | Validated, deduplicated, enriched, and structured analytical tables.                                                  |
| `ecommerce.audit`     | Pipeline evidence, quality metrics, validation results, quarantine records, failures, watermarks, and serving builds. |

### Iceberg Tables

| Layer     | Tables                                                                                                                                                                                       |
| --------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Raw       | `raw.kafka_messages`                                                                                                                                                                         |
| Processed | `product_catalog_clean`, `clickstream_clean`, `webserver_logs_clean`, `users_cdc_clean`, `orders_cdc_clean`, `order_items_cdc_clean`, `user_profile_scd2`, `weather_clean`, `holidays_clean` |
| Audit     | `pipeline_runs`, `quality_metrics`, `external_api_failures`, `validation_runs`, `serving_builds`, `watermarks`, `quarantine_records`                                                         |

The lakehouse stores clean analytical data while preserving operational evidence required to validate the pipeline.

---

## Serving Layer

ClickHouse is the serving database for Power BI and analytical consumption.

```text
Database: personalization_olap
```

The serving layer publishes physical dimensions, facts, and marts, then exposes stable `v_*` views for the latest active serving build.

Power BI reads the serving views only. Raw, processed, audit, and internal tables are intentionally kept outside the report model.

### Power BI Serving Views

| Category                          | Views                                                              |
| --------------------------------- | ------------------------------------------------------------------ |
| Dimensions                        | `v_dim_date`, `v_dim_product`, `v_dim_user_current`                |
| Facts                             | `v_fact_clickstream_event`, `v_fact_order`, `v_fact_order_item`    |
| Session and Journey Marts         | `v_mart_journey_session`, `v_mart_navigation_paths`                |
| Product and Experience Marts      | `v_mart_product_performance_daily`, `v_mart_web_experience_daily`  |
| Context and Personalization Marts | `v_mart_context_impact_daily`, `v_mart_personalization_candidates` |

The serving contract is intentionally limited to the twelve curated views above. Dashboard-specific calculations are handled inside the Power BI semantic model.

---

## Power BI Dashboard

Power BI consumes ClickHouse serving views in Import mode.

```text
power_BI_dashboard/project_clickstream.pbix
```

The report presents executive, revenue, journey, funnel, personalization, and context analytics through a clean business-facing model built on the curated serving layer.

### Dashboard Pages

| Page                      | Purpose                                                               | Preview                                                                                       |
| ------------------------- | --------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| Executive Overview        | High-level business, engagement, and performance summary.             | ![Executive Overview](screenshots/16_powerbi_dashboard_Executive_Overview.png)                |
| Growth & Revenue          | Revenue, orders, product performance, and growth-oriented analysis.   | ![Growth and Revenue](screenshots/17_powerbi_dashboard_Growth&Revenue.png)                   |
| Funnel & Journey          | Funnel leakage, session progression, and navigation behavior.         | ![Funnel and Journey](screenshots/18_powerbi_dashboard_Funnel&Journey.png)                   |
| Personalization & Context | Personalization candidates, context signals, and behavior enrichment. | ![Personalization and Context](screenshots/19_powerbi_dashboard_Personalization&Context.png) |

### Power BI Model

![Power BI Data Model](screenshots/20_powerbi_data_model.png)

The Power BI model keeps analytical logic close to the report while preserving ClickHouse as the clean serving contract. Measures, ratios, funnel calculations, and presentation-level calculations are implemented in Power BI.

---

## Operations Console

The project includes a Streamlit Operations Console for read-only operational visibility.

The console summarizes:

* Docker service health.
* Kafka and CDC status.
* Spark streaming state.
* Lakehouse table evidence.
* Data quality checks.
* SCD Type 2 status.
* Batch enrichment status.
* ClickHouse serving readiness.
* Power BI serving view availability.

```text
observability_ui/
```

The console is designed as an operational evidence layer, not as a control plane. It surfaces the current state of the platform without modifying project data.

---

## Validation and Evidence

The platform records validation and serving evidence as part of the normal run lifecycle.

| Evidence Area         | Output                                   |
| --------------------- | ---------------------------------------- |
| Platform health       | `python main.py status`                  |
| Latest validation     | `reports/validation_latest.json`         |
| Latest serving build  | `reports/serving_latest.json`            |
| Runtime observability | `runtime/observability/latest.json`      |
| Quality metrics       | Iceberg audit table `quality_metrics`    |
| Quarantine evidence   | Iceberg audit table `quarantine_records` |
| Serving build history | Iceberg audit table `serving_builds`     |

The serving publication validates the stable Power BI view contract and verifies that the expected twelve ClickHouse views are available for reporting.

---

## Technology Stack

| Technology       | Role                                                                                |
| ---------------- | ----------------------------------------------------------------------------------- |
| Python 3.12      | CLI workflow, local orchestration helpers, source generation, validation utilities. |
| Docker Compose   | Local multi-service runtime.                                                        |
| PostgreSQL 16    | Relational source system and Iceberg JDBC catalog backend.                          |
| Apache Kafka     | Streaming backbone for clickstream, web logs, and CDC topics.                       |
| Debezium Connect | PostgreSQL CDC capture into Kafka.                                                  |
| Filebeat         | Web server log shipping into Kafka.                                                 |
| Apache Spark 3.5 | Structured Streaming and scheduled batch processing.                                |
| Apache Iceberg   | Lakehouse table format.                                                             |
| MinIO            | S3-compatible local object storage for the Iceberg warehouse.                       |
| Apache Airflow   | Batch orchestration for analytical refresh jobs.                                    |
| ClickHouse       | OLAP serving database for dashboard-ready data.                                     |
| Power BI         | Business intelligence dashboard and semantic model.                                 |
| Streamlit        | Read-only operations console.                                                       |
| MaxMind GeoLite2 | GeoIP enrichment.                                                                   |
| Open-Meteo       | Weather context enrichment.                                                         |
| Calendarific     | Holiday context enrichment.                                                         |
| Black            | Python formatting.                                                                  |
| Ruff             | Python linting.                                                                     |
| Pytest           | Static and contract validation tests.                                               |

---

## Repository Structure

```text
clickstream-personalization-platform/
├── airflow/
│   └── dags/
│       └── analytics_refresh.py
├── clickhouse/
│   └── users.d/
├── config/
│   ├── filebeat.yml
│   ├── settings.yaml
│   └── spark-defaults.conf
├── data/
│   ├── reference/
│   │   └── product_catalog.csv
│   ├── source/
│   ├── minio/
│   └── clickhouse/
├── diagrams/
│   ├── 01_architecture_overview.png
│   ├── 02_data_flow.png
│   ├── 03_lakehouse_zones.png
│   ├── 04_cdc_scd2_flow.png
│   ├── 05_clickhouse_olap_model.png
│   ├── 06_analytics_refresh_orchestration.png
│   ├── 07_data_quality_audit_reconciliation.png
│   ├── 08_business_key_relationships.png
│   └── 09_bronze_silver_gold_flow.png
├── docker/
│   ├── Dockerfile.airflow
│   ├── Dockerfile.observability
│   └── Dockerfile.spark
├── docs/
│   ├── 01_PROJECT_ARCHITECTURE.md
│   ├── 02_DATA_SOURCES_AND_CONTRACTS.md
│   ├── 03_PIPELINES_QUALITY_AND_LAKEHOUSE.md
│   ├── 04_SERVING_AND_DASHBOARDS.md
│   ├── 05_OPERATIONS_AND_VALIDATION.md
│   └── 06_REPOSITORY_GUIDE.md
├── observability_ui/
│   ├── app.py
│   └── services/
├── power_BI_dashboard/
│   └── project_clickstream.pbix
├── reports/
├── runtime/
├── screenshots/
├── spark_jobs/
├── src/
│   └── platform_core/
├── tests/
├── docker-compose.yml
├── main.py
├── pyproject.toml
├── requirements.txt
└── requirements-dev.txt
```

---

## Run the Platform

### 1. Prepare the environment

Create and activate a Python virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install host-side runtime dependencies:

```bash
pip install -r requirements.txt
```

Install development tools:

```bash
pip install -r requirements-dev.txt
```

Create the local environment file from the example:

```bash
cp .env.example .env
```

Update `.env` with the required local values:

```text
CALENDARIFIC_API_KEY=...
GEOIP_DATABASE_PATH=...
```

The GeoIP path must point to a local GeoLite2 City `.mmdb` file.

---

### 2. Build the platform from a clean state

```bash
python main.py init
```

The initialization workflow performs:

1. Environment validation.
2. Local source generation.
3. Docker infrastructure startup.
4. Iceberg lakehouse bootstrap.
5. PostgreSQL seed and Debezium CDC setup.
6. Spark streaming startup.
7. Controlled CDC mutations.
8. Initial streaming load verification.
9. Analytics refresh and serving publication.

---

### 3. Check platform status

```bash
python main.py status
```

The status command reports service health, streaming state, validation status, and active serving build evidence.

---

### 4. Start an existing platform

```bash
python main.py start
```

This starts the existing containers and resumes the preserved local state.

---

### 5. Stop the platform

```bash
python main.py stop
```

This stops containers while preserving generated data, checkpoints, reports, and local storage.

---

### 6. Reset local dynamic state

```bash
python main.py reset --confirm
```

This removes dynamic runtime state and returns the project to a clean first-run state while preserving source code, reference data, documentation, and configuration files.

---

## Developer Quality Checks

The project includes formatting, linting, syntax checks, and contract tests.

```bash
black .
ruff check .
pytest -q
```

Targeted syntax validation can also be executed with:

```bash
python -m py_compile \
  main.py \
  airflow/dags/analytics_refresh.py \
  observability_ui/app.py \
  observability_ui/services/probes.py \
  spark_jobs/bootstrap_lakehouse.py \
  spark_jobs/streaming_ingestion.py \
  spark_jobs/weather_enrichment.py \
  spark_jobs/holiday_enrichment.py \
  spark_jobs/user_scd2_incremental.py \
  spark_jobs/validate_lakehouse.py \
  spark_jobs/publish_clickhouse.py
```

The tests include project contract checks that protect the final serving model, dashboard view contract, observability structure, and rejected serving-layer drift.

---

## Documentation

| Document                                                                        | Description                                                                                                |
| ------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| [Project Architecture](docs/01_PROJECT_ARCHITECTURE.md)                         | End-to-end architecture, platform layers, processing paths, and system responsibilities.                   |
| [Data Sources and Contracts](docs/02_DATA_SOURCES_AND_CONTRACTS.md)             | Source inventory, ingestion contracts, business keys, validation rules, and relationships.                 |
| [Pipelines, Quality, and Lakehouse](docs/03_PIPELINES_QUALITY_AND_LAKEHOUSE.md) | Spark streaming, batch processing, Iceberg tables, quarantine handling, audit model, and validation logic. |
| [Serving and Dashboards](docs/04_SERVING_AND_DASHBOARDS.md)                     | ClickHouse serving model, twelve Power BI views, dashboard pages, and semantic model responsibilities.     |
| [Operations and Validation](docs/05_OPERATIONS_AND_VALIDATION.md)               | Operations Console, health checks, validation reports, serving checks, and operational evidence.           |
| [Repository Guide](docs/06_REPOSITORY_GUIDE.md)                                 | Repository structure, generated folders, configuration files, and developer tooling.                       |

---

## Visual Evidence

The repository includes visual evidence for the platform and dashboard:

| Area              | Evidence                                                                                                                                                                                                                                                                         |
| ----------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Docker platform   | `screenshots/01_docker_compose_healthy.png`                                                                                                                                                                                                                                      |
| Platform status   | `screenshots/02_main_status_healthy_1.png`, `screenshots/02_main_status_healthy_2.png`                                                                                                                                                                                           |
| Kafka topics      | `screenshots/03_kafka_topics.png`                                                                                                                                                                                                                                                |
| MinIO warehouse   | `screenshots/04_minio_warehouse_bucket_1.png`, `screenshots/04_minio_warehouse_bucket_2.png`, `screenshots/04_minio_warehouse_bucket_3.png`                                                                                                                                      |
| Spark streaming   | `screenshots/05_spark_streaming_status.png`                                                                                                                                                                                                                                      |
| Airflow refresh   | `screenshots/06_airflow_or_refresh_jobs_passed_1.png`, `screenshots/06_airflow_or_refresh_jobs_passed_2.png`                                                                                                                                                                     |
| Validation        | `screenshots/07_validation_latest_passed_1.png`, `screenshots/07_validation_latest_passed_2.png`                                                                                                                                                                                 |
| Serving           | `screenshots/08_serving_latest_passed.png`                                                                                                                                                                                                                                       |
| ClickHouse        | `screenshots/14_clickhouse_row_counts.png`                                                                                                                                                                                                                                       |
| Context analytics | `screenshots/15_clickhouse_geo_weather_context_1.png`, `screenshots/15_clickhouse_geo_weather_context_2.png`                                                                                                                                                                     |
| Power BI          | `screenshots/16_powerbi_dashboard_Executive_Overview.png`, `screenshots/17_powerbi_dashboard_Growth&Revenue.png`, `screenshots/18_powerbi_dashboard_Funnel&Journey.png`, `screenshots/19_powerbi_dashboard_Personalization&Context.png`, `screenshots/20_powerbi_data_model.png` |

---

## Final Analytical Contract

The final analytical contract is intentionally clean:

```text
Iceberg lakehouse
  → ClickHouse physical serving tables
  → Twelve stable ClickHouse v_* views
  → Power BI Import model
```

Power BI reads curated serving views only.
Raw, processed, audit, and internal operational tables remain outside the reporting model.
Dashboard-specific calculations are handled inside Power BI, while ClickHouse provides the governed serving layer.

---
