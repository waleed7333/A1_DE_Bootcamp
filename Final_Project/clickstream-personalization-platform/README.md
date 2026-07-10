# Clickstream Personalization Platform

## Overview

**Clickstream Personalization Platform** is an end-to-end data engineering project designed to collect, process, validate, enrich, and serve website behavioral data for personalization and business intelligence.

The platform analyzes user clickstream behavior, website access logs, product interactions, user profiles, orders, order items, geographic context, weather context, and holiday context to understand:

* User navigation patterns
* Funnel conversion and revenue leakage
* Popular products and content
* Technical experience impact on user journeys
* Geography and context-driven behavior
* Personalization and recommendation opportunities

The final analytical output is served through **ClickHouse** and consumed by **Power BI** using dashboard-ready OLAP views.

---

## Business Problem

Modern e-commerce teams need to understand not only what users purchase, but also how users move through the website before they purchase or abandon.

This project answers business questions such as:

* Where do users drop off between product view and checkout completion?
* Which products receive high interest but low conversion?
* Which user segments, devices, cities, or traffic sources convert better?
* Do slow endpoints or HTTP errors affect checkout completion?
* How do weather and holidays align with observed demand patterns?
* Which products or segments are strong candidates for personalization?

The platform connects behavioral events, infrastructure logs, transactional data, master data, and external context into one governed analytical pipeline.

---

## Architecture Summary

The platform is built around two processing paths:

```text
Real-Time Streaming Path
Clickstream / Web Logs / CDC
→ Kafka
→ Spark Structured Streaming
→ Iceberg on MinIO
```

```text
Scheduled Batch Path
Product Catalog / SCD2 / Weather / Holidays / Validation / Serving
→ Spark Batch Jobs
→ Iceberg on MinIO
→ ClickHouse
→ Power BI
```

High-level flow:

```text
Data Sources
→ Kafka / Filebeat / Debezium / API Pulls
→ Spark Streaming and Spark Batch
→ Apache Iceberg Lakehouse on MinIO
→ Data Quality, Audit, and Quarantine
→ ClickHouse OLAP Serving Layer
→ Power BI Dashboard
```

---

## Data Sources

| Category                | Source               | Data Type                      | Processing Style             |
| ----------------------- | -------------------- | ------------------------------ | ---------------------------- |
| User Behavioral Data    | Clickstream Events   | JSON Events / JSONL            | Real-Time Streaming          |
| Infrastructure Data     | Web Server Logs      | Structured JSON `.log` Files   | Real-Time Streaming          |
| Master Data             | Product Catalog      | CSV Snapshot                   | Static Batch                 |
| Master Data             | User Profile         | PostgreSQL Table               | CDC + Incremental Batch      |
| Transactional Data      | Orders               | PostgreSQL Table               | CDC + Incremental Batch      |
| Transactional Data      | Order Items          | PostgreSQL Table               | CDC + Incremental Batch      |
| External Reference Data | GeoIP Database       | MaxMind GeoLite2 `.mmdb`       | Streaming / Batch Enrichment |
| External Context Data   | Weather API          | Open-Meteo JSON API Response   | Scheduled Batch API Pull     |
| External Context Data   | Holiday Calendar API | Calendarific JSON API Response | Scheduled Batch API Pull     |

---

## Technology Stack

| Tool             | Role in the Project             | Key Features Used                                                                        |
| ---------------- | ------------------------------- | ---------------------------------------------------------------------------------------- |
| Docker Compose   | Local platform orchestration    | Multi-container platform, service health checks, isolated local runtime                  |
| PostgreSQL       | Operational source database     | Users, Orders, Order Items source tables, logical replication, WAL-based CDC             |
| Debezium Connect | CDC capture                     | Snapshot reads, insert/update/delete capture, Kafka CDC topics                           |
| Apache Kafka     | Streaming backbone              | 3 brokers, 3 partitions, replication factor 3, minimum ISR 2, source topic contracts     |
| Filebeat         | Web log ingestion               | Reads structured `.log` files and publishes web logs to Kafka                            |
| Apache Spark     | Processing engine               | Structured Streaming, batch jobs, validation, CDC processing, enrichment, serving builds |
| Apache Iceberg   | Lakehouse table format          | Raw, processed, audit tables, snapshot-based storage, schema-managed tables              |
| MinIO            | S3-compatible lakehouse storage | Iceberg warehouse bucket, local object storage, lakehouse persistence                    |
| ClickHouse       | OLAP serving layer              | Fast analytical tables, facts, dimensions, marts, Power BI-ready views                   |
| Airflow          | Batch orchestration             | Scheduled Spark batch jobs, SCD2, API enrichment, validation, serving refresh            |
| Power BI         | Business dashboard              | Import mode, ClickHouse views, executive dashboard, funnel and personalization analytics |
| Streamlit        | Operations Console              | Platform health, validation evidence, serving status, source and quality monitoring      |
| MaxMind GeoLite2 | GeoIP enrichment                | IP-to-country/city/latitude/longitude/timezone enrichment                                |
| Open-Meteo       | Weather context                 | Historical weather enrichment by latitude, longitude, and hour                           |
| Calendarific     | Holiday context                 | Country/year holiday enrichment for context analysis                                     |

