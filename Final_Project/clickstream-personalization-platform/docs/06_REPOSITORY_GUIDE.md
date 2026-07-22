# Repository Profile

## Purpose

This document describes the repository structure of **Clickstream Personalization Platform**.

The repository is organized as a complete local data engineering platform. It contains the source code, service definitions, Spark processing jobs, Airflow orchestration, ClickHouse serving assets, Power BI report, architecture diagrams, validation evidence, screenshots, tests, and documentation required to understand the project from source ingestion through dashboard consumption.

This document focuses on the repository itself: what each directory represents, which assets are part of the project definition, which files are generated at runtime, and how the repository is organized for review, execution, and presentation.

---

## Repository Composition

```text
clickstream-personalization-platform/
├── airflow/
├── clickhouse/
├── config/
├── data/
├── diagrams/
├── docker/
├── docs/
├── observability_ui/
├── power_BI_dashboard/
├── reports/
├── runtime/
├── screenshots/
├── spark_jobs/
├── src/
├── tests/
├── docker-compose.yml
├── main.py
├── pyproject.toml
├── requirements.txt
└── requirements-dev.txt
```

| Area | Role |
|---|---|
| `main.py` | Main CLI entry point for the platform lifecycle. |
| `src/platform_core/` | Host-side platform orchestration, source generation, CDC setup, validation helpers, and operational status logic. |
| `spark_jobs/` | Spark Structured Streaming and Spark Batch processing jobs. |
| `airflow/` | Airflow analytical refresh workflow. |
| `docker/` | Docker image definitions for Spark, Airflow, and the Operations Console. |
| `config/` | Runtime configuration files for Spark, Filebeat, and platform settings. |
| `clickhouse/` | ClickHouse configuration assets. |
| `observability_ui/` | Streamlit Operations Console. |
| `power_BI_dashboard/` | Power BI report file. |
| `diagrams/` | Architecture and data-flow diagrams. |
| `screenshots/` | Runtime, validation, serving, and dashboard screenshots. |
| `docs/` | Detailed project documentation. |
| `tests/` | Static project contract and quality tests. |
| `reports/` | Generated validation and serving reports. |
| `runtime/` | Generated operational state and health snapshots. |
| `data/` | Reference data, generated source data, and local service-backed storage. |

The repository is structured by platform responsibility rather than by programming language alone. This makes the ingestion layer, processing layer, serving layer, reporting layer, and operations layer visible from the folder layout.

---

## Platform Entry Point

The main project entry point is:

```text
main.py
```

It provides the platform lifecycle interface.

| Command | Role |
|---|---|
| `python main.py init` | Builds the platform from a clean first-run state. |
| `python main.py start` | Starts an existing local platform state. |
| `python main.py status` | Displays service health, streaming state, validation status, and active serving evidence. |
| `python main.py stop` | Stops local services while preserving generated state. |
| `python main.py reset --confirm` | Clears generated runtime state for a new first-run execution. |

The CLI keeps platform execution centralized and provides a consistent operational interface across source generation, infrastructure startup, lakehouse initialization, streaming, CDC, validation, serving, and status inspection.

---

## Core Platform Package

```text
src/platform_core/
```

The core package contains host-side Python modules used by the CLI and project workflows.

| Capability | Description |
|---|---|
| Environment validation | Checks required host tools, configuration files, credentials, local paths, and runtime prerequisites. |
| Docker orchestration | Starts, stops, and inspects Docker Compose services. |
| Source generation | Creates local clickstream, web log, PostgreSQL seed, and reference source data. |
| Kafka readiness | Validates business topics and streaming infrastructure readiness. |
| CDC setup | Creates and validates Debezium connectors for PostgreSQL source tables. |
| PostgreSQL seed loading | Loads users, orders, and order items into the transactional source database. |
| Lakehouse coordination | Executes Spark jobs that initialize Iceberg namespaces and tables. |
| Runtime status | Produces health evidence and consolidated platform status. |
| Analytical refresh control | Runs the scheduled Spark batch refresh sequence from the host workflow. |

The package represents the platform control layer. Spark jobs remain responsible for distributed data processing.

---

## Spark Processing Layer

```text
spark_jobs/
```

The Spark layer contains the streaming and batch jobs that transform source data into lakehouse tables and serving outputs.

| File | Role |
|---|---|
| `bootstrap_lakehouse.py` | Creates Iceberg namespaces, raw tables, processed tables, and audit tables. |
| `streaming_ingestion.py` | Runs Spark Structured Streaming over Kafka topics and writes raw, clean, quarantine, and audit outputs. |
| `user_scd2_incremental.py` | Builds the SCD Type 2 user profile dimension from clean user CDC events. |
| `weather_enrichment.py` | Enriches observed location-hour combinations with weather context. |
| `holiday_enrichment.py` | Enriches observed country-year combinations with holiday context. |
| `validate_lakehouse.py` | Validates lakehouse readiness, quality evidence, relationships, and analytical outputs. |
| `publish_clickhouse.py` | Publishes curated ClickHouse serving tables and stable Power BI-facing views. |
| `serving_common.py` | Defines shared ClickHouse serving table, view, and validation contracts. |

The Spark layer is divided into two processing paths:

```text
Streaming path:
  streaming_ingestion.py

Batch path:
  bootstrap_lakehouse.py
  user_scd2_incremental.py
  weather_enrichment.py
  holiday_enrichment.py
  validate_lakehouse.py
  publish_clickhouse.py
```

The streaming path handles continuous Kafka processing. The batch path handles lakehouse initialization, SCD2, external context enrichment, validation, and serving publication.

---

## Airflow Orchestration

```text
airflow/
└── dags/
    └── analytics_refresh.py
```

Airflow coordinates the analytical refresh workflow.

The refresh sequence contains:

```text
user_scd2
weather_enrichment
holiday_enrichment
validate_lakehouse
publish_serving
```

This workflow turns clean lakehouse data into historical user dimensions, context-enriched tables, validation evidence, and ClickHouse serving outputs.

Airflow owns the scheduled analytical batch path. Continuous ingestion remains handled by Spark Structured Streaming.

---

## Docker Runtime Definition

```text
docker-compose.yml
```

The Docker Compose topology defines the local runtime environment.

| Service | Role |
|---|---|
| `postgres` | Transactional source database and Iceberg JDBC catalog backend. |
| `zookeeper` | Kafka coordination service. |
| `kafka1` | Kafka broker. |
| `kafka2` | Kafka broker. |
| `kafka3` | Kafka broker. |
| `kafka-ui` | Kafka topic and consumer inspection UI. |
| `debezium` | Debezium Connect runtime for PostgreSQL CDC. |
| `minio` | S3-compatible object storage for the Iceberg warehouse. |
| `filebeat` | Web server log shipper into Kafka. |
| `spark-engine` | Spark runtime for streaming and batch jobs. |
| `airflow` | Batch orchestration service. |
| `clickhouse` | OLAP serving database. |
| `observability-ui` | Streamlit Operations Console. |

The runtime topology supports streaming ingestion, CDC capture, lakehouse storage, scheduled batch orchestration, OLAP serving, operational visibility, and BI consumption.

---

## Docker Image Definitions

```text
docker/
├── Dockerfile.airflow
├── Dockerfile.observability
└── Dockerfile.spark
```

| Dockerfile | Role |
|---|---|
| `Dockerfile.spark` | Builds the Spark runtime image with the dependencies required by streaming and batch jobs. |
| `Dockerfile.airflow` | Builds the Airflow runtime image with DAG execution support. |
| `Dockerfile.observability` | Builds the Streamlit Operations Console runtime image. |

The Docker image definitions keep service-specific dependencies separated while preserving a reproducible local runtime.

---

## Configuration Boundary

```text
config/
```

| File | Role |
|---|---|
| `settings.yaml` | Main project configuration for topics, paths, service endpoints, and platform settings. |
| `filebeat.yml` | Filebeat configuration for shipping web server logs into Kafka. |
| `spark-defaults.conf` | Spark runtime defaults and package configuration. |

Configuration files define runtime behavior without mixing environment settings into processing code. This keeps service endpoints, topic names, storage settings, and execution defaults visible and reviewable.

---

## Environment Configuration

```text
.env
.env.example
```

The environment file stores local values required during execution.

Typical values include:

```text
CALENDARIFIC_API_KEY=...
GEOIP_DATABASE_PATH=...
```