---

## Core Platform Capabilities

### Real-Time Data Processing

The platform continuously processes:

* Clickstream events from Kafka topic `clickstream-events`
* Web server logs from Kafka topic `webserver-logs`
* User CDC events from Kafka topic `users-cdc`
* Order CDC events from Kafka topic `orders-cdc`
* Order item CDC events from Kafka topic `order-items-cdc`

Spark Structured Streaming validates, deduplicates, enriches, and writes clean data to Iceberg.

---

### CDC and Incremental Processing

The project uses Debezium CDC for three PostgreSQL source tables:

```text
public.users
public.orders
public.order_items
```

CDC events preserve:

* Operation type
* Before image
* After image
* Source LSN
* Source timestamp
* Kafka metadata

The User Profile CDC stream is used to build a **User SCD Type 2** table through an incremental Spark batch job.

---

### Lakehouse Storage

The lakehouse is implemented using Apache Iceberg on MinIO.

Main layers:

```text
raw
processed
audit
```

The lakehouse stores:

* Original Kafka payloads
* Clean processed tables
* CDC clean tables
* SCD Type 2 user profiles
* Weather and holiday enrichment
* Quality metrics
* Quarantine records
* Validation and serving audit records

---

### Data Quality and Audit

The platform validates source records before they enter clean tables.

Examples of quality checks:

* Required ID checks
* Event type validation
* Product event validation
* Checkout event validation
* CDC primary key validation
* Duplicate detection
* Raw-to-clean reconciliation
* SCD2 current-row validation
* API coverage checks

Invalid or duplicate records are not silently dropped. They are written to audit and quarantine tables with rejection reasons.

---

### Serving Layer

ClickHouse is used as the analytical serving layer.

Power BI reads only from ClickHouse views prefixed with:

```text
v_
```

Main serving views include:

```text
v_dim_date
v_dim_product
v_dim_user_current
v_fact_clickstream_event
v_fact_order
v_fact_order_item
v_mart_journey_session
v_mart_navigation_paths
v_mart_product_performance_daily
v_mart_web_experience_daily
v_mart_context_impact_daily
v_mart_personalization_candidates
```

This design keeps Power BI focused on fast, dashboard-ready analytical models instead of raw processing logic.

---

## Repository Structure

```text
clickstream-personalization-platform
│
├── config/
│   ├── settings.yaml
│   ├── filebeat.yml
│   └── spark-defaults.conf
│
├── airflow/
│   └── dags/
│       └── analytics_refresh_dag.py
├── docker/
│   ├── Dockerfile.spark
│   └── Dockerfile.airflow
│
├── docs/
│   ├── 01_PROJECT_AND_ARCHITECTURE.md
│   ├── 02_DATA_SOURCES_AND_CONTRACTS.md
│   ├── 03_PROCESSING_AND_QUALITY.md
│   ├── 04_DATA_MODEL_CLICKHOUSE_POWERBI.md
│   ├── 05_OPERATIONS_RUNBOOK.md
│   └── 06_DEMO_TESTING_LIMITATIONS.md
│
├── screenshots /
│
├── diagrams/
│
├── power_BI_dashboard/
│
├── Data/
│   ├── reference/
│   │   ├── products.csv
│   │   └── GeoLite2_City.mmdb
│   │
│   └── source/
│       ├── clickstream/
│       │   └── clickstream_events.jsonl
│       │
│       ├── webserver/ 
│       │   └── webserver_access.log
│       │
│       └── postgres/
│           ├── users_seed.csv
│           ├── orders_seed.csv
│           └── order_items_seed.csv
│
├── observability_ui/
│   ├── requirements.txt
│   └── app.py
│
├── spark_jobs/
│   ├── bootstrap_lakehouse.py
│   ├── holiday_enrichment.py
│   ├── publish_clickhouse.py
│   ├── serving_common.py
│   ├── streaming_ingestion.py
│   ├── user_scd2_incremental.py
│   ├── validate_lakehouse.py
│   ├── verify_lakehouse_bootstrap.py
│   └── weather_enrichment.py
│
├── src/
│   └── platform_core/
│       ├── cdc.py
│       ├── compose.py
│       ├── enviroment.py
│       ├── health_collector.py
│       ├── infrastructure.py
│       ├── initializer.py
│       ├── live_source_generator.py
│       ├── operations.py
│       ├── orchestration.py
│       ├── source_generation.py
│       ├── spark_job_runner.py
│       └── streaming.py
│
├── tests/
│   └── test_project_contract.py
│
├── reports/
│
├── runtime/
│
├── main.py
│
├── docker-compose.yml
├── .gitignore
├── requirements.txt
├── .env.example
└── README.md
```

---

## Required Local Files

Before the first run, the following local reference files and secrets are required:

```text
.env
data/reference/product_catalog.csv
data/reference/GeoLite2-City.mmdb
```

The `.env` file is created from `.env.example` and contains local development secrets such as database passwords and API keys.

The GeoLite2 database is used for IP-based geographic enrichment.

---

## First-Time Run

Run the full platform initialization:

```bash
python main.py init
```

The initialization performs nine major stages:

```text
1. Environment check
2. Source generation
3. Infrastructure startup
4. Lakehouse initialization
5. PostgreSQL and CDC initialization
6. Streaming startup
7. Controlled CDC mutations
8. Initial streaming load
9. Analytics refresh
```

A successful run ends with:

```text
INIT COMPLETE
Platform status: HEALTHY
Streaming remains active.
```

---

## Start Existing Platform

After stopping the platform while preserving data and checkpoints:

```bash
python main.py start
```

This resumes the existing platform and restarts streaming without deleting lakehouse or database state.

---

## Stop Platform Safely

To stop streaming and containers while preserving local data:

```bash
python main.py stop
```

This stops:

* Live source generator
* Spark streaming process
* Docker Compose services

It preserves:

* MinIO data
* ClickHouse data
* Runtime state
* Reports
* Source code
* Reference data

---

## Reset Platform

To rebuild the platform from a clean dynamic state:

```bash
python main.py reset --confirm
```

Reset removes:

* Docker containers
* Docker volumes
* Runtime state
* Generated source data
* MinIO dynamic lakehouse data
* ClickHouse dynamic data

Reset preserves:

* Source code
* Documentation
* `.env`
* Product Catalog reference file
* GeoLite2 database

After reset, run:

```bash
python main.py init
```

---

## Manual Analytics Refresh

To manually run SCD2, weather enrichment, holiday enrichment, validation, and ClickHouse serving refresh:

```bash
python - <<'PY'
from pathlib import Path
import sys

PROJECT_ROOT = Path.cwd()
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from platform_core.orchestration import run_analytics_refresh

results, ok, run_id = run_analytics_refresh(
    PROJECT_ROOT,
    timeout_seconds=1200,
)

print("run_id:", run_id)
print("ok:", ok)

for item in results:
    print(item)
PY
```

A successful refresh returns:

```text
user_scd2: PASS
weather_enrichment: PASS
holiday_enrichment: PASS
validate_lakehouse: PASS
publish_serving: PASS
```

---

## Validation and Serving Reports

The platform writes operational evidence to:

```text
reports/validation_latest.json
reports/serving_latest.json
```

These reports confirm:

* Lakehouse validation status
* Data quality checks
* Serving build status
* ClickHouse row counts
* Active serving build
* Dashboard readiness

---

## Operations Console

The Operations Console provides a lightweight operational view of the platform.

It shows:

* Platform health
* Streaming status
* Source generation evidence
* Validation status
* Serving status
* Data quality reconciliation
* Required demo evidence

Typical local URL:

```text
http://localhost:8501
```

---

## Dashboard

Power BI connects to ClickHouse using Import mode and reads only serving views prefixed with `v_`.

The executive dashboard is designed around:

```text
Revenue Growth & Personalization Intelligence
```

Main dashboard areas:

* KPI overview
* Funnel conversion
* Revenue leakage
* Product performance
* Personalization candidates
* User segment analysis
* Geo and context behavior
* Navigation paths
* Web experience impact
* Weather and holiday observed associations

---

## Documentation

Detailed documentation is available in the `docs/` directory:


| Document                                           | Purpose                                                                              |
| -------------------------------------------------- | ------------------------------------------------------------------------------------ |
| `docs/01_PROJECT_ARCHITECTURE.md`                  | Architecture, services, processing paths, and runtime modes                          |
| `docs/02_DATA_SOURCES_AND_CONTRACTS.md`            | Source contracts, keys, topics, and validation rules                                 |
| `docs/03_PIPELINES_QUALITY_AND_LAKEHOUSE.md`       | Streaming, CDC, batch jobs, quality, quarantine, and Iceberg layout                  |
| `docs/04_SERVING_AND_DASHBOARDS.md`                | ClickHouse model, Power BI dashboards, and serving refresh behavior                  |
| `docs/05_OPERATIONS_VALIDATION_AND_LIMITATIONS.md` | Runbook, validation, evidence, troubleshooting, limitations, and future enhancements |

---

## Final Project State

The platform implements:

* Batch and real-time processing pipelines
* Multiple heterogeneous data sources
* Kafka-based streaming ingestion
* Filebeat-based log ingestion
* PostgreSQL CDC using Debezium
* Spark Structured Streaming
* Spark batch enrichment and validation
* Apache Iceberg lakehouse tables
* MinIO object storage
* Data quality and quarantine handling
* User SCD Type 2
* GeoIP enrichment
* Weather and holiday enrichment
* ClickHouse OLAP serving
* Power BI dashboard-ready views
* Operations evidence and validation reports

This makes the project a complete data engineering platform for clickstream analysis and website personalization.