| File | Role |
|---|---|
| `.env.example` | Template showing required environment keys. |
| `.env` | Local machine configuration with private or machine-specific values. |

The template belongs to the repository. The local `.env` file belongs to the execution environment.

---

## Data Assets

```text
data/
```

The `data` directory represents local data used by the project during generation, ingestion, and runtime storage.

Typical structure:

```text
data/
├── reference/
├── source/
├── minio/
└── clickhouse/
```

| Path | Role |
|---|---|
| `data/reference/` | Project reference assets such as the static product catalog. |
| `data/source/` | Generated source files used by the local ingestion workflows. |
| `data/minio/` | Local MinIO object storage data. |
| `data/clickhouse/` | Local ClickHouse storage data. |

The reference layer is part of the project definition. Container-backed storage paths are generated by platform execution.

---

## Reference Data

```text
data/reference/
└── product_catalog.csv
```

The product catalog is the static product reference source.

It is loaded into:

```text
ecommerce.processed.product_catalog_clean
```

The product reference data supports:

| Area | Role |
|---|---|
| Product dimension | Provides product identifiers, names, categories, prices, and inventory context. |
| Product performance | Supports product-level views, units sold, and revenue analysis. |
| Category analysis | Enables category-level reporting and dashboard filtering. |
| Personalization | Adds product attributes to user-product interest signals. |
| Power BI | Supports slicers, product tables, and category visuals. |

---

## Runtime State

```text
runtime/
```

The runtime directory stores generated operational state.

| Path | Role |
|---|---|
| `runtime/observability/latest.json` | Latest consolidated platform health snapshot. |
| `runtime/observability/history.jsonl` | Historical operational health snapshots. |
| Runtime process files | Process-level state for source generation and streaming workflows. |
| Runtime metadata | Operational metadata generated by project commands. |
| Local checkpoints | Processing progress state where applicable. |

The runtime directory is produced by platform execution and is separate from the static repository definition.

---

## Reports

```text
reports/
```

The reports directory stores generated validation and serving evidence.

| File | Role |
|---|---|
| `validation_latest.json` | Latest lakehouse validation result. |
| `serving_latest.json` | Latest ClickHouse serving publication result. |
| `streaming_start_report.json` | Streaming startup evidence. |
| Final evidence copies | Saved reports from verified project runs when included. |

Reports provide machine-readable evidence for validation, serving, and operational inspection.

---

## ClickHouse Serving Assets

```text
clickhouse/
spark_jobs/serving_common.py
spark_jobs/publish_clickhouse.py
```

ClickHouse is the OLAP serving database for Power BI.

```text
personalization_olap
```

The final serving contract exposes twelve stable Power BI-facing views:

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

| Asset | Role |
|---|---|
| `clickhouse/` | ClickHouse service configuration. |
| `spark_jobs/serving_common.py` | Shared serving table and view contract. |
| `spark_jobs/publish_clickhouse.py` | Serving publication job that writes ClickHouse outputs and validates views. |

ClickHouse exposes curated serving outputs only. Raw, processed, audit, and operational Iceberg tables remain outside the Power BI model.

---

## Power BI Assets

```text
power_BI_dashboard/
└── project_clickstream.pbix
```

The Power BI report connects to ClickHouse serving views in Import mode.

The dashboard pages are:

| Page | Role |
|---|---|
| Executive Overview | High-level business, engagement, and performance indicators. |
| Growth & Revenue | Revenue, orders, product contribution, category behavior, and growth analysis. |
| Funnel & Journey | Conversion funnel, session progression, journey behavior, and navigation analysis. |
| Personalization & Context | Personalization candidates, product interest signals, geo context, weather context, and holiday context. |

Power BI owns semantic modeling, DAX measures, slicers, visual formatting, and report presentation. ClickHouse owns the curated analytical serving contract.

---

## Observability Assets

```text
observability_ui/
├── app.py
└── services/
```

The Operations Console is implemented with Streamlit.

| Component | Role |
|---|---|
| `app.py` | Streamlit application entry point and UI layout. |
| `services/` | Probe and evidence helpers used by the console. |

The console presents operational evidence across:

```text
Infrastructure
Kafka and CDC
Spark Streaming
Lakehouse Storage
Data Quality
SCD Type 2
Batch and APIs
Serving and Power BI
```

The console is a read-only operational view over platform evidence.

---

## Documentation Assets

```text
docs/
```

| Document | Role |
|---|---|
| `01_PROJECT_ARCHITECTURE.md` | End-to-end architecture, platform layers, processing paths, and system responsibilities. |
| `02_DATA_SOURCES_AND_CONTRACTS.md` | Source inventory, ingestion contracts, keys, validation rules, and relationships. |
| `03_PIPELINES_QUALITY_AND_LAKEHOUSE.md` | Streaming, batch, Iceberg lakehouse design, quality model, quarantine, and audit evidence. |
| `04_SERVING_AND_DASHBOARDS.md` | ClickHouse serving model, twelve Power BI views, dashboard pages, and reporting contract. |
| `05_OPERATIONS_AND_VALIDATION.md` | Platform operations, health checks, validation reports, serving checks, and evidence outputs. |
| `06_REPOSITORY_GUIDE.md` | Repository structure, project assets, generated state boundaries, naming conventions, and path references. |

The documentation set is organized so each file has a distinct responsibility.

---

## Diagram Assets

```text
diagrams/
```

| Diagram | Role |
|---|---|
| `01_architecture_overview.png` | End-to-end platform architecture. |
| `02_data_flow.png` | Streaming, CDC, and batch data flow. |
| `03_lakehouse_zones.png` | Raw, processed, and audit lakehouse zones. |
| `04_cdc_scd2_flow.png` | PostgreSQL CDC and SCD Type 2 processing flow. |
| `05_clickhouse_olap_model.png` | ClickHouse serving and Power BI view model. |
| `06_analytics_refresh_orchestration.png` | Airflow analytical refresh workflow. |
| `07_data_quality_audit_reconciliation.png` | Data quality, quarantine, and reconciliation model. |
| `08_business_key_relationships.png` | Business key relationships across sources. |
| `09_bronze_silver_gold_flow.png` | Bronze, Silver, Gold, and consumption progression. |

The diagram set provides visual documentation for platform architecture, processing flow, storage design, quality controls, serving structure, and analytical relationships.

---

## Screenshot Assets

```text
screenshots/
```

The screenshots directory stores visual evidence from the running platform and Power BI report.

| Area | Files |
|---|---|
| Docker health | `01_docker_compose_healthy.png` |
| Platform status | `02_main_status_healthy_1.png`, `02_main_status_healthy_2.png` |
| Kafka topics | `03_kafka_topics.png` |
| MinIO warehouse | `04_minio_warehouse_bucket_1.png`, `04_minio_warehouse_bucket_2.png`, `04_minio_warehouse_bucket_3.png` |
| Spark streaming | `05_spark_streaming_status.png` |
| Airflow refresh | `06_airflow_or_refresh_jobs_passed_1.png`, `06_airflow_or_refresh_jobs_passed_2.png` |
| Validation | `07_validation_latest_passed_1.png`, `07_validation_latest_passed_2.png` |
| Serving | `08_serving_latest_passed.png` |
| ClickHouse row counts | `14_clickhouse_row_counts.png` |
| Context analytics | `15_clickhouse_geo_weather_context_1.png`, `15_clickhouse_geo_weather_context_2.png` |
| Power BI dashboard | `16_powerbi_dashboard_Executive_Overview.png`, `17_powerbi_dashboard_Growth&Revenue.png`, `18_powerbi_dashboard_Funnel&Journey.png`, `19_powerbi_dashboard_Personalization&Context.png` |
| Power BI model | `20_powerbi_data_model.png` |

The screenshot set connects the implementation to visible operational and analytical outputs.

---

## Test Assets

```text
tests/
```

The tests protect the final project contract.

| Test Area | Role |
|---|---|
| Serving contract | Confirms the serving layer exposes the expected twelve stable tables and views. |
| Documentation alignment | Confirms Power BI documentation references the expected serving views. |
| Operations Console structure | Confirms operational sections remain aligned with platform layers. |
| Weather enrichment | Confirms enrichment upsert and coverage behavior. |
| Serving validation | Confirms serving publication validates tables and active views. |
| Checkout contract | Confirms completed checkout events require an order identifier. |

The test suite protects structural project contracts in addition to Python correctness.

---

## Python Tooling

```text
requirements.txt
requirements-dev.txt
pyproject.toml
```

| File | Role |
|---|---|
| `requirements.txt` | Runtime Python dependencies. |
| `requirements-dev.txt` | Development tooling dependencies. |
| `pyproject.toml` | Configuration for Black, Ruff, and Pytest. |

The tooling layer keeps code formatting, linting, and tests consistent across the repository.

---

## Source-Controlled Assets

The source package is composed of project files that define the platform.

```text
airflow/
clickhouse/
config/
data/reference/
diagrams/
docker/
docs/
observability_ui/
power_BI_dashboard/
screenshots/
spark_jobs/
src/
tests/
.env.example
docker-compose.yml
main.py
pyproject.toml
requirements.txt
requirements-dev.txt
README.md
```

These assets represent the repository definition: code, configuration templates, reference data, diagrams, screenshots, dashboard file, tests, and documentation.

---

## Generated Runtime State

Generated local state is separate from the repository definition.

```text
.venv/
__pycache__/
.pytest_cache/
.ruff_cache/
runtime/
data/minio/
data/clickhouse/
data/postgres/
data/kafka/
data/zookeeper/
logs/
*.pyc
.env
```

These paths represent local execution state, caches, private configuration, and container-backed storage.

---

## Naming Conventions

| Area | Convention |
|---|---|
| Kafka topics | Lowercase, hyphen-separated names such as `clickstream-events`. |
| Iceberg namespaces | `ecommerce.raw`, `ecommerce.processed`, `ecommerce.audit`. |
| Iceberg clean tables | Descriptive snake_case names ending with `_clean` where applicable. |
| CDC clean tables | Source table name followed by `_cdc_clean`. |
| SCD2 table | `user_profile_scd2`. |
| ClickHouse physical tables | Dimensions, facts, and marts using `dim_`, `fact_`, and `mart_` prefixes. |
| ClickHouse views | Stable Power BI-facing views using the `v_` prefix. |
| Reports | Latest report files using `_latest.json`. |
| Documentation | Numbered Markdown files inside `docs/`. |
| Screenshots | Numbered files with descriptive names. |
| Diagrams | Numbered files matching documentation order. |

Consistent naming makes the repository easier to inspect, test, validate, document, and present.

---

## Path Reference

| Path | Role |
|---|---|
| `main.py` | CLI entry point. |
| `docker-compose.yml` | Local service topology. |
| `config/settings.yaml` | Main platform settings. |
| `config/filebeat.yml` | Web log shipping configuration. |
| `config/spark-defaults.conf` | Spark runtime defaults. |
| `spark_jobs/streaming_ingestion.py` | Spark Structured Streaming job. |
| `spark_jobs/bootstrap_lakehouse.py` | Iceberg lakehouse bootstrap job. |
| `spark_jobs/user_scd2_incremental.py` | User SCD Type 2 batch job. |
| `spark_jobs/weather_enrichment.py` | Weather context enrichment job. |
| `spark_jobs/holiday_enrichment.py` | Holiday context enrichment job. |
| `spark_jobs/validate_lakehouse.py` | Lakehouse validation job. |
| `spark_jobs/publish_clickhouse.py` | ClickHouse serving publication job. |
| `spark_jobs/serving_common.py` | Shared serving contract definitions. |
| `airflow/dags/analytics_refresh.py` | Analytical refresh DAG. |
| `observability_ui/app.py` | Operations Console application. |
| `power_BI_dashboard/project_clickstream.pbix` | Power BI report file. |
| `reports/validation_latest.json` | Latest validation report. |
| `reports/serving_latest.json` | Latest serving report. |
| `runtime/observability/latest.json` | Latest operational health snapshot. |

---

## Repository Contract Summary

The repository represents the complete project definition:

```text
Source generation and configuration
  → Dockerized platform services
  → Kafka, Filebeat, and Debezium ingestion
  → Spark streaming and batch processing
  → Iceberg raw, processed, and audit storage
  → ClickHouse serving publication
  → Power BI reporting
  → Operations and validation evidence
```

The repository structure makes the project understandable, reproducible, verifiable, and presentable as a complete end-to-end data engineering platform.